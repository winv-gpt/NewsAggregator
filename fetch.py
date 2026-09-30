"""Fetch news items from RSS feeds / Google News, and daily stock moves."""
import hashlib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import requests

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) newsbot/1.0"
MAX_PER_SOURCE = 40
SUMMARY_CHARS = 800


@dataclass
class Item:
    id: str
    source: str
    title: str
    summary: str
    link: str
    published: Optional[datetime]
    topics: List[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _feed_url(spec: dict) -> str:
    if "url" in spec:
        return spec["url"]
    q = quote_plus(f'{spec["google"]} when:1d')
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _published(entry) -> Optional[datetime]:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def fetch_source(name: str, spec: dict, since: datetime) -> List[Item]:
    url = _feed_url(spec)
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("source %r failed: %s", name, e)
        return []
    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries[:MAX_PER_SOURCE]:
        link = entry.get("link", "")
        title = _clean(entry.get("title", ""))
        if not link or not title:
            continue
        published = _published(entry)
        if published and published < since:
            continue
        source = name
        if "google" in spec:
            # Google News titles end in " - Outlet"; keep the real outlet name.
            outlet = entry.get("source", {}).get("title")
            if outlet:
                title = title.removesuffix(f" - {outlet}")
                source = outlet
        if len(title) < 15:  # e.g. bare site names from Google News
            continue
        summary = _clean(entry.get("summary", ""))
        if summary.startswith(title[:40]):  # Google News "summaries" just repeat the headline
            summary = ""
        items.append(Item(
            id=hashlib.sha1(link.encode()).hexdigest()[:12],
            source=source,
            title=title,
            summary=summary[:SUMMARY_CHARS],
            link=link,
            published=published,
        ))
    if not feed.entries:
        log.warning("source %r returned no entries", name)
    return items


def topic_sources(topic: dict) -> List[str]:
    """Flatten a topic's `sources` block (any nesting of lists) into source names."""
    names = []
    for value in (topic.get("sources") or {}).values():
        names.extend(value if isinstance(value, list) else [value])
    return names


def fetch_all(interests: dict, feeds: Dict[str, dict], since: datetime) -> Dict[str, List[Item]]:
    """Return {topic_key: [items]}. Each source is fetched once even if shared by topics."""
    wanted = {}
    for key, topic in interests["topics"].items():
        for name in topic_sources(topic):
            if name not in feeds:
                log.warning("topic %s: source %r is not in feeds.yaml, skipping", key, name)
                continue
            wanted.setdefault(name, []).append(key)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(wanted, pool.map(lambda n: fetch_source(n, feeds[n], since), wanted)))

    by_topic: Dict[str, Dict[str, Item]] = {k: {} for k in interests["topics"]}
    for name, items in results.items():
        log.info("%-26s %3d new items", name, len(items))
        for item in items:
            for key in wanted[name]:
                by_topic[key].setdefault(item.id, item)
    return {k: list(v.values()) for k, v in by_topic.items()}


@dataclass
class StockMove:
    ticker: str
    close: float
    pct: float
    date: str  # trading day of the latest close, YYYY-MM-DD


def fetch_stock_moves(tickers: List[str]) -> List[StockMove]:
    moves = []
    for ticker in tickers:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            points = [(t, c) for t, c in zip(result["timestamp"], result["indicators"]["quote"][0]["close"])
                      if c is not None]
            if len(points) < 2:
                continue
            (_, prev), (stamp, close) = points[-2], points[-1]
            day = datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d")
            moves.append(StockMove(ticker, close, (close / prev - 1) * 100, day))
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            log.warning("stock %s failed: %s", ticker, e)
    return moves

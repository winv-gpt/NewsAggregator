"""Fetch news items from RSS feeds / Google News, daily stock moves, and 12-month price history."""
import hashlib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, quote_plus

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
    q = quote_plus(f'{spec["google"]} when:{spec.get("when", "1d")}')
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


# Source kinds the bot can't read: X needs the paid X API; market data is fetched separately.
UNSUPPORTED_SOURCES = {"x_accounts", "market_data"}


def topic_sources(topics: Dict[str, dict], key: str) -> List[str]:
    """Flatten a topic's `sources` block (any nesting of lists) into source names.
    `sources: same as <other topic>` reuses that topic's sources."""
    sources = topics[key].get("sources") or {}
    if isinstance(sources, str):
        other = sources.removeprefix("same as").strip()
        if other in topics and other != key and not isinstance(topics[other].get("sources"), str):
            return topic_sources(topics, other)
        log.warning("topic %s: can't understand sources %r, skipping", key, sources)
        return []
    names = []
    for kind, value in sources.items():
        if kind not in UNSUPPORTED_SOURCES:
            names.extend(value if isinstance(value, list) else [value])
    return names


def fetch_all(interests: dict, feeds: Dict[str, dict], since: datetime) -> Dict[str, List[Item]]:
    """Return {topic_key: [items]}. Each source is fetched once even if shared by topics."""
    wanted = {}
    for key in interests["topics"]:
        for name in topic_sources(interests["topics"], key):
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


def fetch_prices(symbol: str, range_: str = "1y") -> List[Tuple[str, float]]:
    """Daily closes from Yahoo Finance as [(YYYY-MM-DD, close)], oldest first; [] on failure."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range={range_}&interval=1d"
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        return [(datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"), c)
                for t, c in zip(result["timestamp"], result["indicators"]["quote"][0]["close"])
                if c is not None]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
        log.warning("prices for %s failed: %s", symbol, e)
        return []


def fetch_stock_moves(tickers: List[str]) -> List[StockMove]:
    moves = []
    for ticker in tickers:
        points = fetch_prices(ticker, "5d")
        if len(points) < 2:
            continue
        (_, prev), (day, close) = points[-2], points[-1]
        moves.append(StockMove(ticker, close, (close / prev - 1) * 100, day))
    return moves

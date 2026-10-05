"""News bot: fetch -> score with Claude -> webpage. Run at each scheduled time.

    python run.py              # full run: builds the page and remembers what was shown
    python run.py --preview    # builds the page only; the next real run still sees the same news
    python run.py --fake-scores --preview   # layout test without calling Claude
"""
import argparse
import shutil
import json
import logging
import os
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore", message=".*OpenSSL.*")  # harmless urllib3 notice on macOS Python

import yaml

import fetch
import markets
import web
from score import Story, max_words, score_all, thresholds

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "state.json"
MARKETS_FILE = ROOT / "state" / "markets.json"   # today's market prices and summaries (refreshed daily)
SITE_DIR = ROOT / "site"
ARCHIVE_DIR = ROOT / "state" / "archive"   # past briefings, carried between runs with the state
KEEP_SENT_DAYS = 7
MAX_LOOKBACK = timedelta(hours=36)

log = logging.getLogger("newsbot")


def load_env():
    """Read KEY=value lines from .env into the environment (existing variables win)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_run": None, "sent": {}, "seen": {}}


def save_state(state: dict, stories: List[Story], checked: List[str], now: datetime, alerts_today: dict):
    """`sent`: items shown on the page (their headlines feed dedupe). `seen`: every item already scored.
    `alerts_today`: {"date", "count"} of alerts shown today, for the daily alert cap."""
    cutoff = (now - timedelta(days=KEEP_SENT_DAYS)).isoformat()
    sent = {k: v for k, v in state["sent"].items() if v["at"] >= cutoff}
    seen = {k: v for k, v in state.get("seen", {}).items() if v >= cutoff}
    for s in stories:
        for item_id in s.item_ids:
            sent[item_id] = {"at": now.isoformat(), "headline": s.headline}
    seen.update({i: now.isoformat() for i in checked})
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_run": now.isoformat(), "sent": sent, "seen": seen,
                                      "alerts_today": alerts_today}, ensure_ascii=False, indent=1))


def stock_stories(interests: dict, sent: dict) -> List[Story]:
    topic = interests["topics"].get("big_tech", {})
    if not topic.get("watchlist"):
        return []
    alert_pct, digest_pct = topic.get("stock_alert_pct", 7), topic.get("stock_digest_pct", 3)
    stories = []
    for m in fetch.fetch_stock_moves(topic["watchlist"]):
        sid = f"stock:{m.ticker}:{m.date}"
        if abs(m.pct) < digest_pct or sid in sent:
            continue
        alert, digest = thresholds(interests)
        score = alert + 1 if abs(m.pct) >= alert_pct else digest + 1
        arrow = "▲" if m.pct > 0 else "▼"
        stories.append(Story(
            id=sid, topic="big_tech", score=score,
            headline=f"{m.ticker} {arrow} {m.pct:+.1f}% to ${m.close:,.2f}",
            summary=f"{m.ticker} closed {'up' if m.pct > 0 else 'down'} {abs(m.pct):.1f}% on {m.date}.",
            link=f"https://finance.yahoo.com/quote/{m.ticker}", sources=["Yahoo Finance"],
            published=None, item_ids=[sid],
        ))
    return stories


def fake_scores(items_by_topic: Dict[str, List[fetch.Item]], words: int) -> List[Story]:
    """Stand-in for Claude, for testing layout and delivery without an API key."""
    stories = []
    for topic, items in items_by_topic.items():
        for n, i in enumerate(items[:6]):
            summary = " ".join(i.summary.split()[:words]) or "(no summary)"
            stories.append(Story(i.id, topic, 9 if n == 0 and topic == "chelsea_fc" else 6, i.title,
                                 summary, i.link, [i.source], i.published, [i.id]))
    return stories


def arrange(stories: List[Story], interests: dict, alerts_so_far: int = 0):
    """Drop cross-topic duplicates, then split into capped alerts and a per-topic digest.
    `alerts_so_far`: alerts already shown today, which count towards `max_instant_per_day`."""
    alerts_cfg = interests["alerts"]
    alert_threshold, digest_threshold = thresholds(interests)
    if "max_instant_per_day" in alerts_cfg:
        cap = max(0, alerts_cfg["max_instant_per_day"] - alerts_so_far)
    else:
        cap = alerts_cfg.get("max_alerts_per_run", 5)
    page = interests["presentation"]["webpage"]
    per_section = page.get("items_per_section", 5)
    order = page.get("sections_order") or list(interests["topics"])
    order += [t for t in interests["topics"] if t not in order]

    kept, used = [], set()
    for s in sorted(stories, key=lambda s: -s.score):
        if not used.intersection(s.item_ids):
            kept.append(s)
            used.update(s.item_ids)

    alerts, overflow = [], []
    uncapped = set(alerts_cfg.get("never_capped", []))
    rank = {t: n for n, t in enumerate(order)}
    candidates = sorted((s for s in kept if s.score >= alert_threshold),
                        key=lambda s: (s.topic not in uncapped, -s.score, rank.get(s.topic, 99)))
    for s in candidates:
        if s.topic in uncapped or len(alerts) < cap:
            alerts.append(s)
        else:
            overflow.append(s)

    alert_ids = {s.id for s in alerts}
    digest = {}
    for topic in order:
        rest = [s for s in kept if s.topic == topic and s.id not in alert_ids
                and s.score >= digest_threshold]
        digest[topic] = sorted(rest, key=lambda s: -s.score)[:per_section]
    return alerts, digest


def load_feedback() -> dict:
    path = ROOT / "feedback.yaml"
    data = (yaml.safe_load(path.read_text()) if path.exists() else None) or {}
    return {k: data.get(k) or [] for k in ("muted_sources", "not_interested", "more_like_this", "starred")}


def briefing_title(interests: dict, local: datetime) -> str:
    """Morning title before 12:00, evening title from 12:00 (presentation.titles), plus the date."""
    part = "morning" if local.hour < 12 else "evening"
    titles = interests["presentation"].get("titles") or {}
    return f"{titles.get(part) or part.title() + ' briefing'} · {local:%a %d %b}"


def write_site(title: str, slug: str, now: datetime, alerts, digest, interests: dict, feedback: dict,
               market_rows: List[markets.MarketRow]):
    """Rebuild site/. With show_previous_briefings on, also archive this briefing and link the last 7 days."""
    repo = os.environ.get("GITHUB_REPOSITORY") or "winv-gpt/NewsAggregator"
    common = dict(repo=repo, markets=market_rows, starred=feedback["starred"])
    shutil.rmtree(SITE_DIR, ignore_errors=True)
    SITE_DIR.mkdir()
    if not interests["presentation"]["webpage"].get("show_previous_briefings", True):
        (SITE_DIR / "index.html").write_text(web.render(title, now, alerts, digest, interests,
                                                        muted=feedback["muted_sources"], **common))
        log.info("webpage written to %s", SITE_DIR / "index.html")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / f"{slug}.html").write_text(
        web.render(title, now, alerts, digest, interests, home="../", **common))
    cutoff = (now - timedelta(days=KEEP_SENT_DAYS)).strftime("%Y-%m-%d")
    for old in ARCHIVE_DIR.glob("*.html"):
        if old.stem < cutoff:
            old.unlink()

    earlier = []
    for f in sorted(ARCHIVE_DIR.glob("*.html"), reverse=True):
        if f.stem != slug:
            day, part = f.stem.rsplit("-", 1)
            earlier.append((f"{datetime.strptime(day, '%Y-%m-%d'):%a %d %b} · {part}", f"archive/{f.name}"))

    shutil.copytree(ARCHIVE_DIR, SITE_DIR / "archive")
    (SITE_DIR / "index.html").write_text(web.render(title, now, alerts, digest, interests, earlier=earlier,
                                                    muted=feedback["muted_sources"], **common))
    log.info("webpage written to %s (%d earlier briefings)", SITE_DIR / "index.html", len(earlier))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", action="store_true", help="build the page without updating the bot's memory")
    parser.add_argument("--fake-scores", action="store_true", help="skip Claude (layout testing only)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    load_env()
    interests = yaml.safe_load((ROOT / "interests.yaml").read_text())
    feeds = yaml.safe_load((ROOT / "feeds.yaml").read_text())
    state = load_state()
    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(interests["owner"]["timezone"]))

    since = datetime.fromisoformat(state["last_run"]) if state["last_run"] else now - timedelta(hours=24)
    since = max(since, now - MAX_LOOKBACK)
    log.info("collecting news since %s", since.astimezone(local.tzinfo).strftime("%a %H:%M"))

    feedback = load_feedback()
    muted = {m.casefold() for m in feedback["muted_sources"]}
    items_by_topic = fetch.fetch_all(interests, feeds, since)
    done = state["sent"].keys() | state.get("seen", {}).keys()
    for topic in items_by_topic:
        items_by_topic[topic] = [i for i in items_by_topic[topic]
                                 if i.id not in done and i.source.casefold() not in muted]

    recent = list(dict.fromkeys(v["headline"] for v in state["sent"].values()))[-150:]
    if args.fake_scores:
        stories, failed = fake_scores(items_by_topic, max_words(interests)), []
    else:
        stories, failed = score_all(interests, items_by_topic, recent, feedback)
    attempted = [t for t, items in items_by_topic.items() if items]
    if attempted and len(failed) == len(attempted):
        raise SystemExit("Claude could not score any topic (see errors above); page and memory left unchanged")
    if failed:
        log.warning("topics not scored this run, will retry next run: %s", ", ".join(failed))
    # Items from failed topics stay unmarked so the next run scores them again.
    checked = list({i.id for t, items in items_by_topic.items() if t not in failed for i in items})

    stories += stock_stories(interests, state["sent"])
    today = local.strftime("%Y-%m-%d")
    alerts_today = state.get("alerts_today") or {}
    so_far = alerts_today.get("count", 0) if alerts_today.get("date") == today else 0
    alerts, digest = arrange(stories, interests, so_far)
    shown = alerts + [s for ss in digest.values() for s in ss]
    log.info("%d alerts, %d digest stories", len(alerts), len(shown) - len(alerts))

    market_cache = json.loads(MARKETS_FILE.read_text()) if MARKETS_FILE.exists() else None
    market_rows, market_cache = markets.build(interests, market_cache, today, fake=args.fake_scores)

    part = "morning" if local.hour < 12 else "evening"
    write_site(briefing_title(interests, local), f"{today}-{part}",
               now, alerts, digest, interests, feedback, market_rows)
    if not args.preview:
        save_state(state, shown, checked, now, {"date": today, "count": so_far + len(alerts)})
        if market_cache:
            MARKETS_FILE.write_text(json.dumps(market_cache, ensure_ascii=False))


if __name__ == "__main__":
    main()

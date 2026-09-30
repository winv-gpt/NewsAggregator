"""News bot: fetch -> score with Claude -> Telegram + webpage. Run at each scheduled time.

    python run.py              # full run: sends to Telegram and remembers what was sent
    python run.py --no-send    # preview: builds the page and prints the Telegram text only
    python run.py --fake-scores --no-send   # layout test without calling Claude
"""
import argparse
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
import telegram
import web
from score import Story, score_all

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "state.json"
SITE_DIR = ROOT / "site"
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


def save_state(state: dict, stories: List[Story], checked: List[str], now: datetime):
    """`sent`: items delivered (their headlines feed dedupe). `seen`: every item already scored."""
    cutoff = (now - timedelta(days=KEEP_SENT_DAYS)).isoformat()
    sent = {k: v for k, v in state["sent"].items() if v["at"] >= cutoff}
    seen = {k: v for k, v in state.get("seen", {}).items() if v >= cutoff}
    for s in stories:
        for item_id in s.item_ids:
            sent[item_id] = {"at": now.isoformat(), "headline": s.headline}
    seen.update({i: now.isoformat() for i in checked})
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_run": now.isoformat(), "sent": sent, "seen": seen},
                                     ensure_ascii=False, indent=1))


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
        score = interests["alerts"]["alert_threshold"] + 1 if abs(m.pct) >= alert_pct else \
            interests["alerts"]["digest_threshold"] + 1
        arrow = "▲" if m.pct > 0 else "▼"
        stories.append(Story(
            id=sid, topic="big_tech", score=score,
            headline=f"{m.ticker} {arrow} {m.pct:+.1f}% to ${m.close:,.2f}",
            summary=f"{m.ticker} closed {'up' if m.pct > 0 else 'down'} {abs(m.pct):.1f}% on {m.date}.",
            link=f"https://finance.yahoo.com/quote/{m.ticker}", sources=["Yahoo Finance"],
            published=None, item_ids=[sid],
        ))
    return stories


def fake_scores(items_by_topic: Dict[str, List[fetch.Item]]) -> List[Story]:
    """Stand-in for Claude, for testing layout and delivery without an API key."""
    stories = []
    for topic, items in items_by_topic.items():
        for n, i in enumerate(items[:6]):
            stories.append(Story(i.id, topic, 9 if n == 0 and topic == "chelsea_fc" else 6, i.title,
                                 i.summary[:140] or "(no summary)", i.link, [i.source], i.published, [i.id]))
    return stories


def arrange(stories: List[Story], interests: dict):
    """Drop cross-topic duplicates, then split into capped alerts and a per-topic digest."""
    alerts_cfg = interests["alerts"]
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
    candidates = sorted((s for s in kept if s.score >= alerts_cfg["alert_threshold"]),
                        key=lambda s: (s.topic not in uncapped, -s.score, rank.get(s.topic, 99)))
    for s in candidates:
        if s.topic in uncapped or len(alerts) < alerts_cfg.get("max_alerts_per_run", 5):
            alerts.append(s)
        else:
            overflow.append(s)

    alert_ids = {s.id for s in alerts}
    digest = {}
    for topic in order:
        rest = [s for s in kept if s.topic == topic and s.id not in alert_ids
                and s.score >= alerts_cfg["digest_threshold"]]
        digest[topic] = sorted(rest, key=lambda s: -s.score)[:per_section]
    return alerts, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-send", action="store_true", help="don't send to Telegram or update state")
    parser.add_argument("--fake-scores", action="store_true", help="skip Claude (layout testing only)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    load_env()
    interests = yaml.safe_load((ROOT / "interests.yaml").read_text())
    feeds = yaml.safe_load((ROOT / "feeds.yaml").read_text())
    state = load_state()
    now = datetime.now(timezone.utc)

    since = datetime.fromisoformat(state["last_run"]) if state["last_run"] else now - timedelta(hours=24)
    since = max(since, now - MAX_LOOKBACK)
    log.info("collecting news since %s", since.astimezone(ZoneInfo(interests["owner"]["timezone"])).strftime("%a %H:%M"))

    items_by_topic = fetch.fetch_all(interests, feeds, since)
    done = state["sent"].keys() | state.get("seen", {}).keys()
    for topic in items_by_topic:
        items_by_topic[topic] = [i for i in items_by_topic[topic] if i.id not in done]
    checked = list({i.id for items in items_by_topic.values() for i in items})

    recent = list(dict.fromkeys(v["headline"] for v in state["sent"].values()))[-150:]
    stories = fake_scores(items_by_topic) if args.fake_scores else score_all(interests, items_by_topic, recent)
    stories += stock_stories(interests, state["sent"])
    alerts, digest = arrange(stories, interests)

    local = now.astimezone(ZoneInfo(interests["owner"]["timezone"]))
    title = f"{'Morning' if local.hour < 12 else 'Evening'} briefing · {local:%a %d %b}"

    SITE_DIR.mkdir(exist_ok=True)
    page = web.render(title, now, alerts, digest, interests)
    (SITE_DIR / "index.html").write_text(page)
    log.info("webpage written to %s", SITE_DIR / "index.html")

    messages = telegram.format_briefing(title, alerts, digest, os.environ.get("NEWSBOT_PAGE_URL"))
    delivered = alerts + [s for ss in digest.values() for s in ss]
    log.info("%d alerts, %d digest stories, %d Telegram message(s)",
             len(alerts), len(delivered) - len(alerts), len(messages))

    if args.no_send:
        print("\n" + "\n\n---\n\n".join(messages))
        return
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set (see .env.example)")
    if telegram.send(token, chat, messages):
        save_state(state, delivered, checked, now)
    else:
        raise SystemExit("Telegram delivery failed; state not updated so the next run retries")


if __name__ == "__main__":
    main()

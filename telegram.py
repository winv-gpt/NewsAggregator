"""Format the briefing and send it to Telegram."""
import html
import logging
from typing import Dict, List, Optional

import requests

from score import Story

log = logging.getLogger(__name__)

LIMIT = 4000  # Telegram's hard cap is 4096 characters per message

TOPIC_LABELS = {
    "chelsea_fc": "⚽ Chelsea",
    "premier_league": "🏟 Premier League",
    "big_tech": "💻 Big Tech",
    "global_payments": "💳 Payments",
    "thailand_headlines": "🇹🇭 Thailand",
    "thai_politics": "🏛 Thai politics",
    "global_news": "🌍 World",
    "ironman": "🏊 IRONMAN",
}


def label(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title())


def _line(story: Story, with_topic: bool = False) -> str:
    e = html.escape
    prefix = f"<b>{e(label(story.topic))}</b> · " if with_topic else ""
    head = f'<a href="{e(story.link, quote=True)}">{e(story.headline)}</a>'
    return f"• {prefix}{head}\n  {e(story.summary)} <i>({e(', '.join(story.sources[:2]))})</i>"


def format_briefing(title: str, alerts: List[Story], digest: Dict[str, List[Story]],
                    page_url: Optional[str]) -> List[str]:
    """Return the briefing as one or more Telegram-sized HTML messages."""
    blocks = [f"<b>{html.escape(title)}</b>"]
    if alerts:
        blocks.append("🚨 <b>Alerts</b>\n" + "\n".join(_line(s, with_topic=True) for s in alerts))
    for topic, stories in digest.items():
        if stories:
            blocks.append(f"<b>{html.escape(label(topic))}</b>\n" + "\n".join(_line(s) for s in stories))
    if not alerts and not any(digest.values()):
        blocks.append("Nothing worth your time since the last briefing.")
    if page_url:
        blocks.append(f'🔗 <a href="{html.escape(page_url, quote=True)}">Open the full page</a>')

    messages, current = [], ""
    for block in blocks:
        for piece in _split(block):
            if current and len(current) + len(piece) + 2 > LIMIT:
                messages.append(current)
                current = ""
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        messages.append(current)
    return messages


def _split(block: str) -> List[str]:
    """Split an oversized block on bullet boundaries so no piece exceeds LIMIT."""
    if len(block) <= LIMIT:
        return [block]
    pieces, current = [], ""
    for line in block.split("\n• "):
        line = line if not pieces and not current else "• " + line
        if current and len(current) + len(line) + 1 > LIMIT:
            pieces.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    return pieces + [current]


def send(token: str, chat_id: str, messages: List[str]) -> bool:
    ok = True
    for text in messages:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "link_preview_options": {"is_disabled": True}},
            timeout=20,
        )
        if not resp.ok:
            log.error("Telegram send failed (%s): %s", resp.status_code, resp.text[:300])
            ok = False
    return ok

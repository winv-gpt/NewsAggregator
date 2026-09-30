"""Render the briefing as a static, phone-friendly webpage."""
import html
from datetime import datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from score import Story
from telegram import label

CSS = """
:root { --bg:#f6f5f2; --card:#fff; --text:#1c1c1e; --muted:#6b6b70; --line:#e4e2dc;
        --accent:#034694; --alert:#c0392b; --alert-bg:#fdf0ee; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111214; --card:#1c1d20; --text:#ececef; --muted:#9a9aa2; --line:#2c2d31;
          --accent:#6ea8ff; --alert:#ff7b6b; --alert-bg:#2a1c1a; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font:16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 48px; }
header h1 { font-size:26px; margin:0 0 2px; letter-spacing:-.01em; }
header p { margin:0 0 20px; color:var(--muted); font-size:14px; }
h2 { font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
     margin:28px 0 10px; }
.grid { display:grid; gap:12px; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); }
.list { display:flex; flex-direction:column; gap:8px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px;
        display:flex; flex-direction:column; gap:6px; }
.card.alert { border-color:var(--alert); background:var(--alert-bg); }
.card a { color:var(--text); text-decoration:none; font-weight:600; font-size:16.5px; line-height:1.3; }
.card a:hover { color:var(--accent); }
.card p { margin:0; font-size:14.5px; }
.meta { color:var(--muted); font-size:12.5px; display:flex; gap:8px; flex-wrap:wrap; }
.tag { color:var(--alert); font-weight:600; }
.empty { color:var(--muted); }
"""


def _card(story: Story, tz: ZoneInfo, alert_threshold: int, show: List[str], with_topic=False) -> str:
    e = html.escape
    is_alert = story.score >= alert_threshold
    meta = []
    if with_topic:
        meta.append(f'<span class="tag">{e(label(story.topic))}</span>')
    elif is_alert:
        meta.append('<span class="tag">Alert</span>')
    if "source" in show:
        meta.append(e(", ".join(story.sources[:3])))
    if "time" in show and story.published:
        meta.append(story.published.astimezone(tz).strftime("%a %H:%M"))
    parts = [f'<a href="{e(story.link, quote=True)}" target="_blank" rel="noopener">{e(story.headline)}</a>']
    if "summary" in show:
        parts.append(f"<p>{e(story.summary)}</p>")
    parts.append(f'<div class="meta">{" · ".join(meta)}</div>')
    return f'<article class="card{" alert" if is_alert else ""}">{"".join(parts)}</article>'


def render(title: str, generated: datetime, alerts: List[Story], digest: Dict[str, List[Story]],
           interests: dict) -> str:
    tz = ZoneInfo(interests["owner"]["timezone"])
    page = interests["presentation"]["webpage"]
    show = page.get("show", ["headline", "summary", "source", "time"])
    threshold = interests["alerts"]["alert_threshold"]
    container = "grid" if page.get("layout", "cards") == "cards" else "list"

    sections = []
    if alerts:
        cards = "".join(_card(s, tz, threshold, show, with_topic=True) for s in alerts)
        sections.append(f'<h2>🚨 Alerts</h2><div class="{container}">{cards}</div>')
    for topic, stories in digest.items():
        if stories:
            cards = "".join(_card(s, tz, threshold, show) for s in stories)
            sections.append(f'<h2>{html.escape(label(topic))}</h2><div class="{container}">{cards}</div>')
    if not sections:
        sections.append('<p class="empty">Nothing worth your time since the last briefing.</p>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<header><h1>{html.escape(title)}</h1>
<p>Updated {generated.astimezone(tz).strftime("%A %d %B, %H:%M")} ({interests["owner"]["timezone"]})</p></header>
{"".join(sections)}
</main></body></html>
"""

"""Render the briefing as a static, phone-friendly webpage."""
import html
import json
from datetime import datetime
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from score import Story

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

CSS = """
:root { --bg:#f6f5f2; --card:#fff; --text:#1c1c1e; --muted:#6b6b70; --line:#e4e2dc;
        --accent:#034694; --alert:#c0392b; --alert-bg:#fdf0ee; --bar:#1c1c1e; --bar-text:#fff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111214; --card:#1c1d20; --text:#ececef; --muted:#9a9aa2; --line:#2c2d31;
          --accent:#6ea8ff; --alert:#ff7b6b; --alert-bg:#2a1c1a; --bar:#ececef; --bar-text:#111214; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font:16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 96px; }
header h1 { font-size:26px; margin:0 0 2px; letter-spacing:-.01em; }
header p { margin:0 0 20px; color:var(--muted); font-size:14px; }
h2 { font-size:15px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
     margin:28px 0 10px; }
.grid { display:grid; gap:12px; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); }
.list { display:flex; flex-direction:column; gap:8px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px;
        display:flex; flex-direction:column; gap:6px; transition:opacity .2s; }
.card.alert { border-color:var(--alert); background:var(--alert-bg); }
.card.dim { opacity:.4; }
.card a { color:var(--text); text-decoration:none; font-weight:600; font-size:16.5px; line-height:1.3; }
.card a:hover { color:var(--accent); }
.card p { margin:0; font-size:14.5px; }
.meta { color:var(--muted); font-size:12.5px; display:flex; gap:8px; flex-wrap:wrap; }
.tag { color:var(--alert); font-weight:600; }
.fb { display:flex; gap:16px; flex-wrap:wrap; margin-top:4px; padding-top:8px; border-top:1px solid var(--line);
      font-size:13px; color:var(--muted); }
.fb label { display:flex; align-items:center; gap:6px; cursor:pointer; min-height:28px; }
.fb input { width:17px; height:17px; margin:0; accent-color:var(--accent); }
.empty { color:var(--muted); }
header nav a, footer a { color:var(--accent); text-decoration:none; font-size:14px; }
footer { margin-top:36px; padding-top:16px; border-top:1px solid var(--line); }
footer ul { list-style:none; padding:0; margin:8px 0 0; display:flex; flex-direction:column; gap:6px; }
footer .fb { border:0; padding:0; }
#bar { position:fixed; left:50%; bottom:16px; transform:translateX(-50%); display:none; align-items:center;
       gap:14px; background:var(--bar); color:var(--bar-text); padding:10px 12px 10px 18px; border-radius:999px;
       box-shadow:0 6px 24px rgba(0,0,0,.25); font-size:14px; max-width:calc(100% - 32px); }
#bar.show { display:flex; }
#count { white-space:nowrap; }
#bar.done button { display:none; }
#bar button { border:0; border-radius:999px; padding:8px 14px; font:inherit; font-weight:600; cursor:pointer;
              background:var(--accent); color:#fff; white-space:nowrap; }
#bar button.ghost { background:transparent; color:inherit; opacity:.7; padding:8px 6px; }
"""

# Collects ticks locally, then opens a pre-filled GitHub issue; the feedback workflow applies it.
JS = """
const REPO = %(repo)s;
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};
let pending = store.get("newsbot-pending", {mute: [], unmute: [], meh: []});
const muted = new Set(store.get("newsbot-muted", []));

function cardsFor(source) { return document.querySelectorAll(`.card[data-source="${CSS.escape(source)}"]`); }

function refresh() {
  document.querySelectorAll(".card").forEach(card => {
    const src = card.dataset.source, head = card.dataset.headline;
    const m = card.querySelector('[data-kind="mute"]'), n = card.querySelector('[data-kind="meh"]');
    m.checked = pending.mute.includes(src);
    n.checked = pending.meh.some(x => x.headline === head);
    card.classList.toggle("dim", m.checked || n.checked);
    card.hidden = muted.has(src) && !pending.unmute.includes(src);
  });
  document.querySelectorAll('[data-kind="unmute"]').forEach(b => { b.checked = pending.unmute.includes(b.dataset.source); });
  const count = pending.mute.length + pending.unmute.length + pending.meh.length;
  document.getElementById("count").textContent = count === 1 ? "1 change" : count + " changes";
  document.getElementById("bar").classList.toggle("show", count > 0);
  store.set("newsbot-pending", pending);
}

document.addEventListener("change", e => {
  const box = e.target, kind = box.dataset.kind;
  if (!kind) return;
  const card = box.closest(".card");
  if (kind === "mute") {
    const src = card.dataset.source;
    pending.mute = pending.mute.filter(s => s !== src);
    if (box.checked) pending.mute.push(src);
  } else if (kind === "meh") {
    const item = {topic: card.dataset.topic, headline: card.dataset.headline, source: card.dataset.source};
    pending.meh = pending.meh.filter(x => x.headline !== item.headline);
    if (box.checked) pending.meh.push(item);
  } else if (kind === "unmute") {
    const src = box.dataset.source;
    pending.unmute = pending.unmute.filter(s => s !== src);
    if (box.checked) pending.unmute.push(src);
  }
  refresh();
});

document.getElementById("save").addEventListener("click", () => {
  const data = {mute_sources: pending.mute, unmute_sources: pending.unmute, not_interested: pending.meh};
  const parts = [];
  if (data.mute_sources.length) parts.push("mute " + data.mute_sources.join(", "));
  if (data.unmute_sources.length) parts.push("unmute " + data.unmute_sources.join(", "));
  if (data.not_interested.length) parts.push(data.not_interested.length + " not interested");
  const title = "Newsbot feedback: " + parts.join("; ");
  const body = "Tap **Create** to save this feedback. It applies from the next briefing.\\n\\n" +
               "```json\\n" + JSON.stringify(data, null, 1) + "\\n```";
  window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, "_blank");
  pending.mute.forEach(s => muted.add(s));
  pending.unmute.forEach(s => muted.delete(s));
  store.set("newsbot-muted", [...muted]);
  pending = {mute: [], unmute: [], meh: []};
  refresh();
  const bar = document.getElementById("bar");
  bar.classList.add("show", "done");
  document.getElementById("count").textContent = "Opened GitHub: tap Create to save";
  setTimeout(() => { bar.classList.remove("done"); refresh(); }, 6000);
});
document.getElementById("clear").addEventListener("click", () => { pending = {mute: [], unmute: [], meh: []}; refresh(); });
refresh();
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
    source = story.sources[0]
    parts.append(
        '<div class="fb">'
        f'<label><input type="checkbox" data-kind="mute"> Mute {e(source)}</label>'
        '<label><input type="checkbox" data-kind="meh"> Not interested</label></div>')
    attrs = (f'data-topic="{e(story.topic, quote=True)}" data-source="{e(source, quote=True)}" '
             f'data-headline="{e(story.headline, quote=True)}"')
    return f'<article class="card{" alert" if is_alert else ""}" {attrs}>{"".join(parts)}</article>'


def render(title: str, generated: datetime, alerts: List[Story], digest: Dict[str, List[Story]],
           interests: dict, earlier: List[Tuple[str, str]] = (), home: str = "",
           repo: str = "", muted: List[str] = ()) -> str:
    """`earlier`: (label, href) links to previous briefings. `home`: link back to the latest one.
    `repo`: owner/name that receives feedback issues. `muted`: currently muted sources."""
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

    script = JS % {"repo": json.dumps(repo)}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<header><h1>{html.escape(title)}</h1>
<p>Updated {generated.astimezone(tz).strftime("%A %d %B, %H:%M")} ({interests["owner"]["timezone"]})</p>
{f'<nav><a href="{home}">← Latest briefing</a></nav>' if home else ""}</header>
{"".join(sections)}
{_muted(muted)}
{_earlier(earlier)}
</main>
<div id="bar" role="status"><span id="count"></span>
<button id="clear" class="ghost" type="button">Clear</button>
<button id="save" type="button">Save to bot ↗</button></div>
<script>{script}</script>
</body></html>
"""


def _muted(sources: List[str]) -> str:
    if not sources:
        return ""
    items = "".join(f'<li class="fb"><label><input type="checkbox" data-kind="unmute" '
                    f'data-source="{html.escape(s, quote=True)}"> Unmute {html.escape(s)}</label></li>'
                    for s in sources)
    return f"<footer><h2>Muted sources</h2><ul>{items}</ul></footer>"


def _earlier(links: List[Tuple[str, str]]) -> str:
    if not links:
        return ""
    items = "".join(f'<li><a href="{html.escape(href, quote=True)}">{html.escape(text)}</a></li>'
                    for text, href in links)
    return f"<footer><h2>Earlier briefings</h2><ul>{items}</ul></footer>"

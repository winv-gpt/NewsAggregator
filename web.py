"""Render the briefing as a static, phone-friendly webpage."""
import html
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from markets import QUARTER_DAYS, Instrument, MarketRow
from score import Story, thresholds

TOPIC_LABELS = {
    "chelsea_fc": "⚽ Chelsea",
    "premier_league": "🏟 Premier League",
    "big_tech": "💻 Big Tech",
    "global_payments": "💳 Payments",
    "thailand_headlines": "🇹🇭 Thailand",
    "thai_politics": "🏛 Thai politics",
    "global_news": "🌍 World",
    "ironman": "🏊 IRONMAN",
    "markets": "📈 Markets",
}

# Which page action each feedback button in interests.yaml (presentation.feedback_buttons) performs.
FEEDBACK_KINDS = {"👍": "like", "👎": "meh"}
DEFAULT_BUTTONS = [{"label": "👍", "meaning": "more like this"}, {"label": "👎", "meaning": "less like this"}]


def label(topic: str) -> str:
    return TOPIC_LABELS.get(topic, topic.replace("_", " ").title())

CSS = """
:root { --bg:#f6f5f2; --card:#fff; --text:#1c1c1e; --muted:#6b6b70; --line:#e4e2dc;
        --accent:#034694; --alert:#c0392b; --alert-bg:#fdf0ee; --bar:#1c1c1e; --bar-text:#fff;
        --chip-on:#e6eefa; --band:#efeee9; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111214; --card:#1c1d20; --text:#ececef; --muted:#9a9aa2; --line:#2c2d31;
          --accent:#6ea8ff; --alert:#ff7b6b; --alert-bg:#2a1c1a; --bar:#ececef; --bar-text:#111214;
          --chip-on:#1e2a3d; --band:#25262a; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text);
       font:16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 96px; }
header { display:flex; flex-wrap:wrap; align-items:flex-start; justify-content:space-between; gap:12px; }
header h1 { font-size:26px; margin:0 0 2px; letter-spacing:-.01em; }
header p { margin:0 0 20px; color:var(--muted); font-size:14px; }
.fetch { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); background:var(--card);
         color:var(--accent); border-radius:999px; padding:8px 14px; font-size:14px; font-weight:600;
         text-decoration:none; white-space:nowrap; }
.fetch:hover { border-color:var(--accent); }
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
.fb { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:4px; padding-top:8px;
      border-top:1px solid var(--line); font-size:13px; color:var(--muted); }
.fb label { display:flex; align-items:center; gap:6px; cursor:pointer; min-height:32px; }
.fb input { width:17px; height:17px; margin:0; accent-color:var(--accent); }
.fb .chip { position:relative; min-width:40px; justify-content:center; border:1px solid var(--line); border-radius:999px;
            padding:0 10px; font-size:16px; }
.fb .chip input { position:absolute; opacity:0; pointer-events:none; }
.fb .chip:has(input:checked) { background:var(--chip-on); border-color:var(--accent); }
.fb .chip:has(input:focus-visible) { outline:2px solid var(--accent); outline-offset:2px; }
.empty { color:var(--muted); }
header nav a, footer a { color:var(--accent); text-decoration:none; font-size:14px; }
footer { margin-top:36px; padding-top:16px; border-top:1px solid var(--line); }
footer ul { list-style:none; padding:0; margin:8px 0 0; display:flex; flex-direction:column; gap:6px; }
.market { gap:8px; }
.market .name { font-weight:600; font-size:16px; }
.stats { display:flex; flex-wrap:wrap; gap:4px 14px; font-size:13px; color:var(--muted); }
.stats b { color:var(--text); font-weight:600; font-variant-numeric:tabular-nums; }
.chart { position:relative; margin-top:30px; }   /* room for the hover label above the line */
.chart svg { display:block; width:100%; height:96px; overflow:visible; touch-action:pan-y; }
.chart .line { fill:none; stroke:var(--accent); stroke-width:2; stroke-linejoin:round; stroke-linecap:round;
               vector-effect:non-scaling-stroke; }
.chart .area { fill:var(--accent); opacity:.1; }
.chart .band { fill:var(--band); }
.chart .base { stroke:var(--line); stroke-width:1; vector-effect:non-scaling-stroke; }
.chart .cross { stroke:var(--muted); stroke-width:1; vector-effect:non-scaling-stroke; visibility:hidden; }
.chart .dot { position:absolute; width:8px; height:8px; margin:-4px 0 0 -4px; border-radius:50%;
              background:var(--accent); box-shadow:0 0 0 2px var(--card); pointer-events:none; }
.chart .dot.hover { visibility:hidden; }
.chart .tip { position:absolute; top:-6px; transform:translate(-50%,-100%); background:var(--bar);
              color:var(--bar-text); font-size:12px; padding:3px 8px; border-radius:6px; white-space:nowrap;
              pointer-events:none; visibility:hidden; font-variant-numeric:tabular-nums; }
.axis { display:flex; justify-content:space-between; font-size:11.5px; color:var(--muted); }
.drivers { font-size:14px; }
.drivers .src { color:var(--muted); font-size:12.5px; }
.drivers .src a { font-size:12.5px; font-weight:400; color:var(--accent); }
.movers { display:flex; flex-wrap:wrap; gap:8px; }
.mover { border:1px solid var(--line); border-radius:8px; padding:6px 10px; font-size:13px; }
.mover b { display:block; font-size:14px; }
.mover span { color:var(--muted); font-variant-numeric:tabular-nums; }
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
const EMPTY = () => ({meh: [], like: []});
const saved = store.get("newsbot-pending", {});
let pending = {meh: saved.meh || [], like: saved.like || []};
const KINDS = ["meh", "like"];

function refresh() {
  document.querySelectorAll(".card[data-headline]").forEach(card => {
    const head = card.dataset.headline;
    KINDS.forEach(k => {
      const box = card.querySelector(`[data-kind="${k}"]`);
      if (box) box.checked = pending[k].some(x => x.headline === head);
    });
    const meh = card.querySelector('[data-kind="meh"]');
    card.classList.toggle("dim", !!(meh && meh.checked));
  });
  const count = KINDS.reduce((n, k) => n + pending[k].length, 0);
  document.getElementById("count").textContent = count === 1 ? "1 change" : count + " changes";
  document.getElementById("bar").classList.toggle("show", count > 0);
  store.set("newsbot-pending", pending);
}

document.addEventListener("change", e => {
  const box = e.target, kind = box.dataset.kind;
  if (!kind) return;
  const card = box.closest(".card");
  const item = {topic: card.dataset.topic, headline: card.dataset.headline, source: card.dataset.source};
  pending[kind] = pending[kind].filter(x => x.headline !== item.headline);
  if (box.checked) {
    pending[kind].push(item);
    const other = {like: "meh", meh: "like"}[kind];   // 👍 and 👎 cancel each other out
    pending[other] = pending[other].filter(x => x.headline !== item.headline);
  }
  refresh();
});

document.getElementById("save").addEventListener("click", () => {
  const data = {not_interested: pending.meh, more_like_this: pending.like};
  const parts = [];
  if (data.more_like_this.length) parts.push(data.more_like_this.length + " 👍");
  if (data.not_interested.length) parts.push(data.not_interested.length + " 👎");
  const title = "Newsbot feedback: " + parts.join("; ");
  const body = "Tap **Create** to save this feedback. It applies from the next briefing.\\n\\n" +
               "```json\\n" + JSON.stringify(data, null, 1) + "\\n```";
  window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, "_blank");
  pending = EMPTY();
  refresh();
  const bar = document.getElementById("bar");
  bar.classList.add("show", "done");
  document.getElementById("count").textContent = "Opened GitHub: tap Create to save";
  setTimeout(() => { bar.classList.remove("done"); refresh(); }, 6000);
});
document.getElementById("clear").addEventListener("click", () => { pending = EMPTY(); refresh(); });
refresh();

// Market charts: a crosshair that snaps to the nearest day, with that day's close.
document.querySelectorAll(".chart").forEach(chart => {
  const svg = chart.querySelector("svg"), cross = chart.querySelector(".cross");
  const dot = chart.querySelector(".dot.hover"), tip = chart.querySelector(".tip");
  const pts = JSON.parse(chart.dataset.points), [lo, hi] = JSON.parse(chart.dataset.range);
  const unit = chart.dataset.unit;
  const fmt = v => (Math.abs(v) >= 1000 ? v.toLocaleString("en-US", {maximumFractionDigits: 0})
                    : v.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2})) + unit;
  function show(clientX) {
    const r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(pts.length - 1, Math.round((clientX - r.left) / r.width * (pts.length - 1))));
    const x = i / (pts.length - 1) * r.width, y = (1 - (pts[i][1] - lo) / (hi - lo || 1)) * 80 / 90 * r.height + 5 / 90 * r.height;
    cross.setAttribute("x1", i); cross.setAttribute("x2", i); cross.style.visibility = "visible";
    dot.style.left = x + "px"; dot.style.top = y + "px"; dot.style.visibility = "visible";
    const d = new Date(pts[i][0] + "T00:00:00Z");
    tip.textContent = d.toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}) + " · " + fmt(pts[i][1]);
    tip.style.left = Math.max(60, Math.min(r.width - 60, x)) + "px"; tip.style.visibility = "visible";
  }
  function hide() { [cross, dot, tip].forEach(el => el.style.visibility = "hidden"); }
  svg.addEventListener("pointermove", e => show(e.clientX));
  svg.addEventListener("pointerdown", e => show(e.clientX));
  svg.addEventListener("pointerleave", hide);
});
"""


def _feedback_controls(buttons: List[dict]) -> str:
    e = html.escape
    chips = []
    for b in buttons:
        kind = FEEDBACK_KINDS.get(str(b.get("label", "")).strip())
        if kind:
            meaning = e(str(b.get("meaning", "")), quote=True)
            chips.append(f'<label class="chip" title="{meaning}"><input type="checkbox" data-kind="{kind}" '
                         f'aria-label="{meaning}">{e(b["label"])}</label>')
    return f'<div class="fb">{"".join(chips)}</div>' if chips else ""


def _card(story: Story, tz: ZoneInfo, alert_threshold: int, show: List[str], buttons: List[dict],
          with_topic=False) -> str:
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
    if controls := _feedback_controls(buttons):
        parts.append(controls)
    attrs = (f'data-topic="{e(story.topic, quote=True)}" data-source="{e(source, quote=True)}" '
             f'data-headline="{e(story.headline, quote=True)}"')
    return f'<article class="card{" alert" if is_alert else ""}" {attrs}>{"".join(parts)}</article>'


def _value(inst: Instrument, v: float) -> str:
    if inst.is_yield:
        return f"{v:.2f}%"
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"


def _change(inst: Instrument, days: int) -> str:
    c = inst.change(days)
    if c is None:
        return "–"
    arrow = "▲" if c > 0 else "▼" if c < 0 else ""
    return f"{arrow}{abs(c):.2f} pts" if inst.is_yield else f"{arrow}{abs(c):.1f}%"


def _chart(inst: Instrument) -> str:
    """12-month line in a 0..n-1 by 0..90 box (stretched to the card's width); last quarter shaded."""
    pts = inst.points
    n = len(pts) - 1
    lo, hi = min(c for _, c in pts), max(c for _, c in pts)
    y = lambda c: 5 + (1 - (c - lo) / ((hi - lo) or 1)) * 80
    line = " ".join(f"{i},{y(c):.2f}" for i, (_, c) in enumerate(pts))
    quarter_start = (date.fromisoformat(pts[-1][0]) - timedelta(days=QUARTER_DAYS)).isoformat()
    q = next((i for i, (d, _) in enumerate(pts) if d > quarter_start), n)
    end_x, end_y = 100.0, y(pts[-1][1]) / 90 * 100   # end dot, as % of the box
    unit = "%" if inst.is_yield else ""
    first = date.fromisoformat(pts[0][0])
    return (
        f'<div class="chart" data-points="{html.escape(json.dumps(pts), quote=True)}" '
        f'data-range="{json.dumps([lo, hi])}" data-unit="{unit}">'
        f'<svg viewBox="0 0 {n} 90" preserveAspectRatio="none" role="img" '
        f'aria-label="{html.escape(inst.name, quote=True)}, past 12 months">'
        f'<rect class="band" x="{q}" y="0" width="{n - q}" height="90"/>'
        f'<path class="area" d="M0,90 L{line} L{n},90 Z"/>'
        f'<line class="base" x1="0" x2="{n}" y1="90" y2="90"/>'
        f'<polyline class="line" points="{line}"/>'
        f'<line class="cross" x1="0" x2="0" y1="0" y2="90"/></svg>'
        f'<span class="dot" style="left:{end_x}%;top:{end_y:.1f}%"></span>'
        f'<span class="dot hover"></span><span class="tip"></span></div>'
        f'<div class="axis"><span>{first:%b %Y}</span><span>past quarter shaded</span>'
        f'<span>{date.fromisoformat(pts[-1][0]):%d %b}</span></div>')


def _drivers(row: MarketRow) -> str:
    if not row.summary:
        return ""
    links = ", ".join(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">'
                      f'{html.escape(src)}</a>' for src, url in row.links)
    return (f'<p class="drivers"><b>Past quarter:</b> {html.escape(row.summary)}'
            + (f' <span class="src">({links})</span>' if links else "") + "</p>")


def _market_card(row: MarketRow) -> str:
    e = html.escape
    if row.group:
        movers = "".join(
            f'<div class="mover"><b>{e(i.name)}</b><span>3 mo {_change(i, QUARTER_DAYS)} · '
            f'12 mo {_change(i, 365)}</span></div>' if len(i.points) >= 2 else
            f'<div class="mover"><b>{e(i.name)}</b><span>no price data</span></div>' for i in row.instruments)
        return (f'<article class="card market"><div class="name">{e(row.name)}</div>'
                f'<div class="movers">{movers}</div>{_drivers(row)}</article>')
    inst = row.instruments[0]
    if len(inst.points) < 2:   # keep the card, so a missing market is visible rather than silently dropped
        return (f'<article class="card market"><div class="name">{e(row.name)}</div>'
                f'<p class="empty">No price data from Yahoo Finance right now ({e(inst.symbol)}).</p>'
                f'{_drivers(row)}</article>')
    stats = (f'<b>{_value(inst, inst.last)}</b><span>1 day {_change(inst, 1)}</span>'
             f'<span>3 mo {_change(inst, QUARTER_DAYS)}</span><span>12 mo {_change(inst, 365)}</span>')
    return (f'<article class="card market"><div class="name">{e(row.name)}</div>'
            f'<div class="stats">{stats}</div>{_chart(inst)}{_drivers(row)}</article>')


def _markets(rows: List[MarketRow], container: str) -> str:
    if not rows:
        return ""
    if any(len(i.points) >= 2 for r in rows for i in r.instruments):
        body = f'<div class="{container}">{"".join(_market_card(r) for r in rows)}</div>'
    else:
        body = '<p class="empty">Market data is unavailable right now.</p>'
    return f'<h2>{html.escape(label("markets"))}</h2>{body}'


def render(title: str, generated: datetime, alerts: List[Story], digest: Dict[str, List[Story]],
           interests: dict, earlier: List[Tuple[str, str]] = (), home: str = "",
           repo: str = "", markets: Optional[List[MarketRow]] = None) -> str:
    """`earlier`: (label, href) links to previous briefings. `home`: link back to the latest one.
    `repo`: owner/name that receives feedback issues and runs the bot. `markets`: rows for the Markets section."""
    tz = ZoneInfo(interests["owner"]["timezone"])
    presentation = interests["presentation"]
    page = presentation["webpage"]
    show = page.get("show", ["headline", "summary", "source", "time"])
    buttons = presentation.get("feedback_buttons") or DEFAULT_BUTTONS
    threshold = thresholds(interests)[0]
    container = "grid" if page.get("layout", "cards") == "cards" else "list"

    sections = []
    if alerts:
        cards = "".join(_card(s, tz, threshold, show, buttons, with_topic=True) for s in alerts)
        sections.append(f'<h2>🚨 Alerts</h2><div class="{container}">{cards}</div>')
    order = list(digest)
    if "markets" not in order:
        order.append("markets")
    has_news = bool(alerts)
    for topic in order:
        if topic == "markets":
            sections.append(_markets(markets or [], container))
        elif digest.get(topic):
            has_news = True
            cards = "".join(_card(s, tz, threshold, show, buttons) for s in digest[topic])
            sections.append(f'<h2>{html.escape(label(topic))}</h2><div class="{container}">{cards}</div>')
    if not has_news:
        sections.insert(0, '<p class="empty">No new stories worth your time since the last briefing.</p>')

    fetch_now = ""
    if page.get("fetch_now_button") and repo:
        # GitHub can't be triggered from a static page without a token, so this opens the workflow's
        # page, where "Run workflow" starts a fresh briefing (ready in about 2-3 minutes).
        url = f"https://github.com/{repo}/actions/workflows/newsbot.yml"
        fetch_now = (f'<a class="fetch" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener" '
                     f'title="Opens GitHub: tap Run workflow, then reload this page in about 3 minutes">'
                     f'↻ Fetch now</a>')

    script = JS % {"repo": json.dumps(repo)}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<header><div><h1>{html.escape(title)}</h1>
<p>Updated {generated.astimezone(tz).strftime("%A %d %B, %H:%M")} ({interests["owner"]["timezone"]})</p>
{f'<nav><a href="{home}">← Latest briefing</a></nav>' if home else ""}</div>{fetch_now}</header>
{"".join(sections)}
{_earlier(earlier)}
</main>
<div id="bar" role="status"><span id="count"></span>
<button id="clear" class="ghost" type="button">Clear</button>
<button id="save" type="button">Save to bot ↗</button></div>
<script>{script}</script>
</body></html>
"""


def _earlier(links: List[Tuple[str, str]]) -> str:
    if not links:
        return ""
    items = "".join(f'<li><a href="{html.escape(href, quote=True)}">{html.escape(text)}</a></li>'
                    for text, href in links)
    return f"<footer><h2>Earlier briefings</h2><ul>{items}</ul></footer>"

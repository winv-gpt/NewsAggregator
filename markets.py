"""Markets section: 12-month prices from Yahoo Finance, plus a short Claude summary of what drove
each move over the past quarter, written only from news headlines (with links)."""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import anthropic

import fetch
from score import EFFORT, MODEL, make_client

log = logging.getLogger(__name__)

QUARTER_DAYS = 91
NEWS_PER_ROW = 20
YIELDS = {"^TNX", "^TYX", "^FVX", "^IRX"}   # quoted in %, so moves are shown in percentage points

SYSTEM = """You write the Markets section of a personal news briefing for {name}.
For each market below you get its price move over the {period} and recent news headlines (with ids).

For each market, write at most {max_words} words explaining the main drivers of that move.
Rules: {rules}
Use only the headlines given. If they don't explain the move, say the news doesn't show a clear driver.
List the ids of the headlines you relied on (1-3) in source_ids."""

SCHEMA = {
    "type": "object",
    "properties": {
        "markets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "summary", "source_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["markets"],
    "additionalProperties": False,
}


@dataclass
class Instrument:
    name: str
    symbol: str
    points: List[Tuple[str, float]] = field(default_factory=list)   # (YYYY-MM-DD, close), oldest first

    @property
    def is_yield(self) -> bool:
        return self.symbol in YIELDS

    @property
    def last(self) -> Optional[float]:
        return self.points[-1][1] if self.points else None

    def change(self, days: int) -> Optional[float]:
        """% change (points for yields) from the last close at least `days` ago to the latest close."""
        if len(self.points) < 2:
            return None
        cutoff = (date.fromisoformat(self.points[-1][0]) - timedelta(days=days)).isoformat()
        before = [c for d, c in self.points if d <= cutoff]
        start = before[-1] if before else self.points[0][1]
        return self.last - start if self.is_yield else (self.last / start - 1) * 100


@dataclass
class MarketRow:
    name: str
    instruments: List[Instrument]
    group: bool = False                  # a group is one compact row of stocks, without a chart
    summary: str = ""
    links: List[Tuple[str, str]] = field(default_factory=list)   # (source, url) behind the summary


def _rows(cfg: dict) -> List[MarketRow]:
    rows = []
    for entry in cfg.get("instruments") or []:
        if entry.get("group"):
            rows.append(MarketRow(entry["name"], [Instrument(g["name"], g["symbol"]) for g in entry["group"]],
                                  group=True))
        else:
            rows.append(MarketRow(entry["name"], [Instrument(entry["name"], entry["symbol"])]))
    return rows


def _news_query(row: MarketRow) -> str:
    if row.group:
        return " OR ".join(f'"{i.name}"' for i in row.instruments) + " stock"
    return re.sub(r"\s*\(.*?\)", "", row.name) + " market"


def _move_text(row: MarketRow, days: int) -> str:
    parts = []
    for i in row.instruments:
        c = i.change(days)
        if c is not None:
            parts.append(f"{i.name} {c:+.2f} points" if i.is_yield else f"{i.name} {c:+.1f}%")
    return ", ".join(parts) or "no price data"


def _summarize(rows: List[MarketRow], interests: dict, cfg: dict, news: Dict[str, List[fetch.Item]]) -> bool:
    """Fill each row's summary and links with one Claude request. Returns False if it failed."""
    drivers = cfg.get("drivers_summary") or {}
    period = drivers.get("period", "past quarter")
    system = SYSTEM.format(name=interests["owner"]["name"], period=period,
                           max_words=drivers.get("max_words", 60),
                           rules=" ".join((drivers.get("rules") or "").split()))
    ids: Dict[str, fetch.Item] = {}
    blocks = []
    for r, row in enumerate(rows):
        lines = []
        for n, item in enumerate(news.get(row.name, [])[:NEWS_PER_ROW]):
            ids[f"m{r}-{n}"] = item
            day = item.published.strftime("%d %b") if item.published else "?"
            lines.append(f"  [m{r}-{n}] {day} · {item.source}: {item.title}")
        blocks.append(f"## {row.name}\nMove over the {period}: {_move_text(row, QUARTER_DAYS)}\n"
                      + ("\n".join(lines) or "  (no headlines found)"))
    try:
        response = make_client().messages.create(
            model=MODEL, max_tokens=8000, system=system,
            messages=[{"role": "user", "content": "\n\n".join(blocks)}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        answers = {m["name"]: m for m in json.loads(text)["markets"]}
    except (anthropic.APIError, json.JSONDecodeError, KeyError) as e:
        log.error("markets: could not get driver summaries: %s", e)
        return False
    for row in rows:
        answer = answers.get(row.name)
        if answer:
            row.summary = answer["summary"]
            row.links = [(ids[i].source, ids[i].link) for i in answer["source_ids"] if i in ids][:3]
    return True


def _fake_summaries(rows: List[MarketRow]):
    for row in rows:
        row.summary = f"(Layout test) {row.name}: {_move_text(row, QUARTER_DAYS)} over the past quarter."
        row.links = [("Example source", "https://example.com/")]


def _to_json(rows: List[MarketRow]) -> list:
    return [{"name": r.name, "group": r.group, "summary": r.summary, "links": r.links,
             "instruments": [{"name": i.name, "symbol": i.symbol, "points": i.points} for i in r.instruments]}
            for r in rows]


def _from_json(data: list) -> List[MarketRow]:
    return [MarketRow(r["name"], [Instrument(i["name"], i["symbol"], [tuple(p) for p in i["points"]])
                                  for i in r["instruments"]],
                      r["group"], r["summary"], [tuple(l) for l in r["links"]]) for r in data]


def build(interests: dict, cache: Optional[dict], today: str, fake: bool = False) -> Tuple[List[MarketRow], dict]:
    """Return (rows, cache to save). Prices and summaries refresh once a day (`refresh: daily`);
    later runs that day reuse the cache. A run where prices or summaries failed isn't cached."""
    cfg = interests.get("markets") or {}
    if not cfg.get("instruments"):
        return [], cache or {}
    daily = cfg.get("refresh", "daily") == "daily"
    if daily and cache and cache.get("date") == today and not fake:
        log.info("markets: reusing today's data")
        return _from_json(cache["rows"]), cache

    rows = _rows(cfg)
    for row in rows:
        for inst in row.instruments:
            inst.points = fetch.fetch_prices(inst.symbol, "1y")
    priced = sum(1 for r in rows for i in r.instruments if i.points)
    log.info("markets: prices for %d of %d instruments", priced, sum(len(r.instruments) for r in rows))
    if not priced:
        return rows, cache or {}

    if fake:
        _fake_summaries(rows)
        return rows, cache or {}
    since = datetime.fromisoformat(today).replace(tzinfo=timezone.utc) - timedelta(days=QUARTER_DAYS)
    specs = {row.name: {"google": _news_query(row), "when": f"{QUARTER_DAYS}d"} for row in rows}
    news = {name: fetch.fetch_source(name, spec, since) for name, spec in specs.items()}
    ok = _summarize(rows, interests, cfg, news)
    complete = ok and priced == sum(len(r.instruments) for r in rows)
    return rows, ({"date": today, "rows": _to_json(rows)} if complete else cache or {})

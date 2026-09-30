"""Score, merge and translate items with Claude — one request per topic."""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import anthropic
import yaml

from fetch import Item

log = logging.getLogger(__name__)

MODEL = os.environ.get("NEWSBOT_MODEL") or "claude-sonnet-5"
EFFORT = os.environ.get("NEWSBOT_EFFORT") or "medium"

SYSTEM = """You are the editor of a personal news briefing for {name} (timezone {tz}).
You receive the raw items fetched for ONE topic since the last briefing, plus that topic's rules.

For the topic:
1. Group items that report the same story (across outlets, and across languages) into one story.
2. Score each story 0-10 for how much {name} should see it, strictly following the topic rules:
   - {alert}-10: meets the topic's `instant_alert_if` rule.
   - {digest}-{alert_minus}: meets the topic's `digest_if` rule.
   - below {digest}: everything else, including anything matching `ignore` rules.
   Respect caps in the rules (e.g. "top 5", "max 3 per day") by scoring the rest below {digest}.
3. Write a neutral English headline and a one-sentence English summary for each story, translating
   any non-English source. Base them only on the items given; do not add facts.

Global ignore rules: {ignore}

Return only stories scoring {digest} or more. Returning no stories is fine."""

SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_ids": {"type": "array", "items": {"type": "string"},
                                 "description": "ids of every input item covering this story, most authoritative first"},
                    "score": {"type": "integer", "description": "0-10"},
                    "headline": {"type": "string"},
                    "summary": {"type": "string", "description": "one sentence"},
                },
                "required": ["item_ids", "score", "headline", "summary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stories"],
    "additionalProperties": False,
}


@dataclass
class Story:
    id: str              # id of the lead item (or stock:TICKER:DATE), used for dedupe
    topic: str
    score: int
    headline: str
    summary: str
    link: str
    sources: List[str]
    published: Optional[datetime]
    item_ids: List[str]


def _topic_rules(topic: dict) -> str:
    rules = {k: v for k, v in topic.items() if k not in ("sources", "watchlist")}
    return yaml.safe_dump(rules, sort_keys=False, allow_unicode=True)


def score_topic(client: anthropic.Anthropic, interests: dict, key: str, items: List[Item],
                recent_headlines: List[str]) -> Optional[List[Story]]:
    """Return the topic's stories, or None if Claude could not score it."""
    if not items:
        return []
    alerts = interests["alerts"]
    system = SYSTEM.format(
        name=interests["owner"]["name"], tz=interests["owner"]["timezone"],
        alert=alerts["alert_threshold"], digest=alerts["digest_threshold"],
        alert_minus=alerts["alert_threshold"] - 1, ignore="; ".join(interests.get("ignore", [])),
    )
    payload = [{"id": i.id, "source": i.source, "title": i.title, "summary": i.summary,
                "published": i.published.isoformat() if i.published else None} for i in items]
    user = (f"Topic: {key}\n\nTopic rules:\n{_topic_rules(interests['topics'][key])}\n"
            f"Headlines already sent in the last few days (score any repeat of these below "
            f"{alerts['digest_threshold']} unless there is a genuinely new development):\n"
            + ("\n".join(f"- {h}" for h in recent_headlines) or "(none)")
            + f"\n\nItems:\n{json.dumps(payload, ensure_ascii=False)}")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except anthropic.APIStatusError as e:
        log.error("topic %s: Claude API error %s: %s", key, e.status_code, e.message)
        return None
    except anthropic.APIConnectionError as e:
        log.error("topic %s: could not reach Claude API: %s", key, e)
        return None

    if response.stop_reason == "refusal":
        log.warning("topic %s: request declined (%s)", key, response.stop_details)
        return None
    if response.stop_reason == "max_tokens":
        log.warning("topic %s: response hit max_tokens, skipping", key)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        raw = json.loads(text)["stories"]
    except (json.JSONDecodeError, KeyError) as e:
        log.error("topic %s: could not parse response: %s", key, e)
        return None

    by_id = {i.id: i for i in items}
    stories = []
    for s in raw:
        members = [by_id[i] for i in s["item_ids"] if i in by_id]
        if not members:
            continue
        dates = [m.published for m in members if m.published]
        stories.append(Story(
            id=members[0].id, topic=key, score=max(0, min(10, s["score"])),
            headline=s["headline"], summary=s["summary"], link=members[0].link,
            sources=list(dict.fromkeys(m.source for m in members)),
            published=min(dates) if dates else None, item_ids=[m.id for m in members],
        ))
    u = response.usage
    log.info("topic %-18s %3d items -> %2d stories  (in %d / out %d tokens)",
             key, len(items), len(stories), u.input_tokens, u.output_tokens)
    return stories


def score_all(interests: dict, items_by_topic: Dict[str, List[Item]],
              recent_headlines: List[str]) -> Tuple[List[Story], List[str]]:
    """Return (stories, keys of topics that failed to score)."""
    client = anthropic.Anthropic()
    keys = [k for k, v in items_by_topic.items() if v]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(keys, pool.map(lambda k: score_topic(client, interests, k, items_by_topic[k],
                                                                recent_headlines), keys)))
    failed = [k for k, r in results.items() if r is None]
    return [s for r in results.values() if r for s in r], failed

"""Apply feedback from a "Newsbot feedback" GitHub issue to feedback.yaml.

Run by .github/workflows/feedback.yml with the issue body in $ISSUE_BODY. The body is untrusted
text: only the JSON block is read, and every value is type-checked and length-limited.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
FEEDBACK = ROOT / "feedback.yaml"
KEEP_EXAMPLES = 150      # per list: newest kept
MAX_PER_ISSUE = 50
# Story lists the page can send: issue key -> feedback.yaml key (👎, 👍, ⭐).
STORY_LISTS = {"not_interested": "not_interested", "more_like_this": "more_like_this", "starred": "starred"}


def clean(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()[:limit]


def main():
    match = re.search(r"```json\s*(\{.*?\})\s*```", os.environ.get("ISSUE_BODY", ""), re.S)
    if not match:
        sys.exit("No feedback JSON block found in the issue.")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        sys.exit(f"Feedback JSON is invalid: {e}")
    if not isinstance(data, dict):
        sys.exit("Feedback JSON must be an object.")

    topics = set(yaml.safe_load((ROOT / "interests.yaml").read_text())["topics"])
    current = yaml.safe_load(FEEDBACK.read_text()) if FEEDBACK.exists() else None
    current = current or {}
    muted = list(current.get("muted_sources") or [])

    def names(key):
        items = data.get(key) if isinstance(data.get(key), list) else []
        return [n for n in (clean(v, 100) for v in items[:MAX_PER_ISSUE]) if n]

    added, removed = names("mute_sources"), names("unmute_sources")
    for name in added:
        if name.casefold() not in {m.casefold() for m in muted}:
            muted.append(name)
    muted = [m for m in muted if m.casefold() not in {r.casefold() for r in removed}]

    lists, counts = {}, {}
    for issue_key, key in STORY_LISTS.items():
        entries = list(current.get(key) or [])
        raw = data.get(issue_key) if isinstance(data.get(issue_key), list) else []
        known = {n.get("headline") for n in entries if isinstance(n, dict)}
        counts[key] = 0
        for entry in raw[:MAX_PER_ISSUE]:
            if not isinstance(entry, dict):
                continue
            topic, headline = clean(entry.get("topic"), 50), clean(entry.get("headline"), 300)
            if topic in topics and headline and headline not in known:
                saved = {"topic": topic, "headline": headline, "source": clean(entry.get("source"), 100),
                         "date": date.today().isoformat()}
                link = clean(entry.get("link"), 1000)
                if key == "starred" and re.match(r"https?://", link):
                    saved["link"] = link
                entries.append(saved)
                known.add(headline)
                counts[key] += 1
        lists[key] = entries[-KEEP_EXAMPLES:]

    header = "".join(l + "\n" for l in FEEDBACK.read_text().splitlines() if l.startswith("#")) \
        if FEEDBACK.exists() else ""
    FEEDBACK.write_text(header + "\n" + yaml.safe_dump(
        {"muted_sources": muted, **lists},
        sort_keys=False, allow_unicode=True, width=200))

    summary = []
    if added:
        summary.append("muted " + ", ".join(added))
    if removed:
        summary.append("unmuted " + ", ".join(removed))
    for key, what in (("more_like_this", "👍"), ("not_interested", "👎"), ("starred", "⭐")):
        if counts[key]:
            summary.append(f"{counts[key]} {what} saved")
    print("; ".join(summary) or "nothing new to save")


if __name__ == "__main__":
    main()

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
KEEP_NOT_INTERESTED = 150
MAX_PER_ISSUE = 50


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
    not_interested = list(current.get("not_interested") or [])

    def names(key):
        items = data.get(key) if isinstance(data.get(key), list) else []
        return [n for n in (clean(v, 100) for v in items[:MAX_PER_ISSUE]) if n]

    added, removed = names("mute_sources"), names("unmute_sources")
    for name in added:
        if name.casefold() not in {m.casefold() for m in muted}:
            muted.append(name)
    muted = [m for m in muted if m.casefold() not in {r.casefold() for r in removed}]

    new_examples = 0
    raw = data.get("not_interested") if isinstance(data.get("not_interested"), list) else []
    known = {n.get("headline") for n in not_interested if isinstance(n, dict)}
    for entry in raw[:MAX_PER_ISSUE]:
        if not isinstance(entry, dict):
            continue
        topic, headline = clean(entry.get("topic"), 50), clean(entry.get("headline"), 300)
        if topic in topics and headline and headline not in known:
            not_interested.append({"topic": topic, "headline": headline,
                                   "source": clean(entry.get("source"), 100),
                                   "date": date.today().isoformat()})
            known.add(headline)
            new_examples += 1
    not_interested = not_interested[-KEEP_NOT_INTERESTED:]

    header = "".join(l + "\n" for l in FEEDBACK.read_text().splitlines() if l.startswith("#")) \
        if FEEDBACK.exists() else ""
    FEEDBACK.write_text(header + "\n" + yaml.safe_dump(
        {"muted_sources": muted, "not_interested": not_interested},
        sort_keys=False, allow_unicode=True, width=200))

    summary = []
    if added:
        summary.append("muted " + ", ".join(added))
    if removed:
        summary.append("unmuted " + ", ".join(removed))
    if new_examples:
        summary.append(f"{new_examples} 'not interested' example(s) saved")
    print("; ".join(summary) or "nothing new to save")


if __name__ == "__main__":
    main()

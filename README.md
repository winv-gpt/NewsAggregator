# News Aggregator

A personal news briefing webpage, rebuilt at 07:00 and 17:00 (Bangkok time).

Page: https://winv-gpt.github.io/NewsAggregator/

Each run:
1. Fetches everything published since the previous run from the sources in `feeds.yaml`.
2. Asks Claude (Sonnet 5 by default) to merge duplicate stories, translate Thai items, and score each story 0–10 against your rules in `interests.yaml`.
3. Rebuilds the page: **Alerts** (score 8+) at the top, then each topic's stories (5–7), each with a 2–3 sentence summary. Links to the past 7 days of briefings are at the bottom.

## Teaching the bot from the page

Every card has two checkboxes:
- **Mute {source}**: stop showing stories from that outlet.
- **Not interested**: show fewer stories like this one (Claude uses them as examples when scoring that topic).

Tick as many as you like, then tap **Save to bot**. GitHub opens a pre-filled issue; tap **Create**. The *Save page feedback* workflow writes it into `feedback.yaml` and closes the issue, and it applies from the next briefing. Muted sources are listed at the bottom of the page with **Unmute** boxes. Only issues opened by the repo owner are applied.

Stock moves for the watchlist come from Yahoo Finance and are scored by fixed rules (over 7% = alert, over 3% = listed), not by Claude.

## Files

| File | What it is |
|---|---|
| `interests.yaml` | Your topics, rules, thresholds and layout. Edit freely. |
| `feeds.yaml` | Where each source name is fetched from (RSS URL or Google News search). |
| `run.py` | Entry point: fetch → score → arrange → webpage. |
| `feedback.yaml` | Your mutes and "not interested" examples, written by the page's checkboxes. Editable by hand. |
| `fetch.py` / `score.py` / `web.py` | The individual steps. |
| `apply_feedback.py` | Saves feedback from a page issue into `feedback.yaml`. |
| `.github/workflows/newsbot.yml` | Runs the bot twice a day on GitHub Actions and publishes the page. |
| `.github/workflows/feedback.yml` | Applies feedback issues from the page. |

## Setup

1. **Settings → Secrets and variables → Actions → Secrets**: add `ANTHROPIC_API_KEY`. Create the key *inside a workspace* (platform.claude.com → Workspaces → pick one → API keys). If you use a key that isn't scoped to a workspace, also add an Actions **variable** `ANTHROPIC_WORKSPACE_ID` with the workspace's ID.
2. **Settings → Pages**: set *Source* to **GitHub Actions**.
3. **Actions → News briefing → Run workflow** to run it now. After that it runs on schedule.

> GitHub Pages is free for public repositories, which means the page and `interests.yaml` are publicly visible. A private repo with Pages needs GitHub Pro.

If a run fails (for example, the API key runs out of credit), GitHub emails you and the page keeps its last briefing.

## Running locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                                  # then put your API key in .env
.venv/bin/python run.py --preview                     # real scoring; builds site/index.html
.venv/bin/python run.py --fake-scores --preview       # no Claude call, for layout testing
```

`--preview` never updates the bot's memory, so you can preview as often as you like.

## Changing things

- **Rules, thresholds, topics:** edit `interests.yaml`. Changes apply on the next run.
- **Add a source:** add it to `feeds.yaml` (`url:` for an RSS feed, `google:` for a Google News search), then list its name under a topic's `sources`.
- **Model:** add an Actions *variable* `NEWSBOT_MODEL` (e.g. `claude-opus-5` for sharper judgment at ~2.5× the cost).
- **Times:** edit the two `cron` lines in the workflow (they are in UTC; Bangkok is UTC+7).

## Not yet supported
- The X account `@blue_footy`: reading X requires the paid X API. Chelsea news comes from chelseafc.com, BBC Sport and Google News instead.

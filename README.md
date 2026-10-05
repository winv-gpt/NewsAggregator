# News Aggregator

A personal news briefing webpage, rebuilt at 06:30 (*Win's Morning Briefing*) and 18:00 (*Win's Evening Digest*), Bangkok time.

Page: https://winv-gpt.github.io/NewsAggregator/

Each run:
1. Fetches everything published since the previous run from the sources in `feeds.yaml`.
2. Asks Claude (Sonnet 5 by default) to merge duplicate stories, translate Thai items, and score each story 0–10 against your rules in `interests.yaml`.
3. Rebuilds the page: **Alerts** (score 8+, at most 6 a day) at the top, then each topic's stories (5–7), each with a one-sentence summary (25 words max), then **Markets** at the bottom.

For a fresh briefing outside the schedule, open GitHub's *Actions → News briefing* page and tap **Run workflow** (then the green **Run workflow** button). Reload the page about 3 minutes later. Setting `fetch_now_button: true` in `interests.yaml` puts a **↻ Fetch now** shortcut to that page at the top of the briefing.

## Markets

The last section shows a 12-month chart for each instrument under `markets:` in `interests.yaml` (prices from Yahoo Finance, with the past quarter shaded), its 1-day / 3-month / 12-month change, and a short note (60 words max) from Claude on what drove the past quarter's move, based only on news headlines and linking to them. A `group:` (like *Payments stocks*) is shown as one compact row of % changes. Market data and notes refresh once a day, so the evening digest reuses the morning's (unless you change the `instruments` list).

## Teaching the bot from the page

Every card has these buttons:
- **👍**: more like this (Claude scores similar stories a little higher).
- **👎**: less like this (Claude scores similar stories lower).

Tap as many as you like, then tap **Save to bot**. GitHub opens a pre-filled issue; tap **Create**. The *Save page feedback* workflow writes it into `feedback.yaml` and closes the issue, and it applies from the next briefing. Only issues opened by the repo owner are applied.

Stock moves for the watchlist come from Yahoo Finance and are scored by fixed rules (over 7% = alert, over 3% = listed), not by Claude.

## Files

| File | What it is |
|---|---|
| `interests.yaml` | Your topics, rules, thresholds and layout. Edit freely. |
| `feeds.yaml` | Where each source name is fetched from (RSS URL or Google News search). |
| `run.py` | Entry point: fetch → score → arrange → webpage. |
| `feedback.yaml` | Your 👍 / 👎 stories, written by the page's buttons. Editable by hand. |
| `fetch.py` / `score.py` / `markets.py` / `web.py` | The individual steps (`markets.py` builds the Markets section). |
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
- **Times:** edit the two `cron` lines in the workflow (they are in UTC; Bangkok is UTC+7). Changing `morning_briefing_time` / `evening_digest_time` in `interests.yaml` alone doesn't move the runs.
- **Earlier briefings:** set `show_previous_briefings: true` in `interests.yaml` to bring back links to the past 7 days' briefings.

## Not yet supported
- The X account `@blue_footy`: reading X requires the paid X API, so it's skipped.
- Telegram (`instant_push`, `quiet_hours`, `presentation.telegram`): the bot publishes only the webpage. `instant_push` and `daily_digest` are used as the page's alert and digest score thresholds, and `max_instant_per_day` caps alerts per day.

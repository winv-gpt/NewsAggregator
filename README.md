# News bot

A personal news briefing, sent to Telegram at 07:00 and 17:00 (Bangkok time) and published as a webpage.

Each run:
1. Fetches everything published since the previous run from the sources in `feeds.yaml`.
2. Asks Claude (Sonnet 5 by default) to merge duplicate stories, translate Thai items, and score each story 0–10 against your rules in `interests.yaml`.
3. Sends a Telegram message: **alerts** (score 8+) first, then the **digest** (5–7) grouped by topic.
4. Rebuilds the webpage with the same briefing as cards.

Stock moves for the watchlist come from Yahoo Finance and are scored by fixed rules (over 7% = alert, over 3% = digest), not by Claude.

## Files

| File | What it is |
|---|---|
| `interests.yaml` | Your topics, rules, thresholds and layout. Edit freely. |
| `feeds.yaml` | Where each source name is fetched from (RSS URL or Google News search). |
| `run.py` | Entry point: fetch → score → arrange → Telegram + webpage. |
| `fetch.py` / `score.py` / `telegram.py` / `web.py` | The individual steps. |
| `.github/workflows/newsbot.yml` | Runs the bot twice a day on GitHub Actions. |

## Setup

### 1. Telegram bot
1. In Telegram, message **@BotFather**, send `/newbot`, and follow the prompts. Save the token it gives you.
2. Send your new bot any message (e.g. "hi").
3. Find your chat ID: copy `.env.example` to `.env`, put the token in `TELEGRAM_BOT_TOKEN`, then run `python setup_telegram.py`.

### 2. Anthropic API key
Create one at https://platform.claude.com/settings/keys.

### 3. GitHub
1. Create a new repository on github.com and push this folder to it.
2. **Settings → Secrets and variables → Actions → Secrets**: add `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. **Settings → Pages**: set *Source* to **GitHub Actions**.
4. **Actions → News briefing → Run workflow** to test it now. The page URL appears in the run summary.
5. Optional: **Settings → Secrets and variables → Actions → Variables**: add `NEWSBOT_PAGE_URL` with that URL so each Telegram message links to the page.

> GitHub Pages is free for public repositories. On a free account a public repo means your `interests.yaml` and the webpage are publicly visible. A private repo with Pages needs GitHub Pro.

## Running locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py --no-send               # real scoring, prints the Telegram text, sends nothing
.venv/bin/python run.py --fake-scores --no-send # no Claude call, for layout testing
.venv/bin/python run.py                          # full run
```

`--no-send` never updates the bot's memory, so you can preview as often as you like.

## Changing things

- **Rules, thresholds, topics:** edit `interests.yaml`. Changes apply on the next run.
- **Add a source:** add it to `feeds.yaml` (`url:` for an RSS feed, `google:` for a Google News search), then list its name under a topic's `sources`.
- **Model:** set the Actions variable `NEWSBOT_MODEL` (e.g. `claude-opus-5` for sharper judgment at ~2.5× the cost).
- **Times:** edit the two `cron` lines in the workflow (they are in UTC; Bangkok is UTC+7).

## Not yet supported
- The X account `@blue_footy`: reading X requires the paid X API. Chelsea news comes from chelseafc.com, BBC Sport and Google News instead.

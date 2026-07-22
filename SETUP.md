# Football Bot — Autonomous AI Football Telegram Channel

## Overview

Fully autonomous AI-powered football Telegram channel that runs via GitHub Actions.
No server, no VPS, no Docker required. Publishes multiple times per day with zero manual intervention.

## Quick Start

### Step 1 — Fork / clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/football-bot.git
cd football-bot
```

### Step 2 — Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Description | Example |
|---|---|---|
| `BOT_TOKEN` | Telegram Bot API token from @BotFather | `7123456789:AAF...` |
| `CHANNEL_ID` | Your Telegram channel (bot must be admin) | `@my_football_channel` or `-1001234567890` |
| `MISTRAL_API_KEY` | Mistral AI API key from console.mistral.ai | `abc123...` |
| `MISTRAL_MODEL` | Mistral model to use | `mistral-large-latest` |

### Step 3 — Make the bot an admin of your channel

1. Open your Telegram channel settings
2. Administrators → Add Administrator
3. Search for your bot and add it
4. Give it permission to **Post Messages**

### Step 4 — Test manually

Go to **Actions → Football Bot → Run workflow** and select a mode:

- `news` — collect and publish breaking news
- `facts` — publish an interesting fact or historical post
- `standings` — publish league tables
- `digest_daily` — daily news digest

### Step 5 — Set up automatic scheduling with cron-job.org

The bot is triggered externally by HTTP POST to GitHub's `workflow_dispatch` API.

#### Create a Personal Access Token

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Create token with permission: **Actions: Read and Write** on your repository
3. Copy the token — you'll need it for cron-job.org

#### Configure cron-job.org

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Create a new cronjob for each schedule you want

**URL format:**
```
https://api.github.com/repos/YOUR_USERNAME/football-bot/actions/workflows/football_bot.yml/dispatches
```

**Method:** POST

**Headers:**
```
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_PAT
Content-Type: application/json
X-GitHub-Api-Version: 2022-11-28
```

**Body (JSON):**
```json
{
  "ref": "main",
  "inputs": {
    "run_mode": "news"
  }
}
```

#### Recommended schedule

| Cron expression | Run mode | Description |
|---|---|---|
| `0 6 * * *` | `news` | Morning news (06:00 UTC) |
| `0 9 * * *` | `news` | Midday news (09:00 UTC) |
| `0 12 * * *` | `standings` | Midday standings |
| `0 15 * * *` | `news` | Afternoon news |
| `0 18 * * *` | `news` | Evening news |
| `0 20 * * *` | `facts` | Evening interesting fact |
| `0 22 * * *` | `digest_daily` | Daily digest |
| `0 10 * * 1` | `digest_weekly` | Weekly digest (Mondays) |
| `0 10 1 * *` | `digest_monthly` | Monthly digest (1st of month) |
| `0 8 * * *` | `analytics` | Daily self-learning update |

#### Example curl command to trigger manually

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_GITHUB_PAT" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/YOUR_USERNAME/football-bot/actions/workflows/football_bot.yml/dispatches \
  -d '{"ref":"main","inputs":{"run_mode":"news"}}'
```

## Architecture

```
football_bot/
├── config/          # Settings (Pydantic) + constants (sources, leagues)
├── core/
│   ├── models/      # Domain models: NewsItem, Match, Publication, Standing
│   └── interfaces/  # Abstract Repository + Service contracts
├── storage/         # SQLAlchemy schema + async DB manager (SQLite)
├── repositories/    # Concrete implementations: news, match, publication
├── services/
│   ├── mistral_service.py     # LLM: retries, rate limiting, caching, fallback
│   ├── news_aggregator.py     # Orchestrates all parsers
│   ├── duplicate_detector.py  # Cosine similarity deduplication
│   ├── fact_checker.py        # Multi-source reliability scoring via LLM
│   ├── ai_editor.py           # All publication text generation
│   ├── image_generator.py     # Pillow card generation
│   ├── match_center.py        # Match schedule + results
│   ├── live_center.py         # Live match event publishing
│   ├── standings_generator.py # League table posts
│   ├── history_generator.py   # Historical "on this day" posts
│   ├── facts_generator.py     # Interesting facts & trivia
│   ├── analytics_engine.py    # Performance analysis
│   └── self_learning.py       # Strategy auto-adjustment
├── parsers/
│   ├── rss_parser.py          # 25+ RSS/Atom feeds
│   ├── html_parser.py         # HTML scraping (selectolax + BS4)
│   └── transfer_parser.py     # Transfer market specialist parser
├── telegram/
│   ├── publisher.py           # aiogram 3.x Bot API client
│   └── formatter.py           # HTML sanitisation + length limits
├── utils/
│   ├── logger.py              # structlog structured logging
│   ├── metrics.py             # Runtime metrics collector
│   └── health.py              # Health check aggregator
└── runners/
    └── github_actions_runner.py  # Main entry point + DI container
```

## Available run modes

| Mode | Trigger | Description |
|---|---|---|
| `news` | Every 3h | Collect, fact-check, write, publish breaking news |
| `live` | Every 1min (during match) | Publish live match events |
| `digest_daily` | 22:00 UTC | Daily news summary |
| `digest_weekly` | Monday 10:00 UTC | Weekly roundup |
| `digest_monthly` | 1st 10:00 UTC | Monthly review |
| `facts` | 20:00 UTC | Interesting fact or historical post |
| `standings` | 12:00 UTC | League tables |
| `analytics` | 08:00 UTC daily | Self-learning analytics update |

## Data persistence

The SQLite database (`data/football_bot.db`) is persisted between runs using **GitHub Actions Cache**.
The cache is keyed by run number and restored at the start of each run. This ensures:

- Deduplication works across runs
- Self-learning state persists
- No re-publishing of already sent content
- LLM response cache persists (cost saving)

## News sources (25+)

RSS: BBC Sport, Sky Sports, ESPN FC, The Guardian, UEFA, FIFA, Goal.com, FourFourTwo, Marca, AS, Sport, Gazzetta, Kicker, L'Équipe, Sport-Express, Championat, and more.

HTML: Transfermarkt, Flashscore, FBref, SofaScore.

Transfers: Transfermarkt, Fabrizio Romano, Sky Sports Transfers, BBC.

## Self-learning

After 30+ publications, the analytics engine automatically adjusts:
- Publication format weights (what formats perform best)
- Best posting hours
- Preferred leagues

State is stored in SQLite and survives between runs.

## Local testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export BOT_TOKEN="your_token"
export CHANNEL_ID="@your_channel"
export MISTRAL_API_KEY="your_key"
export MISTRAL_MODEL="mistral-large-latest"
export RUN_MODE="news"

# Run
python -m football_bot.main
```

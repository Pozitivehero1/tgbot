# Football Bot — Autonomous AI Football Telegram Channel

Fully autonomous AI-powered football Telegram channel. Runs via GitHub Actions on schedule triggered by cron-job.org. Zero manual intervention after initial setup.

## Run & Operate

```bash
# Local run (set .env first)
python -m football_bot.main

# Run specific pipeline
RUN_MODE=news python -m football_bot.main
RUN_MODE=standings python -m football_bot.main
RUN_MODE=facts python -m football_bot.main
RUN_MODE=digest_daily python -m football_bot.main

# Install dependencies
pip install -r requirements.txt
```

## Required environment variables

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot API token from @BotFather |
| `CHANNEL_ID` | Telegram channel ID (`@channel` or `-100...`) |
| `MISTRAL_API_KEY` | Mistral AI API key |
| `MISTRAL_MODEL` | Model name, e.g. `mistral-large-latest` |

## Stack

- Python 3.12 + asyncio
- aiogram 3.x (Telegram Bot API)
- Mistral AI (exclusive LLM provider — no OpenAI/Claude/Gemini)
- SQLAlchemy 2.0 + aiosqlite (SQLite)
- httpx + selectolax + BeautifulSoup4 + feedparser (parsers)
- Pillow (image card generation)
- structlog (structured JSON logging)
- Pydantic + pydantic-settings (config/models)
- tenacity (retry logic)
- GitHub Actions (execution environment)
- cron-job.org (external cron trigger via workflow_dispatch)

## Where things live

```
football_bot/
├── config/          # Settings (Pydantic) + constants (25+ news sources, leagues)
├── core/models/     # Domain models: NewsItem, Match, Publication, Standing
├── core/interfaces/ # Abstract Repository + Service contracts (Clean Architecture)
├── storage/         # SQLAlchemy schema + async DB manager
├── repositories/    # Concrete implementations (news, match, publication)
├── services/        # All business logic (Mistral, aggregator, editor, etc.)
├── parsers/         # RSS (25+ feeds), HTML (selectolax+BS4), Transfer parser
├── telegram/        # Publisher (aiogram 3.x) + HTML formatter
├── utils/           # logger, metrics, health checker
└── runners/         # GitHub Actions entry point + DI container
.github/workflows/   # football_bot.yml — workflow_dispatch triggered
SETUP.md             # Full setup guide with cron-job.org instructions
.env.example         # All configurable env vars with defaults
```

## Architecture decisions

- **Clean Architecture**: core models/interfaces know nothing about infrastructure
- **Repository Pattern**: all DB access goes through abstract interfaces
- **Service Layer**: each service has a single responsibility
- **Dependency Injection**: Container class in runner wires everything
- **GitHub Actions Cache**: SQLite DB persisted between runs (dedup + self-learning state)
- **No schedule in workflow**: uses `workflow_dispatch` triggered by external cron-job.org
- **Mistral-only LLM**: MistralService with retry, rate limiting, dual-model failover, caching

## Run modes

| Mode | Description |
|---|---|
| `news` | Collect RSS → fact-check → write → publish breaking news |
| `live` | Poll live matches → publish goal/card/sub events |
| `digest_daily` | Daily news summary |
| `digest_weekly` | Weekly roundup |
| `digest_monthly` | Monthly review |
| `facts` | Interesting fact or historical "on this day" post |
| `standings` | League tables with AI commentary |
| `analytics` | Self-learning analytics cycle |

## User preferences

- Python 3.12, no type stubs ignored, full typing throughout
- No TODO, no mock, no pass, no stubs
- Mistral AI exclusively — no OpenAI, no Claude, no Gemini
- No Docker, no VPS, no persistent server — GitHub Actions only
- External cron via cron-job.org → workflow_dispatch
- All files production-ready and complete

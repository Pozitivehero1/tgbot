"""Entry point — `python -m football_bot.main` or `python football_bot/main.py`."""

import asyncio

from football_bot.runners.github_actions_runner import run

if __name__ == "__main__":
    asyncio.run(run())

"""NewsAggregator — orchestrates all parsers and persists deduplicated news."""

from __future__ import annotations

import asyncio
from datetime import datetime

from football_bot.config.settings import get_settings
from football_bot.core.models.news import NewsItem
from football_bot.parsers.rss_parser import RSSParser
from football_bot.parsers.transfer_parser import TransferParser
from football_bot.repositories.news_repository import NewsRepository
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class NewsAggregator:
    """Fetches news from all configured sources, deduplicates, and saves to DB."""

    def __init__(
        self,
        news_repository: NewsRepository,
        rss_parser: RSSParser,
        transfer_parser: TransferParser,
    ) -> None:
        self._repo = news_repository
        self._rss_parser = rss_parser
        self._transfer_parser = transfer_parser
        self._settings = get_settings()

    async def run(self) -> list[NewsItem]:
        """Full aggregation pipeline: fetch → filter → persist → return new items."""
        logger.info("news_aggregation_started")

        rss_task = self._rss_parser.fetch_all_rss_sources()
        transfer_task = self._transfer_parser.fetch_all_transfer_sources()
        rss_items, transfer_items = await asyncio.gather(rss_task, transfer_task)

        all_items = rss_items + transfer_items
        logger.info("news_fetched_total", count=len(all_items))

        fresh_items = [
            item for item in all_items
            if not item.is_stale(self._settings.max_news_age_hours)
        ]
        logger.info("news_fresh", count=len(fresh_items))

        new_items: list[NewsItem] = []
        for item in fresh_items:
            if not await self._repo.exists(item.item_id):
                await self._repo.save(item)
                new_items.append(item)

        logger.info("news_aggregation_complete", new=len(new_items), total=len(fresh_items))
        return new_items

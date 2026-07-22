"""Transfer news parser — aggregates from RSS + HTML sources."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from football_bot.config.constants import TRANSFER_SOURCES
from football_bot.core.models.news import NewsCategory, NewsItem, NewsReliability
from football_bot.parsers.base_parser import BaseParser, make_item_id
from football_bot.parsers.rss_parser import RSSParser
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_TRANSFER_KEYWORDS = {
    "transfer", "signing", "joins", "move", "deal", "fee", "contract",
    "loan", "departure", "release", "extends", "renews", "bid", "offer",
    "agree", "confirmed", "unveil", "announce", "medical",
}

_TRANSFER_AMOUNT_PATTERN = re.compile(
    r"(?:€|£|\$|euros?|pounds?|million|m\b|bn\b|\d+)",
    re.IGNORECASE,
)


class TransferParser(BaseParser):
    """Specialist parser for transfer market news."""

    def __init__(self) -> None:
        super().__init__()
        self._rss_parser = RSSParser()

    @property
    def source_name(self) -> str:
        return "TransferParser"

    def _is_transfer_item(self, item: NewsItem) -> bool:
        combined = (item.title + " " + item.summary).lower()
        return any(kw in combined for kw in _TRANSFER_KEYWORDS)

    def _extract_transfer_amount(self, text: str) -> Optional[str]:
        match = _TRANSFER_AMOUNT_PATTERN.search(text)
        if match:
            start = max(0, match.start() - 10)
            end = min(len(text), match.end() + 20)
            return text[start:end].strip()
        return None

    def _extract_clubs(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Naive extraction: look for 'from Club A to Club B' pattern."""
        pattern = re.compile(
            r"(?:from|leaves?)\s+([A-Z][a-zA-Z\s]+?)(?:\s+to|\s+for|\s+joins?|\.|,)",
            re.IGNORECASE,
        )
        pattern2 = re.compile(
            r"(?:to|joins?|signs? for)\s+([A-Z][a-zA-Z\s]{3,30}?)(?:\s+for|\s+on|\.|,|\s+in\s)",
            re.IGNORECASE,
        )
        from_match = pattern.search(text)
        to_match = pattern2.search(text)
        from_club = from_match.group(1).strip() if from_match else None
        to_club = to_match.group(1).strip() if to_match else None
        return from_club, to_club

    async def fetch(self, url: str) -> list[NewsItem]:
        source_meta = next(
            (s for s in TRANSFER_SOURCES if s["url"] == url),
            {"name": url, "type": "rss", "reliability": 0.75},
        )
        if source_meta.get("type") == "rss":
            items = await self._rss_parser.fetch(url)
        else:
            from football_bot.parsers.html_parser import HTMLParser
            html = HTMLParser()
            items = await html.fetch(url)
        transfer_items = [item for item in items if self._is_transfer_item(item)]
        for item in transfer_items:
            item.category = NewsCategory.TRANSFER
            item.source_reliability = source_meta.get("reliability", 0.75)
            item.tags.append("transfer")
            amount = self._extract_transfer_amount(item.title + " " + item.summary)
            if amount:
                item.tags.append(f"amount:{amount}")
        logger.info("transfer_fetched", url=url, total=len(items), transfers=len(transfer_items))
        return transfer_items

    async def fetch_all_transfer_sources(self) -> list[NewsItem]:
        """Fetch all configured transfer sources and return deduplicated items."""
        from football_bot.parsers.base_parser import BaseParser
        import asyncio
        urls = [s["url"] for s in TRANSFER_SOURCES]
        tasks = [self.fetch(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_items: list[NewsItem] = []
        seen_ids: set[str] = set()
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.warning("transfer_source_failed", url=url, error=str(result))
                continue
            for item in result:
                if item.item_id not in seen_ids:
                    seen_ids.add(item.item_id)
                    all_items.append(item)
        logger.info("transfer_all_fetched", total=len(all_items))
        return all_items

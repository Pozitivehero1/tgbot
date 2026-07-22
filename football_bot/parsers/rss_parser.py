"""RSS/Atom feed parser using feedparser with full async HTTP fetch."""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from typing import Optional

import feedparser
from dateutil import parser as dateutil_parser

from football_bot.config.constants import NEWS_SOURCES
from football_bot.core.models.news import NewsCategory, NewsItem, NewsReliability
from football_bot.parsers.base_parser import BaseParser, make_item_id
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class RSSParser(BaseParser):
    """Parses RSS/Atom feeds into NewsItem objects."""

    @property
    def source_name(self) -> str:
        return "RSSParser"

    def _parse_date(self, date_string: Optional[str]) -> datetime:
        if not date_string:
            return datetime.utcnow()
        try:
            dt = dateutil_parser.parse(date_string)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return datetime.utcnow()

    def _infer_category(self, title: str, summary: str) -> NewsCategory:
        combined = (title + " " + summary).lower()
        if any(w in combined for w in ["transfer", "signing", "joins", "move", "deal", "fee", "contract"]):
            return NewsCategory.TRANSFER
        if any(w in combined for w in ["injury", "injured", "ruled out", "sidelined", "fitness"]):
            return NewsCategory.INJURY
        if any(w in combined for w in ["lineup", "starting xi", "squad", "bench"]):
            return NewsCategory.LINEUP
        if any(w in combined for w in ["preview", "ahead of", "build-up", "upcoming"]):
            return NewsCategory.MATCH_PREVIEW
        if any(w in combined for w in ["result", "win", "victory", "defeat", "draw", "score", "goal"]):
            return NewsCategory.MATCH_RESULT
        if any(w in combined for w in ["ban", "suspension", "red card", "appeal"]):
            return NewsCategory.DISCIPLINARY
        if any(w in combined for w in ["statement", "official", "club confirm", "press conference"]):
            return NewsCategory.OFFICIAL_STATEMENT
        if any(w in combined for w in ["rumour", "links", "interest", "target", "tracked"]):
            return NewsCategory.RUMOUR
        if any(w in combined for w in ["statistic", "record", "data", "analysis"]):
            return NewsCategory.STATISTICS
        return NewsCategory.GENERAL

    async def fetch(self, url: str) -> list[NewsItem]:
        """Fetch and parse a single RSS feed URL."""
        raw_text = await self._fetch_raw(url)
        if not raw_text:
            return []

        source_meta = next(
            (s for s in NEWS_SOURCES if s["url"] == url),
            {"name": url, "reliability": 0.75, "language": "en"},
        )

        try:
            feed = feedparser.parse(io.StringIO(raw_text))
        except Exception as exc:
            logger.warning("rss_parse_error", url=url, error=str(exc))
            return []

        items: list[NewsItem] = []
        for entry in feed.entries:
            try:
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                article_url = (entry.get("link") or "").strip()
                if not title or not article_url:
                    continue

                published_at = self._parse_date(
                    entry.get("published") or entry.get("updated")
                )
                item_id = make_item_id(article_url, title)
                category = self._infer_category(title, summary)

                # Extract tags if available
                tags: list[str] = [
                    tag.get("term", "") for tag in entry.get("tags", []) if tag.get("term")
                ]

                item = NewsItem(
                    item_id=item_id,
                    source_name=source_meta["name"],
                    source_url=url,
                    article_url=article_url,
                    title=title,
                    summary=summary[:2000],
                    language=source_meta.get("language", "en"),
                    category=category,
                    reliability=NewsReliability.UNCONFIRMED,
                    reliability_score=0.0,
                    published_at=published_at,
                    source_reliability=source_meta.get("reliability", 0.75),
                    tags=tags,
                )
                items.append(item)
            except Exception as exc:
                logger.warning("rss_entry_parse_error", url=url, error=str(exc))
                continue

        logger.info("rss_fetched", url=url, count=len(items))
        return items

    async def fetch_all_rss_sources(self) -> list[NewsItem]:
        """Fetch all configured RSS sources concurrently."""
        rss_sources = [s for s in NEWS_SOURCES if s["type"] == "rss"]
        urls = [s["url"] for s in rss_sources]
        tasks = [self.fetch(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_items: list[NewsItem] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.warning("rss_source_failed", url=url, error=str(result))
            elif isinstance(result, list):
                all_items.extend(result)
        logger.info("rss_all_fetched", total=len(all_items), sources=len(rss_sources))
        return all_items

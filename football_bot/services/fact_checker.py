"""FactChecker — uses Mistral to score news reliability and categorise claims."""

from __future__ import annotations

import asyncio
import json

from football_bot.config.constants import SYSTEM_PROMPT_FACT_CHECKER
from football_bot.core.models.news import NewsItem, NewsReliability
from football_bot.repositories.news_repository import NewsRepository
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_RELIABILITY_MAP = {
    "official": NewsReliability.OFFICIAL,
    "confirmed": NewsReliability.CONFIRMED,
    "rumour": NewsReliability.RUMOUR,
    "insider": NewsReliability.INSIDER,
    "unconfirmed": NewsReliability.UNCONFIRMED,
}


class FactChecker:
    """Scores news items for reliability using cross-source analysis + Mistral."""

    def __init__(
        self,
        mistral_service: MistralService,
        news_repository: NewsRepository,
    ) -> None:
        self._llm = mistral_service
        self._repo = news_repository

    def _build_prompt(self, item: NewsItem, similar_items: list[NewsItem]) -> str:
        corroboration_texts = "\n".join(
            f"- [{s.source_name}] {s.title}" for s in similar_items[:5]
        )
        corroboration_section = (
            f"\nСхожие публикации из других источников:\n{corroboration_texts}"
            if similar_items
            else "\nДругих источников, подтверждающих эту новость, не найдено."
        )
        return f"""Проверь достоверность следующей новости:

Источник: {item.source_name} (рейтинг надёжности: {item.source_reliability:.0%})
Заголовок: {item.title}
Краткое содержание: {item.summary[:500]}
{corroboration_section}

Верни JSON с полями:
- score: число от 0.0 до 1.0 (достоверность)
- category: одно из [official, confirmed, rumour, insider, unconfirmed]
- reasoning: строка с объяснением (2-3 предложения)
- red_flags: список строк с подозрительными признаками (может быть пустым)"""

    async def check_item(self, item: NewsItem) -> NewsItem:
        """Fact-check a single news item and update its reliability fields."""
        recent = await self._repo.get_recent(hours=24, limit=200)
        similar = [
            r for r in recent
            if r.item_id != item.item_id
            and any(word in r.title.lower() for word in item.title.lower().split()[:3])
        ]
        corroboration_count = len(similar) + 1

        try:
            result = await self._llm.generate_json(
                prompt=self._build_prompt(item, similar),
                system_prompt=SYSTEM_PROMPT_FACT_CHECKER,
                temperature=0.1,
            )
            score = float(result.get("score", 0.0))
            category_str = str(result.get("category", "unconfirmed")).lower()
            reliability = _RELIABILITY_MAP.get(category_str, NewsReliability.UNCONFIRMED)
            reasoning = str(result.get("reasoning", ""))
            red_flags = [str(f) for f in result.get("red_flags", [])]

            bonus = min(corroboration_count * 0.03, 0.15)
            final_score = min(score + bonus, 1.0)

            item.reliability_score = final_score
            item.reliability = reliability
            item.reliability_reasoning = reasoning
            item.red_flags = red_flags
            item.corroboration_count = corroboration_count
            item.corroborating_sources = [s.source_name for s in similar[:5]]

            await self._repo.update_reliability(
                item.item_id, final_score, reliability, reasoning, red_flags
            )
            logger.info(
                "fact_check_complete",
                item_id=item.item_id,
                score=round(final_score, 3),
                category=reliability.value,
                corroborations=corroboration_count,
            )
        except Exception as exc:
            logger.error("fact_check_failed", item_id=item.item_id, error=str(exc))
            item.reliability_score = item.source_reliability * 0.5
            item.reliability = NewsReliability.UNCONFIRMED

        return item

    async def check_batch(self, items: list[NewsItem]) -> list[NewsItem]:
        """Fact-check a list of news items sequentially with a delay between requests to avoid rate limits."""
        checked: list[NewsItem] = []
        for i, item in enumerate(items):
            checked.append(await self.check_item(item))
            # Задержка между запросами, чтобы не превысить лимит RPM (30/мин)
            # 1.5 секунды даёт ~40 запросов в минуту — комфортный запас
            if i < len(items) - 1:
                await asyncio.sleep(1.5)
        return checked

"""AnalyticsEngine — analyses publication performance and generates insights."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from football_bot.config.constants import SYSTEM_PROMPT_ANALYST
from football_bot.core.models.publication import Publication, PublicationFormat
from football_bot.repositories.publication_repository import PublicationRepository
from football_bot.services.mistral_service import MistralService
from football_bot.storage.schema import AnalyticsEventORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsEngine:
    """Collects and analyses channel performance metrics."""

    def __init__(
        self,
        publication_repository: PublicationRepository,
        mistral_service: MistralService,
        session_factory,
    ) -> None:
        self._pub_repo = publication_repository
        self._llm = mistral_service
        self._session_factory = session_factory

    async def record_publication_event(self, pub: Publication) -> None:
        if not pub.published_at:
            return
        try:
            async with self._session_factory() as session:
                event = AnalyticsEventORM(
                    pub_id=pub.pub_id,
                    format=pub.format.value,
                    league_code=pub.league_code,
                    published_at=pub.published_at,
                    hour_of_day=pub.published_at.hour,
                    day_of_week=pub.published_at.weekday(),
                    ai_quality_score=pub.ai_quality_score,
                    text_length=len(pub.text),
                )
                session.add(event)
                await session.commit()
        except Exception as exc:
            logger.warning("analytics_record_error", error=str(exc))

    def _compute_format_stats(self, publications: list[Publication]) -> dict[str, dict]:
        stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_score": 0.0, "avg_length": 0.0})
        format_lengths: dict[str, list[int]] = defaultdict(list)
        for pub in publications:
            key = pub.format.value
            stats[key]["count"] += 1
            stats[key]["total_score"] += pub.ai_quality_score or 0.0
            format_lengths[key].append(len(pub.text))
        for key in stats:
            if stats[key]["count"] > 0:
                stats[key]["avg_score"] = stats[key]["total_score"] / stats[key]["count"]
                lengths = format_lengths[key]
                stats[key]["avg_length"] = sum(lengths) / len(lengths) if lengths else 0
        return dict(stats)

    def _compute_hourly_distribution(self, publications: list[Publication]) -> dict[int, int]:
        dist: dict[int, int] = defaultdict(int)
        for pub in publications:
            if pub.published_at:
                dist[pub.published_at.hour] += 1
        return dict(sorted(dist.items()))

    def _compute_daily_distribution(self, publications: list[Publication]) -> dict[int, int]:
        dist: dict[int, int] = defaultdict(int)
        for pub in publications:
            if pub.published_at:
                dist[pub.published_at.weekday()] += 1
        return dict(sorted(dist.items()))

    async def compute_analytics_report(self, days: int = 30) -> dict[str, Any]:
        publications = await self._pub_repo.get_analytics_window(days=days)
        if not publications:
            return {"status": "no_data", "days": days}

        format_stats = self._compute_format_stats(publications)
        hourly = self._compute_hourly_distribution(publications)
        daily = self._compute_daily_distribution(publications)

        best_hour = max(hourly, key=hourly.get, default=12) if hourly else 12
        best_day = max(daily, key=daily.get, default=0) if daily else 0
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        report = {
            "period_days": days,
            "total_publications": len(publications),
            "format_breakdown": format_stats,
            "hourly_distribution": hourly,
            "daily_distribution": daily,
            "best_posting_hour_utc": best_hour,
            "best_posting_day": day_names[best_day],
            "generated_at": datetime.utcnow().isoformat(),
        }
        logger.info("analytics_computed", total=len(publications), days=days)
        return report

    async def generate_strategy_recommendations(self, report: dict[str, Any]) -> str:
        if report.get("status") == "no_data":
            return "Недостаточно данных для анализа. Накопите больше публикаций."

        prompt = f"""Проанализируй данные о публикациях футбольного Telegram-канала и дай конкретные рекомендации.

Данные за {report.get('period_days')} дней:
- Всего публикаций: {report.get('total_publications')}
- Лучшее время публикации: {report.get('best_posting_hour_utc')}:00 UTC
- Лучший день недели: {report.get('best_posting_day')}
- Распределение по форматам: {report.get('format_breakdown', {})}

Требования:
- Дай 5 конкретных, применимых рекомендаций
- Основывайся только на данных, не выдумывай
- Укажи, какие форматы работают лучше и почему
- Предложи оптимальное расписание публикаций
- 400–600 символов"""

        return await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_ANALYST,
            temperature=0.5,
            max_tokens=500,
        )

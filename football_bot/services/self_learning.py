"""SelfLearningModule — adjusts publication strategy based on analytics."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from football_bot.core.models.publication import PublicationFormat
from football_bot.services.analytics_engine import AnalyticsEngine
from football_bot.storage.schema import SelfLearningStateORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_STATE: dict[str, Any] = {
    "preferred_formats": [f.value for f in PublicationFormat],
    "preferred_leagues": ["UCL", "PL", "LL", "BL", "SA"],
    "best_posting_hours": [8, 12, 18, 21],
    "format_weights": {f.value: 1.0 for f in PublicationFormat},
    "league_weights": {},
    "min_reliability_override": None,
    "max_posts_per_run_override": None,
    "updated_at": None,
    "iteration": 0,
}


class SelfLearningModule:
    """Updates posting strategy based on analytics data.

    State is persisted to SQLite so it survives between GitHub Actions runs.
    """

    def __init__(
        self,
        analytics_engine: AnalyticsEngine,
        session_factory,
    ) -> None:
        self._analytics = analytics_engine
        self._session_factory = session_factory
        self._state: dict[str, Any] = dict(_DEFAULT_STATE)

    async def _load_state(self) -> None:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SelfLearningStateORM).where(SelfLearningStateORM.key == "main")
                )
                orm = result.scalar_one_or_none()
                if orm:
                    self._state = dict(_DEFAULT_STATE)
                    self._state.update(orm.value)
        except Exception as exc:
            logger.warning("self_learning_load_error", error=str(exc))

    async def _save_state(self) -> None:
        self._state["updated_at"] = datetime.utcnow().isoformat()
        self._state["iteration"] = self._state.get("iteration", 0) + 1
        try:
            async with self._session_factory() as session:
                stmt = insert(SelfLearningStateORM).values(
                    key="main",
                    value=self._state,
                    updated_at=datetime.utcnow(),
                ).on_conflict_do_update(
                    index_elements=["key"],
                    set_={"value": self._state, "updated_at": datetime.utcnow()},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:
            logger.warning("self_learning_save_error", error=str(exc))

    async def run_learning_cycle(self) -> dict[str, Any]:
        """Full learning cycle: load state → analyse → adjust → persist."""
        await self._load_state()

        report = await self._analytics.compute_analytics_report(days=30)
        if report.get("status") == "no_data":
            logger.info("self_learning_skipped", reason="no_data")
            return self._state

        format_stats: dict = report.get("format_breakdown", {})
        if format_stats:
            weights: dict[str, float] = {}
            for fmt, stats in format_stats.items():
                count = stats.get("count", 0)
                avg_score = stats.get("avg_score", 0.5)
                weights[fmt] = max(0.1, avg_score * (1.0 + min(count / 50.0, 1.0)))
            self._state["format_weights"] = weights
            top_formats = sorted(weights.items(), key=lambda x: x[1], reverse=True)
            self._state["preferred_formats"] = [f for f, _ in top_formats[:8]]

        hourly: dict = report.get("hourly_distribution", {})
        if hourly:
            top_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:4]
            self._state["best_posting_hours"] = sorted([h for h, _ in top_hours])

        await self._save_state()
        logger.info(
            "self_learning_complete",
            iteration=self._state.get("iteration"),
            preferred_formats=self._state.get("preferred_formats")[:3],
            best_hours=self._state.get("best_posting_hours"),
        )
        return self._state

    async def get_current_strategy(self) -> dict[str, Any]:
        await self._load_state()
        return self._state

    def get_format_priority(self, fmt: PublicationFormat) -> float:
        return self._state.get("format_weights", {}).get(fmt.value, 1.0)

    def get_preferred_leagues(self) -> list[str]:
        return self._state.get("preferred_leagues", ["UCL", "PL", "LL"])

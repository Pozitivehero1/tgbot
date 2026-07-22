"""StatsCollector — aggregates match and publication statistics for reporting."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from football_bot.repositories.match_repository import MatchRepository
from football_bot.repositories.publication_repository import PublicationRepository
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class StatsCollector:
    """Collects and exposes aggregate statistics for the channel."""

    def __init__(
        self,
        match_repository: MatchRepository,
        publication_repository: PublicationRepository,
    ) -> None:
        self._match_repo = match_repository
        self._pub_repo = publication_repository

    async def collect_match_stats(self, hours: int = 24) -> dict[str, Any]:
        """Aggregate match statistics for the last N hours."""
        matches = await self._match_repo.get_recent_finished(hours=hours)
        league_goals: dict[str, int] = defaultdict(int)
        total_goals = 0
        results: dict[str, int] = {"home_win": 0, "away_win": 0, "draw": 0}

        for match in matches:
            hg = match.home_score or 0
            ag = match.away_score or 0
            total_goals += hg + ag
            league_goals[match.league_code] += hg + ag
            if hg > ag:
                results["home_win"] += 1
            elif ag > hg:
                results["away_win"] += 1
            else:
                results["draw"] += 1

        avg_goals = total_goals / len(matches) if matches else 0.0
        return {
            "period_hours": hours,
            "matches_analysed": len(matches),
            "total_goals": total_goals,
            "average_goals_per_match": round(avg_goals, 2),
            "results_breakdown": results,
            "goals_by_league": dict(league_goals),
            "collected_at": datetime.utcnow().isoformat(),
        }

    async def collect_channel_stats(self, days: int = 7) -> dict[str, Any]:
        """Aggregate channel publishing statistics for the last N days."""
        publications = await self._pub_repo.get_analytics_window(days=days)
        format_counts: dict[str, int] = defaultdict(int)
        daily_counts: dict[str, int] = defaultdict(int)

        for pub in publications:
            format_counts[pub.format.value] += 1
            if pub.published_at:
                day_key = pub.published_at.strftime("%Y-%m-%d")
                daily_counts[day_key] += 1

        total = len(publications)
        avg_per_day = total / days if days > 0 else 0.0
        return {
            "period_days": days,
            "total_publications": total,
            "average_per_day": round(avg_per_day, 1),
            "by_format": dict(format_counts),
            "by_day": dict(sorted(daily_counts.items())),
            "collected_at": datetime.utcnow().isoformat(),
        }

    async def build_performance_summary(self) -> str:
        """Build a human-readable performance summary string."""
        match_stats = await self.collect_match_stats(hours=168)
        channel_stats = await self.collect_channel_stats(days=7)

        return (
            f"📊 Статистика канала за 7 дней\n\n"
            f"Публикаций: {channel_stats['total_publications']}\n"
            f"В среднем в день: {channel_stats['average_per_day']}\n\n"
            f"Матчей отслежено: {match_stats['matches_analysed']}\n"
            f"Голов всего: {match_stats['total_goals']}\n"
            f"Голов за матч: {match_stats['average_goals_per_match']}\n\n"
            f"Форматы публикаций:\n"
            + "\n".join(f"  • {k}: {v}" for k, v in channel_stats["by_format"].items())
        )

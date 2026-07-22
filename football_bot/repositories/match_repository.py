"""SQLAlchemy implementation of AbstractMatchRepository."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import orjson
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from football_bot.core.interfaces.repository import AbstractMatchRepository
from football_bot.core.models.match import Match, MatchStatus, MatchEvent, MatchStatistics, TeamLineup, PlayerStats
from football_bot.repositories.base import BaseRepository
from football_bot.storage.schema import MatchORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_LIVE_STATUSES = {
    MatchStatus.LIVE.value,
    MatchStatus.HALF_TIME.value,
    MatchStatus.EXTRA_TIME.value,
    MatchStatus.PENALTY_SHOOTOUT.value,
    MatchStatus.LINEUP_ANNOUNCED.value,
}


class MatchRepository(BaseRepository, AbstractMatchRepository):

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    @staticmethod
    def _orm_to_model(orm: MatchORM) -> Match:
        def _parse_events(raw: list | None) -> list[MatchEvent]:
            if not raw:
                return []
            return [MatchEvent(**e) for e in raw]

        def _parse_stats(raw: dict | None) -> Optional[MatchStatistics]:
            if not raw:
                return None
            return MatchStatistics(**raw)

        def _parse_lineup(raw: dict | None) -> Optional[TeamLineup]:
            if not raw:
                return None
            return TeamLineup(**raw)

        def _parse_player_stats(raw: list | None) -> list[PlayerStats]:
            if not raw:
                return []
            return [PlayerStats(**p) for p in raw]

        return Match(
            match_id=orm.match_id,
            league_code=orm.league_code,
            league_name=orm.league_name or "",
            round_label=orm.round_label or "",
            home_team=orm.home_team,
            away_team=orm.away_team,
            home_score=orm.home_score,
            away_score=orm.away_score,
            home_score_ht=orm.home_score_ht,
            away_score_ht=orm.away_score_ht,
            home_score_et=orm.home_score_et,
            away_score_et=orm.away_score_et,
            home_score_pen=orm.home_score_pen,
            away_score_pen=orm.away_score_pen,
            status=MatchStatus(orm.status),
            kickoff_time=orm.kickoff_time,
            current_minute=orm.current_minute,
            venue=orm.venue or "",
            referee=orm.referee or "",
            attendance=orm.attendance,
            events=_parse_events(orm.events),
            statistics=_parse_stats(orm.statistics),
            home_lineup=_parse_lineup(orm.home_lineup),
            away_lineup=_parse_lineup(orm.away_lineup),
            player_stats=_parse_player_stats(orm.player_stats),
            best_player=orm.best_player,
            source=orm.source or "",
            fetched_at=orm.fetched_at or datetime.utcnow(),
            live_published_events=orm.live_published_events or [],
        )

    @staticmethod
    def _model_to_orm(match: Match) -> MatchORM:
        return MatchORM(
            match_id=match.match_id,
            league_code=match.league_code,
            league_name=match.league_name,
            round_label=match.round_label,
            home_team=match.home_team,
            away_team=match.away_team,
            home_score=match.home_score,
            away_score=match.away_score,
            home_score_ht=match.home_score_ht,
            away_score_ht=match.away_score_ht,
            home_score_et=match.home_score_et,
            away_score_et=match.away_score_et,
            home_score_pen=match.home_score_pen,
            away_score_pen=match.away_score_pen,
            status=match.status.value,
            kickoff_time=match.kickoff_time,
            current_minute=match.current_minute,
            venue=match.venue,
            referee=match.referee,
            attendance=match.attendance,
            events=[e.model_dump() for e in match.events],
            statistics=match.statistics.model_dump() if match.statistics else None,
            home_lineup=match.home_lineup.model_dump() if match.home_lineup else None,
            away_lineup=match.away_lineup.model_dump() if match.away_lineup else None,
            player_stats=[p.model_dump() for p in match.player_stats],
            best_player=match.best_player,
            source=match.source,
            fetched_at=match.fetched_at,
            live_published_events=match.live_published_events,
        )

    async def save(self, match: Match) -> None:
        async with self._session_factory() as session:
            existing = await session.get(MatchORM, match.match_id)
            orm = self._model_to_orm(match)
            if existing:
                for field, value in orm.__dict__.items():
                    if not field.startswith("_"):
                        setattr(existing, field, value)
            else:
                session.add(orm)
            await session.commit()

    async def get_by_id(self, match_id: str) -> Optional[Match]:
        async with self._session_factory() as session:
            orm = await session.get(MatchORM, match_id)
            return self._orm_to_model(orm) if orm else None

    async def get_live(self) -> list[Match]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(MatchORM).where(MatchORM.status.in_(list(_LIVE_STATUSES)))
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def get_upcoming(self, hours_ahead: int = 48) -> list[Match]:
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours_ahead)
        async with self._session_factory() as session:
            result = await session.execute(
                select(MatchORM)
                .where(
                    MatchORM.kickoff_time >= now,
                    MatchORM.kickoff_time <= cutoff,
                    MatchORM.status == MatchStatus.SCHEDULED.value,
                )
                .order_by(MatchORM.kickoff_time.asc())
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def get_recent_finished(self, hours: int = 24) -> list[Match]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        async with self._session_factory() as session:
            result = await session.execute(
                select(MatchORM)
                .where(
                    MatchORM.status == MatchStatus.FINISHED.value,
                    MatchORM.kickoff_time >= cutoff,
                )
                .order_by(MatchORM.kickoff_time.desc())
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def update_status(self, match_id: str, status: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(MatchORM)
                .where(MatchORM.match_id == match_id)
                .values(status=status)
            )
            await session.commit()

    async def save_live_event(self, match_id: str, event_type: str) -> None:
        async with self._session_factory() as session:
            orm = await session.get(MatchORM, match_id)
            if orm:
                published = list(orm.live_published_events or [])
                if event_type not in published:
                    published.append(event_type)
                    await session.execute(
                        update(MatchORM)
                        .where(MatchORM.match_id == match_id)
                        .values(live_published_events=published)
                    )
                    await session.commit()

    async def get_published_events(self, match_id: str) -> list[str]:
        async with self._session_factory() as session:
            orm = await session.get(MatchORM, match_id)
            return list(orm.live_published_events or []) if orm else []

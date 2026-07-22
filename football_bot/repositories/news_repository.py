"""SQLAlchemy implementation of AbstractNewsRepository."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from football_bot.core.interfaces.repository import AbstractNewsRepository
from football_bot.core.models.news import NewsItem, NewsCategory, NewsReliability
from football_bot.repositories.base import BaseRepository
from football_bot.storage.schema import NewsItemORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class NewsRepository(BaseRepository, AbstractNewsRepository):
    """Persists and retrieves NewsItem objects using SQLite."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    @staticmethod
    def _orm_to_model(orm: NewsItemORM) -> NewsItem:
        return NewsItem(
            item_id=orm.item_id,
            source_name=orm.source_name,
            source_url=orm.source_url,
            article_url=orm.article_url,
            title=orm.title,
            summary=orm.summary or "",
            full_text=orm.full_text or "",
            language=orm.language or "en",
            category=NewsCategory(orm.category) if orm.category else NewsCategory.GENERAL,
            reliability=NewsReliability(orm.reliability) if orm.reliability else NewsReliability.UNCONFIRMED,
            reliability_score=orm.reliability_score or 0.0,
            reliability_reasoning=orm.reliability_reasoning or "",
            red_flags=orm.red_flags or [],
            published_at=orm.published_at,
            fetched_at=orm.fetched_at or datetime.utcnow(),
            teams_mentioned=orm.teams_mentioned or [],
            players_mentioned=orm.players_mentioned or [],
            leagues_mentioned=orm.leagues_mentioned or [],
            tags=orm.tags or [],
            is_duplicate=orm.is_duplicate or False,
            duplicate_of=orm.duplicate_of,
            was_published=orm.was_published or False,
            source_reliability=orm.source_reliability or 0.8,
            corroborating_sources=orm.corroborating_sources or [],
            corroboration_count=orm.corroboration_count or 1,
            content_vector=orm.content_vector,
        )

    @staticmethod
    def _model_to_orm(item: NewsItem) -> NewsItemORM:
        return NewsItemORM(
            item_id=item.item_id,
            source_name=item.source_name,
            source_url=item.source_url,
            article_url=item.article_url,
            title=item.title,
            summary=item.summary,
            full_text=item.full_text,
            language=item.language,
            category=item.category.value,
            reliability=item.reliability.value,
            reliability_score=item.reliability_score,
            reliability_reasoning=item.reliability_reasoning,
            red_flags=item.red_flags,
            published_at=item.published_at,
            fetched_at=item.fetched_at,
            teams_mentioned=item.teams_mentioned,
            players_mentioned=item.players_mentioned,
            leagues_mentioned=item.leagues_mentioned,
            tags=item.tags,
            is_duplicate=item.is_duplicate,
            duplicate_of=item.duplicate_of,
            was_published=item.was_published,
            source_reliability=item.source_reliability,
            corroborating_sources=item.corroborating_sources,
            corroboration_count=item.corroboration_count,
            content_vector=item.content_vector,
        )

    async def save(self, item: NewsItem) -> None:
        async with self._session_factory() as session:
            existing = await session.get(NewsItemORM, item.item_id)
            if existing:
                for field, value in self._model_to_orm(item).__dict__.items():
                    if not field.startswith("_"):
                        setattr(existing, field, value)
            else:
                session.add(self._model_to_orm(item))
            await session.commit()

    async def get_by_id(self, item_id: str) -> Optional[NewsItem]:
        async with self._session_factory() as session:
            orm = await session.get(NewsItemORM, item_id)
            return self._orm_to_model(orm) if orm else None

    async def get_recent(self, hours: int = 24, limit: int = 100) -> list[NewsItem]:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        async with self._session_factory() as session:
            result = await session.execute(
                select(NewsItemORM)
                .where(NewsItemORM.published_at >= cutoff)
                .order_by(NewsItemORM.published_at.desc())
                .limit(limit)
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def get_unpublished(
        self,
        min_reliability: float = 0.6,
        limit: int = 20,
    ) -> list[NewsItem]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(NewsItemORM)
                .where(
                    NewsItemORM.was_published == False,  # noqa: E712
                    NewsItemORM.is_duplicate == False,  # noqa: E712
                    NewsItemORM.reliability_score >= min_reliability,
                )
                .order_by(NewsItemORM.reliability_score.desc())
                .limit(limit)
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def mark_published(self, item_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(NewsItemORM)
                .where(NewsItemORM.item_id == item_id)
                .values(was_published=True)
            )
            await session.commit()

    async def mark_duplicate(self, item_id: str, duplicate_of: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(NewsItemORM)
                .where(NewsItemORM.item_id == item_id)
                .values(is_duplicate=True, duplicate_of=duplicate_of)
            )
            await session.commit()

    async def exists(self, item_id: str) -> bool:
        async with self._session_factory() as session:
            orm = await session.get(NewsItemORM, item_id)
            return orm is not None

    async def update_reliability(
        self,
        item_id: str,
        score: float,
        reliability: NewsReliability,
        reasoning: str,
        red_flags: list[str],
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(NewsItemORM)
                .where(NewsItemORM.item_id == item_id)
                .values(
                    reliability_score=score,
                    reliability=reliability.value,
                    reliability_reasoning=reasoning,
                    red_flags=red_flags,
                )
            )
            await session.commit()

    async def get_all_vectors(self) -> list[tuple[str, list[float]]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(NewsItemORM.item_id, NewsItemORM.content_vector).where(
                    NewsItemORM.content_vector.isnot(None)
                )
            )
            return [(row.item_id, row.content_vector) for row in result.all()]

    async def update_vector(self, item_id: str, vector: list[float]) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(NewsItemORM)
                .where(NewsItemORM.item_id == item_id)
                .values(content_vector=vector)
            )
            await session.commit()

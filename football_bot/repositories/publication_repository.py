"""SQLAlchemy implementation of AbstractPublicationRepository."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from football_bot.core.interfaces.repository import AbstractPublicationRepository
from football_bot.core.models.publication import (
    Publication,
    PublicationFormat,
    PublicationMetrics,
    PublicationStatus,
)
from football_bot.repositories.base import BaseRepository
from football_bot.storage.schema import PublicationORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class PublicationRepository(BaseRepository, AbstractPublicationRepository):

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    @staticmethod
    def _orm_to_model(orm: PublicationORM) -> Publication:
        metrics = None
        if orm.metrics:
            metrics = PublicationMetrics(**orm.metrics)
        return Publication(
            pub_id=orm.pub_id,
            format=PublicationFormat(orm.format),
            status=PublicationStatus(orm.status),
            title=orm.title or "",
            text=orm.text,
            image_path=orm.image_path,
            source_item_ids=orm.source_item_ids or [],
            league_code=orm.league_code,
            match_id=orm.match_id,
            telegram_message_id=orm.telegram_message_id,
            published_at=orm.published_at,
            created_at=orm.created_at or datetime.utcnow(),
            scheduled_for=orm.scheduled_for,
            ai_quality_score=orm.ai_quality_score or 0.0,
            reliability_score=orm.reliability_score or 0.0,
            estimated_length=orm.estimated_length or 0,
            metrics=metrics,
            model_used=orm.model_used or "",
            generation_prompt_hash=orm.generation_prompt_hash or "",
            generation_duration_seconds=orm.generation_duration_seconds or 0.0,
        )

    @staticmethod
    def _model_to_orm(pub: Publication) -> PublicationORM:
        return PublicationORM(
            pub_id=pub.pub_id,
            format=pub.format.value,
            status=pub.status.value,
            title=pub.title,
            text=pub.text,
            image_path=pub.image_path,
            source_item_ids=pub.source_item_ids,
            league_code=pub.league_code,
            match_id=pub.match_id,
            telegram_message_id=pub.telegram_message_id,
            published_at=pub.published_at,
            created_at=pub.created_at,
            scheduled_for=pub.scheduled_for,
            ai_quality_score=pub.ai_quality_score,
            reliability_score=pub.reliability_score,
            estimated_length=len(pub.text),
            metrics=pub.metrics.model_dump() if pub.metrics else None,
            model_used=pub.model_used,
            generation_prompt_hash=pub.generation_prompt_hash,
            generation_duration_seconds=pub.generation_duration_seconds,
        )

    async def save(self, pub: Publication) -> None:
        async with self._session_factory() as session:
            existing = await session.get(PublicationORM, pub.pub_id)
            orm = self._model_to_orm(pub)
            if existing:
                for field, value in orm.__dict__.items():
                    if not field.startswith("_"):
                        setattr(existing, field, value)
            else:
                session.add(orm)
            await session.commit()

    async def get_by_id(self, pub_id: str) -> Optional[Publication]:
        async with self._session_factory() as session:
            orm = await session.get(PublicationORM, pub_id)
            return self._orm_to_model(orm) if orm else None

    async def get_recent(self, limit: int = 50) -> list[Publication]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublicationORM)
                .order_by(PublicationORM.created_at.desc())
                .limit(limit)
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def get_by_format(self, fmt: PublicationFormat, limit: int = 10) -> list[Publication]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublicationORM)
                .where(PublicationORM.format == fmt.value)
                .order_by(PublicationORM.created_at.desc())
                .limit(limit)
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def get_pending(self) -> list[Publication]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublicationORM).where(
                    PublicationORM.status == PublicationStatus.READY.value
                )
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def update_status(self, pub_id: str, status: PublicationStatus) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(PublicationORM)
                .where(PublicationORM.pub_id == pub_id)
                .values(status=status.value)
            )
            await session.commit()

    async def update_message_id(self, pub_id: str, message_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(PublicationORM)
                .where(PublicationORM.pub_id == pub_id)
                .values(
                    telegram_message_id=message_id,
                    status=PublicationStatus.PUBLISHED.value,
                    published_at=datetime.utcnow(),
                )
            )
            await session.commit()

    async def get_analytics_window(self, days: int = 30) -> list[Publication]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with self._session_factory() as session:
            result = await session.execute(
                select(PublicationORM)
                .where(
                    PublicationORM.status == PublicationStatus.PUBLISHED.value,
                    PublicationORM.published_at >= cutoff,
                )
                .order_by(PublicationORM.published_at.desc())
            )
            return [self._orm_to_model(row) for row in result.scalars().all()]

    async def count_today(self) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count(PublicationORM.pub_id)).where(
                    PublicationORM.published_at >= today,
                    PublicationORM.status == PublicationStatus.PUBLISHED.value,
                )
            )
            return result.scalar_one() or 0

"""Base repository with common helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class BaseRepository:
    """Provides a session factory to concrete repositories."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        return self._session_factory()

"""Database manager — async SQLite via SQLAlchemy 2.0 + aiosqlite."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from football_bot.storage.schema import Base
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages the async SQLite connection pool and schema lifecycle."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialise(self) -> None:
        """Create the engine, run migrations, and prepare the session factory."""
        os.makedirs(os.path.dirname(self._database_path) or ".", exist_ok=True)
        db_url = f"sqlite+aiosqlite:///{self._database_path}"
        self._engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info("database_initialised", path=self._database_path)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("database_closed")

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield an async session as an async context manager."""
        if self._session_factory is None:
            raise RuntimeError("DatabaseManager.initialise() must be called first.")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("DatabaseManager.initialise() must be called first.")
        return self._session_factory


_database_manager: DatabaseManager | None = None


def get_database_manager(database_path: str | None = None) -> DatabaseManager:
    """Return the singleton DatabaseManager, creating it if needed."""
    global _database_manager
    if _database_manager is None:
        if database_path is None:
            from football_bot.config.settings import get_settings
            database_path = get_settings().database_path
        _database_manager = DatabaseManager(database_path)
    return _database_manager

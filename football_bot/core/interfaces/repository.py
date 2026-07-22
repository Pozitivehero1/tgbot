"""Abstract repository interfaces — Repository Pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from football_bot.core.models.news import NewsItem, NewsReliability
from football_bot.core.models.match import Match
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus


class AbstractNewsRepository(ABC):
    """Contract for news storage operations."""

    @abstractmethod
    async def save(self, item: NewsItem) -> None: ...

    @abstractmethod
    async def get_by_id(self, item_id: str) -> Optional[NewsItem]: ...

    @abstractmethod
    async def get_recent(self, hours: int = 24, limit: int = 100) -> list[NewsItem]: ...

    @abstractmethod
    async def get_unpublished(
        self,
        min_reliability: float = 0.6,
        limit: int = 20,
    ) -> list[NewsItem]: ...

    @abstractmethod
    async def mark_published(self, item_id: str) -> None: ...

    @abstractmethod
    async def mark_duplicate(self, item_id: str, duplicate_of: str) -> None: ...

    @abstractmethod
    async def exists(self, item_id: str) -> bool: ...

    @abstractmethod
    async def update_reliability(
        self,
        item_id: str,
        score: float,
        reliability: NewsReliability,
        reasoning: str,
        red_flags: list[str],
    ) -> None: ...

    @abstractmethod
    async def get_all_vectors(self) -> list[tuple[str, list[float]]]: ...

    @abstractmethod
    async def update_vector(self, item_id: str, vector: list[float]) -> None: ...


class AbstractMatchRepository(ABC):
    """Contract for match storage operations."""

    @abstractmethod
    async def save(self, match: Match) -> None: ...

    @abstractmethod
    async def get_by_id(self, match_id: str) -> Optional[Match]: ...

    @abstractmethod
    async def get_live(self) -> list[Match]: ...

    @abstractmethod
    async def get_upcoming(self, hours_ahead: int = 48) -> list[Match]: ...

    @abstractmethod
    async def get_recent_finished(self, hours: int = 24) -> list[Match]: ...

    @abstractmethod
    async def update_status(self, match_id: str, status: str) -> None: ...

    @abstractmethod
    async def save_live_event(self, match_id: str, event_type: str) -> None: ...

    @abstractmethod
    async def get_published_events(self, match_id: str) -> list[str]: ...


class AbstractPublicationRepository(ABC):
    """Contract for publication storage operations."""

    @abstractmethod
    async def save(self, pub: Publication) -> None: ...

    @abstractmethod
    async def get_by_id(self, pub_id: str) -> Optional[Publication]: ...

    @abstractmethod
    async def get_recent(self, limit: int = 50) -> list[Publication]: ...

    @abstractmethod
    async def get_by_format(self, fmt: PublicationFormat, limit: int = 10) -> list[Publication]: ...

    @abstractmethod
    async def get_pending(self) -> list[Publication]: ...

    @abstractmethod
    async def update_status(self, pub_id: str, status: PublicationStatus) -> None: ...

    @abstractmethod
    async def update_message_id(self, pub_id: str, message_id: int) -> None: ...

    @abstractmethod
    async def get_analytics_window(self, days: int = 30) -> list[Publication]: ...

    @abstractmethod
    async def count_today(self) -> int: ...

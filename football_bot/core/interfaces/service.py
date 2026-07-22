"""Abstract service interfaces — Service Layer contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from football_bot.core.models.news import NewsItem
from football_bot.core.models.publication import Publication, PublicationFormat


class AbstractLLMService(ABC):
    """Contract for LLM interaction — implemented by MistralService."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str: ...

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class AbstractParserService(ABC):
    """Contract for news parsers."""

    @abstractmethod
    async def fetch(self, url: str) -> list[NewsItem]: ...

    @abstractmethod
    async def fetch_all(self, urls: list[str]) -> list[NewsItem]: ...

    @property
    @abstractmethod
    def source_name(self) -> str: ...


class AbstractPublisherService(ABC):
    """Contract for Telegram publisher."""

    @abstractmethod
    async def publish_text(self, text: str, parse_mode: str = "HTML") -> int: ...

    @abstractmethod
    async def publish_photo(self, photo_path: str, caption: str) -> int: ...

    @abstractmethod
    async def publish_publication(self, pub: Publication) -> int: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

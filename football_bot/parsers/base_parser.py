"""Base async HTTP parser with retry, fallback user-agents, and error isolation."""

from __future__ import annotations

import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from football_bot.config.constants import HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENTS
from football_bot.core.models.news import NewsItem
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


def make_item_id(url: str, title: str) -> str:
    """Generate a stable unique ID from article URL + title."""
    content = f"{url}|{title}"
    return hashlib.sha256(content.encode()).hexdigest()[:24]


class BaseParser(ABC):
    """Shared HTTP infrastructure for all parsers."""

    def __init__(self, timeout: float = HTTP_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": random.choice(HTTP_USER_AGENTS)},
                follow_redirects=True,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fetch_raw(self, url: str) -> Optional[str]:
        """Fetch raw text from a URL with retries and a random user-agent."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(HTTP_MAX_RETRIES),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type(
                    (httpx.TransportError, httpx.TimeoutException, httpx.ConnectError)
                ),
                reraise=False,
            ):
                with attempt:
                    client = await self._get_client()
                    response = await client.get(url)
                    if response.status_code == 404:
                        logger.warning("parser_404", url=url)
                        return None
                    response.raise_for_status()
                    return response.text
        except Exception as exc:
            logger.warning("parser_fetch_failed", url=url, error=str(exc))
            return None

   async def _fetch_bytes(self, url: str) -> Optional[bytes]:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(HTTP_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(
                (httpx.TransportError, httpx.TimeoutException, httpx.ConnectError)
            ),
            reraise=False,
        ):
            with attempt:
                client = await self._get_client()
                response = await client.get(url)

                if response.status_code == 404:
                    logger.warning("parser_404", url=url)
                    return None

                response.raise_for_status()
                return response.content

    except Exception as exc:
        logger.warning("parser_bytes_failed", url=url, error=str(exc))
        return None

    @abstractmethod
    async def fetch(self, url: str) -> list[NewsItem]: ...

    async def fetch_all(self, urls: list[str]) -> list[NewsItem]:
        """Fetch all URLs concurrently, isolating failures per source."""
        tasks = [self.fetch(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: list[NewsItem] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.warning("parser_source_failed", url=url, error=str(result))
            elif isinstance(result, list):
                items.extend(result)
        return items

    @property
    @abstractmethod
    def source_name(self) -> str: ...

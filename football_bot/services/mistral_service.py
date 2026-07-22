"""MistralService — единственный LLM-провайдер для всей системы.

Поддерживает:
- повторные попытки с экспоненциальным backoff
- таймауты
- автоматическое переключение моделей
- ограничение скорости (rate limiting)
- кэширование ответов в SQLite
- очередь запросов через asyncio.Semaphore
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from football_bot.config.settings import get_settings
from football_bot.core.interfaces.service import AbstractLLMService
from football_bot.storage.schema import LLMCacheORM
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_MISTRAL_API_BASE = "https://api.mistral.ai/v1"


class MistralRateLimitError(Exception):
    """Raised when the Mistral API returns 429 Too Many Requests."""


class MistralServiceError(Exception):
    """Raised for unrecoverable Mistral API errors."""


class MistralService(AbstractLLMService):
    """Full-featured async Mistral AI client with caching, rate limiting, and failover."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        rate_limit_rpm: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
        session_factory=None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.mistral_api_key
        self._model = model or settings.mistral_model
        self._fallback_model = fallback_model or settings.mistral_fallback_model
        self._timeout = timeout or settings.mistral_timeout
        self._max_retries = max_retries or settings.mistral_max_retries
        self._rate_limit_rpm = rate_limit_rpm or settings.mistral_rate_limit_rpm
        self._cache_ttl = cache_ttl_seconds or settings.mistral_cache_ttl_seconds
        self._session_factory = session_factory

        # Rate limiting via a semaphore — max concurrent requests bounded by RPM/60
        max_concurrent = max(1, self._rate_limit_rpm // 10)
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Track request timestamps for rolling-window rate limiting
        self._request_timestamps: list[float] = []
        self._request_lock = asyncio.Lock()

        self._http_client: Optional[httpx.AsyncClient] = None

        # In-memory LRU cache layer (prompt_hash → (response, expires_at))
        self._memory_cache: dict[str, tuple[str, float]] = {}
        self._memory_cache_max_size = 256

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=_MISTRAL_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Rate limiting ─────────────────────────────────────────────────────────

    async def _wait_for_rate_limit(self) -> None:
        async with self._request_lock:
            now = time.monotonic()
            window_start = now - 60.0
            self._request_timestamps = [ts for ts in self._request_timestamps if ts > window_start]
            if len(self._request_timestamps) >= self._rate_limit_rpm:
                oldest = self._request_timestamps[0]
                wait_time = 60.0 - (now - oldest) + 0.1
                if wait_time > 0:
                    logger.info("rate_limit_wait", seconds=round(wait_time, 2))
                    await asyncio.sleep(wait_time)
            self._request_timestamps.append(time.monotonic())

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _prompt_hash(self, prompt: str, system_prompt: str, model: str) -> str:
        content = f"{model}||{system_prompt}||{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_from_memory_cache(self, cache_key: str) -> Optional[str]:
        entry = self._memory_cache.get(cache_key)
        if entry and entry[1] > time.monotonic():
            return entry[0]
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        return None

    def _set_memory_cache(self, cache_key: str, response: str) -> None:
        if len(self._memory_cache) >= self._memory_cache_max_size:
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
        self._memory_cache[cache_key] = (response, time.monotonic() + self._cache_ttl)

    async def _get_from_db_cache(self, cache_key: str) -> Optional[str]:
        if self._session_factory is None:
            return None
        try:
            async with self._session_factory() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(LLMCacheORM).where(
                        LLMCacheORM.prompt_hash == cache_key,
                        LLMCacheORM.expires_at > datetime.utcnow(),
                    )
                )
                orm = result.scalar_one_or_none()
                if orm:
                    from sqlalchemy import update
                    await session.execute(
                        update(LLMCacheORM)
                        .where(LLMCacheORM.prompt_hash == cache_key)
                        .values(hit_count=LLMCacheORM.hit_count + 1)
                    )
                    await session.commit()
                    return orm.response_text
        except Exception as exc:
            logger.warning("db_cache_read_error", error=str(exc))
        return None

    async def _set_db_cache(self, cache_key: str, response: str, model: str) -> None:
        if self._session_factory is None:
            return
        try:
            async with self._session_factory() as session:
                orm = LLMCacheORM(
                    prompt_hash=cache_key,
                    response_text=response,
                    model=model,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(seconds=self._cache_ttl),
                    hit_count=0,
                )
                from sqlalchemy.dialects.sqlite import insert
                stmt = insert(LLMCacheORM).values(
                    prompt_hash=orm.prompt_hash,
                    response_text=orm.response_text,
                    model=orm.model,
                    created_at=orm.created_at,
                    expires_at=orm.expires_at,
                    hit_count=orm.hit_count,
                ).on_conflict_do_update(
                    index_elements=["prompt_hash"],
                    set_={"response_text": orm.response_text, "expires_at": orm.expires_at},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as exc:
            logger.warning("db_cache_write_error", error=str(exc))

    # ── Core generation ───────────────────────────────────────────────────────

    async def _call_api(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        client = await self._get_http_client()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = await client.post("/chat/completions", json=payload)
        if response.status_code == 429:
            raise MistralRateLimitError("Mistral API rate limit exceeded")
        if response.status_code == 503:
            raise MistralServiceError("Mistral API service unavailable")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        cache_key = self._prompt_hash(prompt, system_prompt, self._model)

        cached = self._get_from_memory_cache(cache_key)
        if cached:
            logger.debug("llm_cache_hit", source="memory")
            return cached

        cached = await self._get_from_db_cache(cache_key)
        if cached:
            logger.debug("llm_cache_hit", source="db")
            self._set_memory_cache(cache_key, cached)
            return cached

        await self._wait_for_rate_limit()

        start = time.monotonic()
        last_error: Optional[Exception] = None

        for model_candidate in [self._model, self._fallback_model]:
            try:
                async with self._semaphore:
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(self._max_retries),
                        wait=wait_exponential(multiplier=2, min=2, max=30),
                        retry=retry_if_exception_type(
                            (httpx.TransportError, httpx.TimeoutException, MistralRateLimitError)
                        ),
                        reraise=True,
                    ):
                        with attempt:
                            response_text = await self._call_api(
                                prompt=prompt,
                                system_prompt=system_prompt,
                                model=model_candidate,
                                temperature=temperature,
                                max_tokens=max_tokens,
                            )

                duration = time.monotonic() - start
                logger.info(
                    "llm_generated",
                    model=model_candidate,
                    duration=round(duration, 2),
                    tokens_approx=len(response_text.split()),
                )
                self._set_memory_cache(cache_key, response_text)
                await self._set_db_cache(cache_key, response_text, model_candidate)
                return response_text

            except MistralServiceError as exc:
                last_error = exc
                logger.warning("llm_model_failed", model=model_candidate, error=str(exc))
                continue
            except Exception as exc:
                last_error = exc
                logger.error("llm_generation_error", model=model_candidate, error=str(exc))
                if model_candidate == self._fallback_model:
                    raise MistralServiceError(f"Both models failed. Last error: {exc}") from exc
                continue

        raise MistralServiceError(f"All model candidates exhausted. Last error: {last_error}")

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        json_system = system_prompt + "\n\nОтветь ТОЛЬКО валидным JSON без пояснений и markdown-блоков."
        raw = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature,
            max_tokens=1024,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise MistralServiceError(f"Failed to parse JSON from LLM response: {raw[:300]}")

    async def health_check(self) -> bool:
        try:
            client = await self._get_http_client()
            response = await client.get("/models", timeout=10.0)
            return response.status_code == 200
        except Exception as exc:
            logger.warning("mistral_health_check_failed", error=str(exc))
            return False

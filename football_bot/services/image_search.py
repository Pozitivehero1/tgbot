"""ImageSearchService — searches for real photos via Unsplash API."""

from __future__ import annotations

import httpx
from typing import Optional

from football_bot.config.settings import get_settings
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

UNSPLASH_API_BASE = "https://api.unsplash.com"


class ImageSearchService:
    """Fetches real photos from Unsplash based on query."""

    def __init__(self, access_key: Optional[str] = None) -> None:
        settings = get_settings()
        self._access_key = access_key or settings.unsplash_access_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "Authorization": f"Client-ID {self._access_key}",
            }
            self._client = httpx.AsyncClient(
                base_url=UNSPLASH_API_BASE,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def search_photo(self, query: str, orientation: str = "landscape") -> Optional[str]:
        """Search for a photo and return the first result's regular URL."""
        if not self._access_key:
            logger.warning("unsplash_no_api_key")
            return None

        try:
            client = await self._get_client()
            response = await client.get(
                "/search/photos",
                params={
                    "query": query,
                    "orientation": orientation,
                    "per_page": 1,
                },
            )
            if response.status_code != 200:
                logger.warning("unsplash_search_failed", status=response.status_code, query=query)
                return None

            data = response.json()
            results = data.get("results", [])
            if not results:
                logger.info("unsplash_no_result", query=query)
                return None

            photo_url = results[0].get("urls", {}).get("regular")
            if photo_url:
                logger.info("unsplash_photo_found", query=query, url=photo_url[:80])
                return photo_url
            return None

        except Exception as exc:
            logger.warning("unsplash_error", error=str(exc), query=query)
            return None

    async def search_club_emblem(self, club_name: str) -> Optional[str]:
        return await self.search_photo(f"{club_name} football club logo", orientation="landscape")

    async def search_player_photo(self, player_name: str) -> Optional[str]:
        return await self.search_photo(f"{player_name} football player portrait", orientation="portrait")

    async def search_match_photo(self, home_team: str, away_team: str) -> Optional[str]:
        return await self.search_photo(f"{home_team} vs {away_team} football match", orientation="landscape")

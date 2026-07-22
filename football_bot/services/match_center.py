"""MatchCenter — fetches upcoming and recent matches from open sources."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from football_bot.core.models.match import Match, MatchStatus
from football_bot.repositories.match_repository import MatchRepository
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"


def _make_match_id(home: str, away: str, kickoff: str) -> str:
    return hashlib.sha256(f"{home}|{away}|{kickoff}".encode()).hexdigest()[:16]


class MatchCenter:
    """Fetches match schedule and results from football-data.org (free tier)."""

    def __init__(
        self,
        match_repository: MatchRepository,
        api_token: str = "",
    ) -> None:
        self._repo = match_repository
        self._api_token = api_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self._api_token:
                headers["X-Auth-Token"] = self._api_token
            self._client = httpx.AsyncClient(
                base_url=_FOOTBALL_DATA_BASE,
                headers=headers,
                timeout=20.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fetch_matches(self, endpoint: str) -> list[dict]:
        try:
            client = await self._get_client()
            response = await client.get(endpoint)
            if response.status_code == 429:
                logger.warning("match_center_rate_limited", endpoint=endpoint)
                return []
            if response.status_code != 200:
                logger.warning("match_center_http_error", status=response.status_code)
                return []
            data = response.json()
            return data.get("matches", [])
        except Exception as exc:
            logger.warning("match_center_fetch_error", error=str(exc))
            return []

    @staticmethod
    def _parse_match(raw: dict) -> Match | None:
        try:
            home = raw.get("homeTeam", {}).get("name", "Unknown")
            away = raw.get("awayTeam", {}).get("name", "Unknown")
            kickoff_str = raw.get("utcDate", "")
            if not kickoff_str:
                return None
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
            kickoff = kickoff.replace(tzinfo=None)
            competition = raw.get("competition", {})
            score_raw = raw.get("score", {})
            ft = score_raw.get("fullTime", {})
            ht = score_raw.get("halfTime", {})
            status_str = raw.get("status", "SCHEDULED").upper()
            status_map = {
                "SCHEDULED": MatchStatus.SCHEDULED,
                "TIMED": MatchStatus.SCHEDULED,
                "IN_PLAY": MatchStatus.LIVE,
                "PAUSED": MatchStatus.HALF_TIME,
                "FINISHED": MatchStatus.FINISHED,
                "POSTPONED": MatchStatus.POSTPONED,
                "CANCELLED": MatchStatus.CANCELLED,
                "SUSPENDED": MatchStatus.ABANDONED,
            }
            status = status_map.get(status_str, MatchStatus.SCHEDULED)
            match_id = str(raw.get("id", _make_match_id(home, away, kickoff_str)))
            return Match(
                match_id=match_id,
                league_code=str(competition.get("code", "UNK")),
                league_name=str(competition.get("name", "")),
                home_team=home,
                away_team=away,
                home_score=ft.get("home"),
                away_score=ft.get("away"),
                home_score_ht=ht.get("home"),
                away_score_ht=ht.get("away"),
                status=status,
                kickoff_time=kickoff,
                venue=raw.get("venue", ""),
                source="football-data.org",
            )
        except Exception as exc:
            logger.warning("match_parse_error", error=str(exc))
            return None

    async def fetch_today_matches(self) -> list[Match]:
        raw_matches = await self._fetch_matches("/matches?dateFrom=today&dateTo=today")
        matches: list[Match] = []
        for raw in raw_matches:
            match = self._parse_match(raw)
            if match:
                await self._repo.save(match)
                matches.append(match)
        logger.info("today_matches_fetched", count=len(matches))
        return matches

    async def fetch_upcoming_matches(self, competition_code: str = "CL") -> list[Match]:
        raw_matches = await self._fetch_matches(f"/competitions/{competition_code}/matches?status=SCHEDULED")
        matches: list[Match] = []
        for raw in raw_matches[:20]:
            match = self._parse_match(raw)
            if match:
                await self._repo.save(match)
                matches.append(match)
        return matches

    async def fetch_recent_results(self, competition_code: str = "CL") -> list[Match]:
        raw_matches = await self._fetch_matches(f"/competitions/{competition_code}/matches?status=FINISHED")
        matches: list[Match] = []
        for raw in raw_matches[:10]:
            match = self._parse_match(raw)
            if match:
                await self._repo.save(match)
                matches.append(match)
        return matches

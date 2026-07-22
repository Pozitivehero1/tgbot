"""StandingsGenerator — fetches league tables and generates posts."""

from __future__ import annotations

from football_bot.config.constants import LEAGUES, SYSTEM_PROMPT_EDITOR
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus
from football_bot.core.models.standing import StandingsTable
from football_bot.parsers.html_parser import HTMLParser
from football_bot.services.ai_editor import _make_pub_id
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_STANDINGS_SOURCES: dict[str, str] = {
    "PL": "https://fbref.com/en/comps/9/Premier-League-Stats",
    "LL": "https://fbref.com/en/comps/12/La-Liga-Stats",
    "BL": "https://fbref.com/en/comps/20/Bundesliga-Stats",
    "SA": "https://fbref.com/en/comps/11/Serie-A-Stats",
    "L1": "https://fbref.com/en/comps/13/Ligue-1-Stats",
}


class StandingsGenerator:
    """Fetches standings and creates formatted Telegram posts."""

    def __init__(
        self,
        html_parser: HTMLParser,
        mistral_service: MistralService,
    ) -> None:
        self._parser = html_parser
        self._llm = mistral_service

    def _format_table_text(self, table: StandingsTable, top_n: int = 10) -> str:
        league = LEAGUES.get(table.league_code, {})
        emoji = league.get("emoji", "⚽")
        league_name = league.get("name", table.league_code)
        lines = [f"{emoji} <b>{league_name}</b>\n"]
        for s in table.top(top_n):
            zone = ""
            if s.is_champions_league:
                zone = "🔵"
            elif s.is_europa_league:
                zone = "🟠"
            elif s.is_relegation:
                zone = "🔴"
            lines.append(
                f"{zone}{s.position:2}. {s.team_name:<22} {s.played:2} {s.points:3}pts"
                f"  {s.goals_display}  {s.goal_difference:+d}"
            )
        return "\n".join(lines)

    async def fetch_standings(self, league_code: str) -> StandingsTable | None:
        url = _STANDINGS_SOURCES.get(league_code)
        if not url:
            logger.warning("no_standings_source", league=league_code)
            return None
        table = await self._parser.parse_standings_from_html(url, league_code)
        if table:
            logger.info("standings_fetched", league=league_code, teams=len(table.standings))
        return table

    async def generate_standings_post(self, league_code: str) -> Publication | None:
        table = await self.fetch_standings(league_code)
        if not table or not table.standings:
            return None

        table_text = self._format_table_text(table)
        league = LEAGUES.get(league_code, {})
        prompt = f"""Напиши короткий комментарий к турнирной таблице {league.get('name', league_code)} для Telegram-канала.

Таблица (топ-10):
{table_text}

Требования:
- 200–400 символов комментария (таблицу не повторяй, она будет добавлена отдельно)
- Отметь текущего лидера, интригу в борьбе за еврокубки или зону вылета
- Стиль живой, экспертный
- Хэштеги"""

        commentary = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=0.7,
            max_tokens=300,
        )

        full_text = f"<pre>{table_text}</pre>\n\n{commentary}"
        return Publication(
            pub_id=_make_pub_id("standings" + league_code),
            format=PublicationFormat.STANDINGS,
            status=PublicationStatus.READY,
            title=f"Таблица: {league.get('name', league_code)}",
            text=full_text,
            league_code=league_code,
            model_used=self._llm._model,
        )

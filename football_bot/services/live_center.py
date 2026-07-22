"""LiveCenter — generates real-time match event posts for Telegram."""

from __future__ import annotations

from football_bot.config.constants import SYSTEM_PROMPT_EDITOR
from football_bot.core.models.match import Match, MatchEvent, MatchStatus
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus
from football_bot.repositories.match_repository import MatchRepository
from football_bot.services.ai_editor import _make_pub_id
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_EVENT_EMOJIS = {
    "goal": "⚽️",
    "own_goal": "🤦",
    "penalty_scored": "🎯",
    "penalty_missed": "❌",
    "red_card": "🟥",
    "yellow_card": "🟨",
    "second_yellow": "🟨🟥",
    "substitution": "🔄",
    "var_check": "📺",
    "var_overturned": "📺❌",
    "injury": "🏥",
    "half_time": "🔔",
    "full_time": "🏁",
    "extra_time_start": "⏱️",
    "extra_time_end": "🏁",
    "penalty_shootout_start": "🎯",
    "penalty_shootout_end": "🏆",
    "lineup_announced": "📋",
    "match_start": "🚀",
    "best_player": "⭐️",
}


class LiveCenter:
    """Generates live match update publications from match events."""

    def __init__(
        self,
        match_repository: MatchRepository,
        mistral_service: MistralService,
    ) -> None:
        self._repo = match_repository
        self._llm = mistral_service

    def _build_score_header(self, match: Match) -> str:
        return f"{match.home_team} {match.score_display} {match.away_team}"

    async def generate_lineup_post(self, match: Match) -> Publication:
        home_xi = ", ".join(match.home_lineup.starting_xi) if match.home_lineup else "не объявлен"
        away_xi = ", ".join(match.away_lineup.starting_xi) if match.away_lineup else "не объявлен"
        home_form = match.home_lineup.formation if match.home_lineup else ""
        away_form = match.away_lineup.formation if match.away_lineup else ""
        text = (
            f"📋 <b>СОСТАВЫ</b>\n\n"
            f"<b>{match.home_team}</b> ({home_form})\n{home_xi}\n\n"
            f"<b>{match.away_team}</b> ({away_form})\n{away_xi}\n\n"
            f"⚽ {match.league_name} | {match.kickoff_time.strftime('%H:%M')} UTC"
        )
        return Publication(
            pub_id=_make_pub_id(match.match_id + "lineup"),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"Составы: {match.home_team} vs {match.away_team}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used="template",
        )

    async def generate_goal_post(self, match: Match, event: MatchEvent) -> Publication:
        emoji = _EVENT_EMOJIS.get(event.event_type, "⚽️")
        scorer = event.player_name or "Неизвестный"
        assist = f" (пас: {event.player_assist})" if event.player_assist else ""
        minute = f"{event.minute}'" if event.minute else ""
        prompt = f"""Напиши короткий live-пост о голе для Telegram-канала.

Матч: {self._build_score_header(match)}
Событие: {event.event_type}
Автор: {scorer}{assist}
Минута: {minute}
Команда: {event.team or 'неизвестно'}

Требования:
- 150–300 символов
- Начни с {emoji}
- Передай эмоцию момента
- Укажи текущий счёт жирным
- НЕ добавляй хэштеги"""

        text = await self._llm.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT_EDITOR, temperature=0.9, max_tokens=200)
        return Publication(
            pub_id=_make_pub_id(match.match_id + "goal" + (event.player_name or "") + str(event.minute)),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"Гол! {self._build_score_header(match)}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used=self._llm._model,
        )

    async def generate_card_post(self, match: Match, event: MatchEvent) -> Publication:
        emoji = _EVENT_EMOJIS.get(event.event_type, "🟨")
        card_type = "Красная карточка" if "red" in event.event_type else "Жёлтая карточка"
        player = event.player_name or "игрок"
        minute = f"{event.minute}'" if event.minute else ""
        text = (
            f"{emoji} <b>{card_type.upper()}</b>\n\n"
            f"<b>{player}</b> ({event.team or match.home_team}) — {minute}\n\n"
            f"<b>{self._build_score_header(match)}</b>"
        )
        return Publication(
            pub_id=_make_pub_id(match.match_id + event.event_type + player),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"{card_type}: {player}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used="template",
        )

    async def generate_halftime_post(self, match: Match) -> Publication:
        text = (
            f"🔔 <b>ПЕРЕРЫВ</b>\n\n"
            f"<b>{match.home_team} {match.score_display} {match.away_team}</b>\n\n"
            f"Первый тайм завершён. "
            f"Слежу за матчем — продолжение через 15 минут."
        )
        return Publication(
            pub_id=_make_pub_id(match.match_id + "halftime"),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"Перерыв: {self._build_score_header(match)}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used="template",
        )

    async def generate_fulltime_post(self, match: Match) -> Publication:
        stats = match.statistics
        stats_line = ""
        if stats:
            stats_line = (
                f"\n\n📊 Владение: {stats.home_possession:.0f}%–{stats.away_possession:.0f}%"
                f" | Удары: {stats.home_shots}–{stats.away_shots}"
                f" | xG: {stats.home_xg:.1f}–{stats.away_xg:.1f}"
            )
        best = f"\n⭐️ Лучший игрок: <b>{match.best_player}</b>" if match.best_player else ""
        text = (
            f"🏁 <b>ФИНАЛЬНЫЙ СВИСТОК</b>\n\n"
            f"<b>{match.home_team} {match.score_display} {match.away_team}</b>\n"
            f"{match.league_name}"
            f"{stats_line}"
            f"{best}"
        )
        return Publication(
            pub_id=_make_pub_id(match.match_id + "fulltime"),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"Итог: {self._build_score_header(match)}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used="template",
        )

    async def generate_substitution_post(self, match: Match, event: MatchEvent) -> Publication:
        player_in = event.player_name or "?"
        player_out = event.player_assist or "?"
        minute = f"{event.minute}'" if event.minute else ""
        text = (
            f"🔄 <b>Замена</b> ({minute})\n"
            f"Вышел: <b>{player_in}</b>\n"
            f"Ушёл: {player_out}\n"
            f"Команда: {event.team or '—'}\n\n"
            f"<b>{self._build_score_header(match)}</b>"
        )
        return Publication(
            pub_id=_make_pub_id(match.match_id + "sub" + player_in),
            format=PublicationFormat.LIVE_UPDATE,
            status=PublicationStatus.READY,
            title=f"Замена: {player_in}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used="template",
        )

    async def process_new_events(self, match: Match) -> list[Publication]:
        """Generate publications for all unpublished events in a match."""
        published_events = await self._repo.get_published_events(match.match_id)
        publications: list[Publication] = []

        for event in match.events:
            event_key = f"{event.event_type}_{event.minute}_{event.player_name}"
            if event_key in published_events:
                continue

            pub: Publication | None = None
            if event.event_type in {"goal", "own_goal", "penalty_scored", "penalty_missed"}:
                pub = await self.generate_goal_post(match, event)
            elif event.event_type in {"red_card", "yellow_card", "second_yellow"}:
                pub = await self.generate_card_post(match, event)
            elif event.event_type == "half_time":
                pub = await self.generate_halftime_post(match)
            elif event.event_type == "full_time":
                pub = await self.generate_fulltime_post(match)
            elif event.event_type == "substitution":
                pub = await self.generate_substitution_post(match, event)
            elif event.event_type == "lineup_announced":
                pub = await self.generate_lineup_post(match)

            if pub:
                publications.append(pub)
                await self._repo.save_live_event(match.match_id, event_key)

        return publications

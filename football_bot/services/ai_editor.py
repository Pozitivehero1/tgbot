"""AIEditor — generates all publication texts via Mistral AI.

Handles: breaking news, transfer posts, match previews/reports,
daily/weekly/monthly digests, interesting facts, historical posts, analysis.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime
from typing import Optional

from football_bot.config.constants import SYSTEM_PROMPT_EDITOR
from football_bot.core.models.match import Match
from football_bot.core.models.news import NewsItem
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus
from football_bot.core.models.standing import StandingsTable
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


def _make_pub_id(content: str) -> str:
    return hashlib.sha256(f"{time.time()}{content}".encode()).hexdigest()[:16]


class AIEditor:
    """Creates Publication objects with AI-generated text for every content format."""

    def __init__(self, mistral_service: MistralService) -> None:
        self._llm = mistral_service

    async def _generate(self, prompt: str, temperature: float = 0.75, max_tokens: int = 1500) -> tuple[str, str]:
        start = time.monotonic()
        text = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        duration = time.monotonic() - start
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return text, prompt_hash

    # ── Breaking / transfer news ───────────────────────────────────────────────

    async def write_breaking_news(self, item: NewsItem) -> Publication:
        prompt = f"""Напиши пост для Telegram-канала о футбольной новости.

Заголовок оригинала: {item.title}
Краткое содержание: {item.summary[:800]}
Источник: {item.source_name}
Достоверность: {item.reliability.value} (оценка: {item.reliability_score:.0%})

Требования:
- Максимум 600 символов
- Начни с яркого эмодзи и захватывающего заголовка
- Изложи суть коротко, фактически, без лишних слов
- В конце добавь хэштеги (не более 3)
- НЕ копируй текст источника — только рерайт фактов"""

        text, prompt_hash = await self._generate(prompt, temperature=0.8, max_tokens=400)
        return Publication(
            pub_id=_make_pub_id(item.item_id),
            format=PublicationFormat.BREAKING_NEWS,
            status=PublicationStatus.READY,
            title=item.title,
            text=text,
            source_item_ids=[item.item_id],
            league_code=next(iter(item.leagues_mentioned), None),
            reliability_score=item.reliability_score,
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    async def write_transfer_news(self, item: NewsItem) -> Publication:
        prompt = f"""Напиши пост о трансфере для Telegram-канала.

Заголовок: {item.title}
Детали: {item.summary[:800]}
Источник: {item.source_name}

Требования:
- 300–600 символов
- Структура: 🔄 [Заголовок] → детали сделки → реакция/контекст → хэштеги
- Укажи участвующие клубы, сумму если известна, длительность контракта
- Добавь экспертный комментарий (1 предложение)
- НЕ выдумывай цифры, которых нет в источнике"""

        text, prompt_hash = await self._generate(prompt, temperature=0.75)
        return Publication(
            pub_id=_make_pub_id(item.item_id + "transfer"),
            format=PublicationFormat.TRANSFER_NEWS,
            status=PublicationStatus.READY,
            title=item.title,
            text=text,
            source_item_ids=[item.item_id],
            reliability_score=item.reliability_score,
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    # ── Match content ──────────────────────────────────────────────────────────

    async def write_match_preview(self, match: Match, context_items: list[NewsItem]) -> Publication:
        context_text = "\n".join(f"- {i.title}" for i in context_items[:5])
        prompt = f"""Напиши превью матча для Telegram-канала.

Матч: {match.home_team} vs {match.away_team}
Турнир: {match.league_name} — {match.round_label}
Время: {match.kickoff_time.strftime('%d.%m.%Y %H:%M')} UTC
Стадион: {match.venue or 'не указан'}

Контекст из последних новостей:
{context_text or 'нет дополнительного контекста'}

Требования:
- 800–1200 символов
- Структура: интригующий вступ → форма команд → ключевые игроки → тактический аспект → прогноз
- Напиши живо, как опытный аналитик
- Добавь эмодзи команд и хэштеги"""

        text, prompt_hash = await self._generate(prompt, temperature=0.8, max_tokens=800)
        return Publication(
            pub_id=_make_pub_id(match.match_id + "preview"),
            format=PublicationFormat.MATCH_PREVIEW,
            status=PublicationStatus.READY,
            title=f"{match.home_team} vs {match.away_team}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    async def write_match_report(self, match: Match) -> Publication:
        events_text = "\n".join(
            f"  {e.minute}' {e.event_type}: {e.player_name or ''} ({e.team or ''})"
            for e in match.events
        ) or "Событий нет"
        stats = match.statistics
        stats_text = ""
        if stats:
            stats_text = f"""
Владение: {stats.home_possession:.0f}% — {stats.away_possession:.0f}%
Удары: {stats.home_shots} — {stats.away_shots}
В створ: {stats.home_shots_on_target} — {stats.away_shots_on_target}
xG: {stats.home_xg:.1f} — {stats.away_xg:.1f}"""

        prompt = f"""Напиши репортаж о завершённом матче для Telegram-канала.

Матч: {match.home_team} {match.score_display} {match.away_team}
Турнир: {match.league_name} — {match.round_label}
Результат: {match.result_label}
Лучший игрок: {match.best_player or 'не определён'}

Ключевые события:
{events_text}
{stats_text}

Требования:
- 1000–1500 символов
- Структура: счёт и результат → ход матча → ключевые моменты → статистика → вывод
- Стиль — профессиональная спортивная журналистика
- Добавь хэштеги"""

        text, prompt_hash = await self._generate(prompt, temperature=0.7, max_tokens=1000)
        return Publication(
            pub_id=_make_pub_id(match.match_id + "report"),
            format=PublicationFormat.MATCH_REPORT,
            status=PublicationStatus.READY,
            title=f"Итог: {match.home_team} {match.score_display} {match.away_team}",
            text=text,
            match_id=match.match_id,
            league_code=match.league_code,
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    # ── Digests ────────────────────────────────────────────────────────────────

    async def write_daily_digest(self, items: list[NewsItem], matches: list[Match]) -> Publication:
        news_text = "\n".join(f"• {i.title}" for i in items[:10])
        match_text = "\n".join(
            f"• {m.home_team} {m.score_display} {m.away_team} ({m.league_name})"
            for m in matches[:8]
        )
        prompt = f"""Напиши ежедневный дайджест для футбольного Telegram-канала.

Главные новости за сегодня:
{news_text or 'Новостей нет'}

Результаты матчей:
{match_text or 'Матчей нет'}

Требования:
- 1000–1800 символов
- Стиль: живой редакционный обзор, не сухой список
- Выдели самое важное, добавь контекст
- Структура: вступ → топ-новость → остальные новости → результаты → заключение
- Добавь хэштеги #дайджест"""

        text, prompt_hash = await self._generate(prompt, temperature=0.75, max_tokens=1200)
        return Publication(
            pub_id=_make_pub_id("daily" + datetime.utcnow().strftime("%Y%m%d")),
            format=PublicationFormat.DAILY_DIGEST,
            status=PublicationStatus.READY,
            title=f"Дайджест {datetime.utcnow().strftime('%d.%m.%Y')}",
            text=text,
            source_item_ids=[i.item_id for i in items],
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    async def write_weekly_digest(self, items: list[NewsItem], matches: list[Match]) -> Publication:
        top_news = "\n".join(f"• {i.title}" for i in items[:15])
        top_matches = "\n".join(
            f"• {m.home_team} {m.score_display} {m.away_team}" for m in matches[:12]
        )
        prompt = f"""Напиши еженедельный обзор для футбольного Telegram-канала.

Главные события недели:
{top_news}

Важнейшие матчи:
{top_matches}

Требования:
- 2000–3000 символов
- Стиль: редакционный аналитический обзор
- Раздели на секции: Трансферы, Результаты, Главная история недели, Цифра недели, Что смотреть на следующей неделе
- Добавь хэштеги #итогинедели"""

        text, prompt_hash = await self._generate(prompt, temperature=0.7, max_tokens=2000)
        return Publication(
            pub_id=_make_pub_id("weekly" + datetime.utcnow().strftime("%Y%W")),
            format=PublicationFormat.WEEKLY_DIGEST,
            status=PublicationStatus.READY,
            title="Итоги недели",
            text=text,
            source_item_ids=[i.item_id for i in items],
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

    async def write_monthly_digest(self, items: list[NewsItem], matches: list[Match]) -> Publication:
        top_news = "\n".join(f"• {i.title}" for i in items[:20])
        top_matches = "\n".join(
            f"• {m.home_team} {m.score_display} {m.away_team} ({m.league_name})" for m in matches[:15]
        )
        month_name = datetime.utcnow().strftime("%B %Y")
        prompt = f"""Напиши месячный обзор для футбольного Telegram-канала.

Месяц: {month_name}

Главные новости месяца:
{top_news}

Лучшие матчи:
{top_matches}

Требования:
- 3000–4000 символов
- Стиль: журналистский ежемесячный отчёт высокого уровня
- Разделы: Событие месяца, Трансферы, Статистика, Матч месяца, Разочарование месяца, Герой месяца, Прогноз на следующий месяц
- Добавь хэштеги #итогимесяца"""

        text, prompt_hash = await self._generate(prompt, temperature=0.7, max_tokens=2500)
        return Publication(
            pub_id=_make_pub_id("monthly" + datetime.utcnow().strftime("%Y%m")),
            format=PublicationFormat.MONTHLY_DIGEST,
            status=PublicationStatus.READY,
            title=f"Итоги месяца: {month_name}",
            text=text,
            source_item_ids=[i.item_id for i in items],
            model_used=self._llm._model,
            generation_prompt_hash=prompt_hash,
        )

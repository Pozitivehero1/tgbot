"""HistoryGenerator — generates historical football posts for today's date."""

from __future__ import annotations

from datetime import datetime

from football_bot.config.constants import LEAGUES, SYSTEM_PROMPT_EDITOR
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus
from football_bot.services.ai_editor import _make_pub_id
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class HistoryGenerator:
    """Generates 'On this day in football history' posts using Mistral."""

    def __init__(self, mistral_service: MistralService) -> None:
        self._llm = mistral_service

    async def generate_on_this_day(self) -> Publication:
        today = datetime.utcnow()
        day_month = today.strftime("%d %B")
        prompt = f"""Напиши пост «В этот день в истории футбола» для Telegram-канала.

Дата: {day_month}

Задача:
- Найди реальные исторические события в футболе, произошедшие {day_month} (в любой год)
- Выбери 1–2 самых ярких события: великие матчи, рекорды, знаковые трансферы, рождения легенд
- Напиши увлекательно, как историю — не просто факт, а контекст и значение события

Требования:
- 600–1000 символов
- Начни с эмодзи 📅 и заголовка
- Добавь исторический контекст
- Заверши хэштегами #историяфутбола #вэтотдень"""

        text = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=0.8,
            max_tokens=700,
        )
        return Publication(
            pub_id=_make_pub_id("history" + today.strftime("%m%d")),
            format=PublicationFormat.HISTORICAL_POST,
            status=PublicationStatus.READY,
            title=f"В этот день — {day_month}",
            text=text,
            model_used=self._llm._model,
        )

    async def generate_club_history(self, club_name: str) -> Publication:
        prompt = f"""Напиши исторический пост о футбольном клубе {club_name} для Telegram-канала.

Содержание:
- Дата основания и история создания
- Самые великие достижения и трофеи
- Легендарные игроки всех времён (3–5 имён)
- Наиболее запоминающийся сезон или матч
- Современное положение клуба

Требования:
- 1200–1800 символов
- Стиль: захватывающий нарратив, не Википедия
- Добавь хэштеги с названием клуба"""

        text = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=0.75,
            max_tokens=1200,
        )
        return Publication(
            pub_id=_make_pub_id("club_" + club_name),
            format=PublicationFormat.HISTORICAL_POST,
            status=PublicationStatus.READY,
            title=f"История клуба: {club_name}",
            text=text,
            model_used=self._llm._model,
        )

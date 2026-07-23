"""InterestingFactsGenerator — generates trivia and statistical curiosities."""

from __future__ import annotations

import random
from datetime import datetime

from football_bot.config.constants import LEAGUES, SYSTEM_PROMPT_EDITOR
from football_bot.core.models.publication import Publication, PublicationFormat, PublicationStatus
from football_bot.services.ai_editor import _make_pub_id
from football_bot.services.mistral_service import MistralService
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_FACT_TOPICS = [
    "самые необычные рекорды в истории Лиги чемпионов",
    "невероятные камбэки в истории футбола",
    "самые быстрые голы в истории крупнейших лиг",
    "футболисты, игравшие за пять и более клубов в топ-5 лигах",
    "самые дорогие трансферы всех времён и окупились ли они",
    "вратари, забивавшие голы в официальных матчах",
    "самые возрастные и самые молодые игроки в истории топ-лиг",
    "рекордные победы и поражения в истории футбола",
    "игроки, выигравшие все клубные и национальные трофеи",
    "самые зрелищные матчи в истории чемпионатов мира",
    "нереализованные пенальти в ключевых матчах",
    "тренеры, выигрывавшие Лигу чемпионов с несколькими клубами",
    "игроки с максимальным числом чемпионских титулов",
    "самые длинные беспроигрышные серии в истории футбола",
    "легенды, завершившие карьеру в неожиданных клубах",
]


class FactsGenerator:
    """Generates interesting football facts and trivia posts."""

    def __init__(self, mistral_service: MistralService) -> None:
        self._llm = mistral_service

    async def generate_interesting_fact(self, topic: str | None = None) -> Publication:
        selected_topic = topic or random.choice(_FACT_TOPICS)
        prompt = f"""Напиши пост с интересным фактом о футболе для Telegram-канала.

Тема: {selected_topic}

Требования:
- Текст должен быть ровно 400–700 символов (не больше 700, не меньше 400). Проверь длину перед отправкой.
- Начни с эмодзи 🤯 или ⚡️ и цепляющего факта
- Добавь контекст — почему это удивительно?
- Факт должен быть реальным и проверяемым
- Заверши призывом обсудить в комментариях
- НЕ используй Markdown (звёздочки, подчёркивания)
- НЕ добавляй хэштеги
- НЕ используй HTML-теги (запрещены <b>, <i> и любые другие)
- Пиши компактно, только суть, без лишней воды
- Если факт слишком длинный, перефразируй его короче, сохранив главное"""

        text = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=0.85,
            max_tokens=450,
        )

        # Проверяем длину и при необходимости просим сократить
        if len(text) > 700:
            logger.warning("fact_too_long", length=len(text), topic=selected_topic)
            # Второй запрос на сокращение
            shorten_prompt = f"Сократи следующий текст до 600–700 символов, сохранив главное:\n\n{text}"
            text = await self._llm.generate(
                prompt=shorten_prompt,
                system_prompt=SYSTEM_PROMPT_EDITOR,
                temperature=0.7,
                max_tokens=400,
            )
            if len(text) > 700:
                # Если всё ещё длинный, обрезаем с многоточием
                text = text[:697] + "..."

        return Publication(
            pub_id=_make_pub_id("fact" + selected_topic[:20]),
            format=PublicationFormat.INTERESTING_FACT,
            status=PublicationStatus.READY,
            title=f"Факт: {selected_topic[:50]}",
            text=text,
            model_used=self._llm._model,
        )

    async def generate_statistical_curiosity(self, data_context: str) -> Publication:
        prompt = f"""Напиши пост с удивительной статистикой для футбольного Telegram-канала.

Данные для анализа:
{data_context}

Требования:
- Найди самый удивительный, нетривиальный вывод из этих данных
- 400–600 символов
- Начни с числа или неожиданного факта
- Объясни, почему это поразительно
- НЕ используй Markdown (звёздочки, подчёркивания)
- НЕ добавляй хэштеги
- НЕ используй HTML-теги
- Пиши компактно, не более 600 символов
- Если статистика требует больше слов, перефразируй короче"""

        text = await self._llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_EDITOR,
            temperature=0.7,
            max_tokens=350,
        )

        if len(text) > 600:
            text = text[:597] + "..."

        return Publication(
            pub_id=_make_pub_id("stat" + data_context[:20]),
            format=PublicationFormat.STATISTICS,
            status=PublicationStatus.READY,
            title="Статистика дня",
            text=text,
            model_used=self._llm._model,
        )

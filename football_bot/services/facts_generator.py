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
        target_min = 500
        target_max = 700

        # Пробуем сгенерировать текст с нужной длиной
        text = await self._generate_fact_with_length(selected_topic, target_min, target_max)

        return Publication(
            pub_id=_make_pub_id("fact" + selected_topic[:20]),
            format=PublicationFormat.INTERESTING_FACT,
            status=PublicationStatus.READY,
            title=f"Факт: {selected_topic[:50]}",
            text=text,
            model_used=self._llm._model,
        )

    async def _generate_fact_with_length(self, topic: str, min_len: int, max_len: int, max_attempts: int = 3) -> str:
        """Генерирует факт с контролем длины, при необходимости перегенерирует."""
        for attempt in range(max_attempts):
            prompt = f"""Напиши пост с интересным фактом о футболе для Telegram-канала.

Тема: {topic}

Важно: текст должен быть ровно от {min_len} до {max_len} символов. Не больше и не меньше.
Проверь длину перед отправкой.

Требования:
- Начни с эмодзи 🤯 или ⚡️ и цепляющего факта
- Добавь контекст — почему это удивительно?
- Факт должен быть реальным и проверяемым
- Заверши призывом обсудить в комментариях
- НЕ используй Markdown (звёздочки, подчёркивания)
- НЕ используй HTML-теги (<b>, <i> и т.п.)
- НЕ добавляй хэштеги
- Пиши только суть, без лишней воды"""

            text = await self._llm.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_EDITOR,
                temperature=0.85,
                max_tokens=450,
            )

            # Удаляем возможные HTML-теги (на всякий случай)
            import re
            text = re.sub(r'<[^>]+>', '', text)

            if min_len <= len(text) <= max_len:
                logger.info("fact_generated", length=len(text), topic=topic, attempt=attempt)
                return text
            else:
                logger.warning("fact_length_mismatch", length=len(text), attempt=attempt, topic=topic)
                # Если слишком короткий, попросим дополнить
                if len(text) < min_len:
                    prompt = f"Дополни следующий текст до {min_len} символов, добавь контекст или детали:\n\n{text}"
                else:
                    prompt = f"Сократи следующий текст до {max_len} символов, сохранив главное:\n\n{text}"
                text = await self._llm.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT_EDITOR,
                    temperature=0.7,
                    max_tokens=400,
                )
                text = re.sub(r'<[^>]+>', '', text)
                if min_len <= len(text) <= max_len:
                    return text

        # Если после всех попыток не получилось, возвращаем последнюю версию, но обрезаем до max_len
        logger.error("fact_length_failed", topic=topic)
        if len(text) > max_len:
            text = text[:max_len-3] + "..."
        return text

    async def generate_statistical_curiosity(self, data_context: str) -> Publication:
        target_min = 400
        target_max = 600
        text = await self._generate_fact_with_length(data_context, target_min, target_max)
        return Publication(
            pub_id=_make_pub_id("stat" + data_context[:20]),
            format=PublicationFormat.STATISTICS,
            status=PublicationStatus.READY,
            title="Статистика дня",
            text=text,
            model_used=self._llm._model,
        )

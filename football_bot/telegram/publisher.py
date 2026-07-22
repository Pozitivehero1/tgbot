"""TelegramPublisher — sends messages and photos to the Telegram channel."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile

from football_bot.config.settings import get_settings
from football_bot.core.interfaces.service import AbstractPublisherService
from football_bot.core.models.publication import Publication
from football_bot.telegram.formatter import TelegramFormatter
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPublisher(AbstractPublisherService):
    """Sends publications to a Telegram channel via aiogram 3.x Bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._bot_token = bot_token or settings.bot_token
        self._channel_id = channel_id or settings.channel_id
        self._publication_delay = settings.publication_delay_seconds
        self._bot: Optional[Bot] = None
        self._formatter = TelegramFormatter()

    async def _get_bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=self._bot_token)
        return self._bot

    async def close(self) -> None:
        if self._bot:
            await self._bot.session.close()
            self._bot = None

    async def _send_with_retry(self, coro, max_retries: int = 3) -> Optional[int]:
        """Execute a send coroutine with rate-limit handling and exponential backoff."""
        for attempt in range(max_retries):
            try:
                message = await coro()
                return message.message_id
            except TelegramRetryAfter as exc:
                wait = exc.retry_after + 1
                logger.warning("telegram_rate_limit", retry_after=wait, attempt=attempt)
                await asyncio.sleep(wait)
            except TelegramBadRequest as exc:
                logger.error("telegram_bad_request", error=str(exc))
                return None
            except TelegramForbiddenError as exc:
                logger.error("telegram_forbidden", error=str(exc))
                return None
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("telegram_send_error", error=str(exc), attempt=attempt, wait=wait)
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    logger.error("telegram_send_failed_permanently", error=str(exc))
                    return None
        return None

    async def publish_text(self, text: str, parse_mode: str = "HTML") -> int:
        """Send a plain text message to the channel."""
        formatted = self._formatter.format_message(text)
        bot = await self._get_bot()

        async def _send():
            return await bot.send_message(
                chat_id=self._channel_id,
                text=formatted,
                parse_mode=ParseMode.HTML if parse_mode == "HTML" else parse_mode,
                disable_web_page_preview=False,
            )

        message_id = await self._send_with_retry(_send)
        if message_id:
            logger.info("telegram_text_sent", message_id=message_id, length=len(formatted))
        return message_id or 0

    async def publish_photo(self, photo_path: str, caption: str) -> int:
        """Send a photo with a caption to the channel."""
        formatted_caption = self._formatter.format_caption(caption)
        bot = await self._get_bot()

        if not os.path.exists(photo_path):
            logger.warning("photo_not_found", path=photo_path)
            return await self.publish_text(caption)

        photo_input = FSInputFile(photo_path)

        async def _send():
            return await bot.send_photo(
                chat_id=self._channel_id,
                photo=photo_input,
                caption=formatted_caption,
                parse_mode=ParseMode.HTML,
            )

        message_id = await self._send_with_retry(_send)
        if message_id:
            logger.info("telegram_photo_sent", message_id=message_id, path=photo_path)
        return message_id or 0

    async def publish_publication(self, pub: Publication) -> int:
        """High-level: send a Publication (with or without image) to the channel."""
        if pub.has_image and pub.image_path and os.path.exists(pub.image_path):
            return await self.publish_photo(pub.image_path, pub.text)
        return await self.publish_text(pub.text)

    async def health_check(self) -> bool:
        try:
            bot = await self._get_bot()
            me = await bot.get_me()
            return bool(me.id)
        except Exception as exc:
            logger.warning("telegram_health_check_failed", error=str(exc))
            return False

    async def publish_batch(self, publications: list[Publication]) -> list[int]:
        """Send a list of publications with the configured delay between them."""
        message_ids: list[int] = []
        for i, pub in enumerate(publications):
            msg_id = await self.publish_publication(pub)
            message_ids.append(msg_id)
            pub.mark_published(msg_id) if msg_id else pub.mark_failed()
            if i < len(publications) - 1:
                await asyncio.sleep(self._publication_delay)
        return message_ids

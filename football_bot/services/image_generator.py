"""ImageGenerator — creates card images programmatically using Pillow."""

from __future__ import annotations

import os
import textwrap
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont

from football_bot.config.constants import CARD_COLORS, FONT_SIZES
from football_bot.config.settings import get_settings
from football_bot.core.models.match import Match
from football_bot.core.models.news import NewsItem
from football_bot.core.models.publication import Publication, PublicationFormat
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)

_FALLBACK_FONT_SIZE = 36


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class ImageGenerator:
    """Generates card images for Telegram publications using Pillow."""

    def __init__(self, image_search_service=None) -> None:
        settings = get_settings()
        self._output_dir = Path(settings.images_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._width = settings.card_width
        self._height = settings.card_height
        self._image_search = image_search_service  # опционально

    def _save_image(self, image: Image.Image, name: str) -> str:
        path = self._output_dir / f"{name}.jpg"
        image.save(str(path), "JPEG", quality=92, optimize=True)
        logger.info("image_saved", path=str(path))
        return str(path)

    async def _download_image(self, url: str, dest_path: Path) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(dest_path, 'wb') as f:
                            f.write(await response.read())
                        logger.info("image_downloaded", path=str(dest_path))
                        return str(dest_path)
                    else:
                        logger.warning("image_download_failed", status=response.status, url=url)
                        return None
        except Exception as exc:
            logger.warning("image_download_error", error=str(exc), url=url)
            return None

    async def get_photo_for_publication(self, pub: Publication, source_item: Optional[NewsItem] = None, match: Optional[Match] = None) -> Optional[str]:
        """Попытаться найти реальное фото. Если не удаётся – вернуть None."""
        if not self._image_search:
            return None

        # Формируем запрос в зависимости от формата
        query = None

        if pub.format in {PublicationFormat.BREAKING_NEWS, PublicationFormat.TRANSFER_NEWS}:
            if source_item:
                # Берём первые 5 слов из заголовка новости
                words = source_item.title.split()[:5]
                query = " ".join(words) + " football"
            else:
                # Заголовок публикации
                words = pub.title.split()[:5]
                query = " ".join(words) + " football"

        elif pub.format == PublicationFormat.INTERESTING_FACT:
            # Убираем "Факт: " из заголовка (если есть)
            topic = pub.title.replace("Факт: ", "").strip()
            if topic:
                words = topic.split()[:5]  # первые 5 слов
                query = " ".join(words) + " football"
            else:
                query = "football fact"

        elif match:
            # Фото матча – используем названия команд + "football"
            query = f"{match.home_team} vs {match.away_team} football"

        else:
            # Универсальный запрос
            query = "football"

        if not query:
            return None

        # Пытаемся найти фото
        photo_url = await self._image_search.search_photo(query)
        if not photo_url:
            return None

        # Скачиваем
        dest_path = self._output_dir / f"real_{uuid.uuid4().hex[:8]}.jpg"
        local_path = await self._download_image(photo_url, dest_path)
        return local_path

    # ----- Остальные методы (generate_news_card, generate_match_card, generate_standings_card, generate_fact_card) остаются без изменений -----
    def _draw_gradient_background(self, draw, bg_color, accent_color):
        ...  # оставляем как было

    def _draw_accent_bar(self, draw, accent_color, height=8):
        ...

    def generate_news_card(self, pub: Publication) -> Optional[str]:
        ...  # как было

    def generate_match_card(self, match: Match) -> Optional[str]:
        ...

    def generate_standings_card(self, league_name: str, top_rows: list) -> Optional[str]:
        ...

    def generate_fact_card(self, fact_text: str) -> Optional[str]:
        ...

    async def generate_for_publication(self, pub: Publication, source_item: Optional[NewsItem] = None, match: Optional[Match] = None) -> Optional[str]:
        """Главная диспетчерская функция."""
        # Сначала пробуем реальное фото
        real_photo = await self.get_photo_for_publication(pub, source_item, match)
        if real_photo:
            return real_photo

        # Если не получилось – генерируем свою карточку
        fmt = pub.format
        if fmt in {PublicationFormat.BREAKING_NEWS, PublicationFormat.TRANSFER_NEWS}:
            return self.generate_news_card(pub)
        if fmt in {PublicationFormat.MATCH_PREVIEW, PublicationFormat.MATCH_REPORT, PublicationFormat.LIVE_UPDATE} and match:
            return self.generate_match_card(match)
        if fmt == PublicationFormat.INTERESTING_FACT:
            return self.generate_fact_card(pub.text[:300])
        if pub.text:
            return self.generate_fact_card(pub.text[:300])
        return None

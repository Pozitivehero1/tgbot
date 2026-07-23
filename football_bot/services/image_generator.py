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
    """Return a PIL font, falling back gracefully if system fonts are unavailable."""
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
        """Скачивает изображение по URL и сохраняет в dest_path."""
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
        """Попытаться найти реальное фото для публикации. Если найдено — скачать и вернуть путь."""
        if not self._image_search:
            return None

        # Генерируем поисковый запрос в зависимости от формата
        query = None
        if pub.format in {PublicationFormat.BREAKING_NEWS, PublicationFormat.TRANSFER_NEWS}:
            if source_item:
                title_words = source_item.title.split()
                query = " ".join(title_words[:5])
            else:
                query = pub.title
        elif pub.format == PublicationFormat.INTERESTING_FACT:
            query = " ".join(pub.title.split()[:4])
        elif match:
            query = f"{match.home_team} vs {match.away_team} football"
        else:
            query = "football"

        if not query:
            return None

        photo_url = await self._image_search.search_photo(query)
        if not photo_url:
            return None

        # Скачиваем фото в папку images
        dest_path = self._output_dir / f"real_{uuid.uuid4().hex[:8]}.jpg"
        local_path = await self._download_image(photo_url, dest_path)
        return local_path

    def _draw_gradient_background(
        self, draw: ImageDraw.ImageDraw, bg_color: tuple, accent_color: tuple
    ) -> None:
        for y in range(self._height):
            ratio = y / self._height
            r = int(bg_color[0] * (1 - ratio * 0.3))
            g = int(bg_color[1] * (1 - ratio * 0.3))
            b = int(bg_color[2] * (1 - ratio * 0.3))
            draw.line([(0, y), (self._width, y)], fill=(r, g, b))
        for x in range(self._width):
            ratio = 1.0 - x / self._width
            alpha = int(40 * ratio)
            draw.line([(x, 0), (x, self._height)], fill=(
                min(255, accent_color[0] + alpha),
                min(255, accent_color[1] + alpha),
                min(255, accent_color[2] + alpha),
            ))

    def _draw_accent_bar(
        self, draw: ImageDraw.ImageDraw, accent_color: tuple, height: int = 8
    ) -> None:
        draw.rectangle([(0, 0), (self._width, height)], fill=accent_color)

    # --- Генерация карточки для новостей (с русским текстом) ---

    def generate_news_card(self, pub: Publication) -> Optional[str]:
        """Создаёт карточку с русским заголовком и первым абзацем."""
        try:
            colors = CARD_COLORS["breaking"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_gradient_background(draw, colors["bg"], colors["accent"])
            self._draw_accent_bar(draw, colors["accent"])

            header_text = "📰 НОВОСТЬ"
            draw.text((60, 50), header_text, font=_get_font(FONT_SIZES["subtitle"], bold=True), fill=colors["accent"])

            wrapped_title = textwrap.wrap(pub.title, width=38)
            y = 130
            for line in wrapped_title[:4]:
                draw.text((60, y), line, font=_get_font(FONT_SIZES["title"], bold=True), fill=colors["text"])
                y += FONT_SIZES["title"] + 8

            if pub.text:
                body_font = _get_font(FONT_SIZES["body"])
                body_lines = textwrap.wrap(pub.text[:200], width=55)
                y += 20
                for line in body_lines[:3]:
                    draw.text((60, y), line, font=body_font, fill=colors["subtext"])
                    y += FONT_SIZES["body"] + 4

            draw.text((60, self._height - 60), "⚽ Football News", font=_get_font(FONT_SIZES["caption"]), fill=colors["subtext"])

            return self._save_image(image, f"news_{pub.pub_id[:8]}")
        except Exception as exc:
            logger.error("image_generation_failed", format="news", error=str(exc))
            return None

    def generate_match_card(self, match: Match) -> Optional[str]:
        try:
            colors = CARD_COLORS["match"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_gradient_background(draw, colors["bg"], colors["accent"])
            self._draw_accent_bar(draw, colors["accent"])

            league_font = _get_font(FONT_SIZES["subtitle"])
            team_font = _get_font(FONT_SIZES["title"], bold=True)
            score_font = _get_font(FONT_SIZES["score"], bold=True)
            caption_font = _get_font(FONT_SIZES["caption"])

            draw.text((self._width // 2, 55), match.league_name, font=league_font, fill=colors["subtext"], anchor="mm")
            draw.text((self._width // 2 - 220, self._height // 2), match.home_team, font=team_font, fill=colors["text"], anchor="mm")
            draw.text((self._width // 2, self._height // 2), match.score_display, font=score_font, fill=colors["accent"], anchor="mm")
            draw.text((self._width // 2 + 220, self._height // 2), match.away_team, font=team_font, fill=colors["text"], anchor="mm")

            status_text = match.status.value.replace("_", " ").upper()
            draw.text((self._width // 2, self._height - 60), status_text, font=caption_font, fill=colors["subtext"], anchor="mm")
            return self._save_image(image, f"match_{match.match_id[:8]}")
        except Exception as exc:
            logger.error("image_generation_failed", format="match", error=str(exc))
            return None

    def generate_standings_card(self, league_name: str, top_rows: list[tuple[int, str, int]]) -> Optional[str]:
        try:
            colors = CARD_COLORS["standings"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_gradient_background(draw, colors["bg"], colors["accent"])
            self._draw_accent_bar(draw, colors["accent"])

            header_font = _get_font(FONT_SIZES["subtitle"], bold=True)
            row_font = _get_font(FONT_SIZES["body"])

            draw.text((60, 40), f"📊 ТАБЛИЦА {league_name.upper()}", font=header_font, fill=colors["text"])
            y = 120
            for pos, team, pts in top_rows[:8]:
                color = colors["accent"] if pos == 1 else colors["text"]
                draw.text((60, y), f"{pos:2}.", font=row_font, fill=colors["subtext"])
                draw.text((110, y), team, font=row_font, fill=color)
                draw.text((self._width - 80, y), f"{pts} pts", font=row_font, fill=colors["subtext"])
                y += FONT_SIZES["body"] + 12

            return self._save_image(image, f"standings_{league_name[:8].lower()}")
        except Exception as exc:
            logger.error("image_generation_failed", format="standings", error=str(exc))
            return None

    def generate_fact_card(self, fact_text: str) -> Optional[str]:
        try:
            colors = CARD_COLORS["fact"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_gradient_background(draw, colors["bg"], colors["accent"])
            self._draw_accent_bar(draw, colors["accent"])

            header_font = _get_font(FONT_SIZES["subtitle"], bold=True)
            body_font = _get_font(FONT_SIZES["body"])

            draw.text((60, 50), "🤯 ФАКТ", font=header_font, fill=colors["accent"])
            lines = textwrap.wrap(fact_text[:400], width=45)
            y = 130
            for line in lines[:8]:
                draw.text((60, y), line, font=body_font, fill=colors["text"])
                y += FONT_SIZES["body"] + 8

            return self._save_image(image, f"fact_{uuid.uuid4().hex[:8]}")
        except Exception as exc:
            logger.error("image_generation_failed", format="fact", error=str(exc))
            return None

    async def generate_for_publication(self, pub: Publication, source_item: Optional[NewsItem] = None, match: Optional[Match] = None) -> Optional[str]:
        """Главная диспетчерская функция с поддержкой реальных фото."""
        # Сначала пробуем получить реальное фото
        real_photo = await self.get_photo_for_publication(pub, source_item, match)
        if real_photo:
            return real_photo

        # Если не получилось — генерируем карточку
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

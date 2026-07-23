"""ImageGenerator — creates beautiful card images for Telegram publications."""

from __future__ import annotations

import math
import os
import re
import textwrap
import uuid
from pathlib import Path
from typing import Optional

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


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text)


class ImageGenerator:
    def __init__(self, image_search_service=None) -> None:
        settings = get_settings()
        self._output_dir = Path(settings.images_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._width = settings.card_width
        self._height = settings.card_height
        self._image_search = image_search_service

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

    # ======== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========
    def _draw_radial_gradient(self, draw, center_color, edge_color):
        cx, cy = self._width // 2, self._height // 2
        max_dist = math.hypot(cx, cy)
        for y in range(self._height):
            for x in range(self._width):
                dist = math.hypot(x - cx, y - cy)
                ratio = min(dist / max_dist, 1.0)
                r = int(center_color[0] * (1 - ratio) + edge_color[0] * ratio)
                g = int(center_color[1] * (1 - ratio) + edge_color[1] * ratio)
                b = int(center_color[2] * (1 - ratio) + edge_color[2] * ratio)
                draw.point((x, y), fill=(r, g, b))

    def _draw_rounded_rect(self, draw, xy, radius, fill, outline=None, width=1):
        x1, y1, x2, y2 = xy
        if x2 - x1 < 2 * radius:
            radius = (x2 - x1) // 2
        if y2 - y1 < 2 * radius:
            radius = (y2 - y1) // 2
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline, width=width)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline, width=width)
        draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill, outline=outline, width=width)
        draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill, outline=outline, width=width)
        draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill, outline=outline, width=width)
        draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill, outline=outline, width=width)

    def _draw_text_with_shadow(self, draw, xy, text, font, fill, shadow_color=(0,0,0,120), offset=(2,2)):
        x, y = xy
        draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=fill)

    # ======== КАРТОЧКА ДЛЯ ФАКТА (С ДЕКОРОМ, БЕЗ ЭМОДЗИ) ========
    def generate_fact_card(self, pub: Publication) -> Optional[str]:
        try:
            # Цветовая схема
            center_color = (25, 20, 50)
            edge_color = (5, 5, 20)
            accent = (255, 215, 0)      # золотой
            text_color = (255, 255, 255)
            sub_text_color = (200, 200, 210)

            image = Image.new("RGB", (self._width, self._height), edge_color)
            draw = ImageDraw.Draw(image, "RGBA")

            # 1. Радиальный градиент
            self._draw_radial_gradient(draw, center_color, edge_color)

            # 2. Декоративные круги (полупрозрачные)
            circle_color = (accent[0], accent[1], accent[2], 40)
            draw.ellipse([-80, -80, 280, 280], fill=circle_color)
            draw.ellipse([self._width - 200, self._height - 200, self._width + 80, self._height + 80], fill=circle_color)
            draw.ellipse([self._width // 2 - 300, self._height // 2 - 300, self._width // 2 + 100, self._height // 2 + 100], fill=(accent[0], accent[1], accent[2], 10))

            # 3. Верхняя акцентная линия (золотая)
            draw.rectangle([(0, 0), (self._width, 6)], fill=accent)

            # 4. Заголовок в плашке (без эмодзи)
            header_text = "★ ИНТЕРЕСНЫЙ ФАКТ"
            header_font = _get_font(FONT_SIZES["subtitle"], bold=True)
            bbox = draw.textbbox((0,0), header_text, font=header_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            rect_x1 = 60
            rect_y1 = 40
            rect_x2 = rect_x1 + text_width + 60
            rect_y2 = rect_y1 + text_height + 30
            self._draw_rounded_rect(draw, (rect_x1, rect_y1, rect_x2, rect_y2), radius=20, fill=(accent[0], accent[1], accent[2], 220))
            draw.text((rect_x1 + 30, rect_y1 + 15), header_text, font=header_font, fill=(0,0,0))

            # 5. Текст факта на подложке
            clean_text = strip_html(pub.text)
            if len(clean_text) > 650:
                display_text = clean_text[:647] + "..."
            else:
                display_text = clean_text

            text_y_start = rect_y2 + 50
            text_y_end = self._height - 80
            overlay = Image.new("RGBA", (self._width, self._height), (0,0,0,0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle([(40, text_y_start - 20), (self._width - 40, text_y_end + 20)], fill=(0,0,0,150))
            image.paste(overlay, (0,0), overlay)

            body_font = _get_font(FONT_SIZES["body"], bold=False)
            lines = textwrap.wrap(display_text, width=50)
            y = text_y_start
            for line in lines[:14]:
                self._draw_text_with_shadow(draw, (60, y), line, font=body_font, fill=text_color, shadow_color=(0,0,0,150), offset=(2,2))
                y += FONT_SIZES["body"] + 10

            # 6. Нижняя подпись
            caption_font = _get_font(FONT_SIZES["caption"])
            draw.text((60, self._height - 45), "⚽ Football News", font=caption_font, fill=sub_text_color)

            # 7. Тонкая рамка
            draw.rectangle([(2, 2), (self._width - 2, self._height - 2)], outline=(accent[0], accent[1], accent[2], 80), width=2)

            return self._save_image(image, f"fact_{pub.pub_id[:8]}")
        except Exception as exc:
            logger.error("image_generation_failed", format="fact", error=str(exc), exc_info=True)
            return None

    # ======== НОВОСТНАЯ КАРТОЧКА ========
    def generate_news_card(self, pub: Publication) -> Optional[str]:
        try:
            colors = CARD_COLORS["breaking"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_radial_gradient(draw, (40,20,40), colors["bg"])
            draw.rectangle([(0, 0), (self._width, 6)], fill=colors["accent"])

            header_font = _get_font(FONT_SIZES["subtitle"], bold=True)
            draw.text((60, 50), "■ НОВОСТЬ", font=header_font, fill=colors["accent"])

            title_clean = strip_html(pub.title)
            title_font = _get_font(FONT_SIZES["title"], bold=True)
            wrapped_title = textwrap.wrap(title_clean, width=38)
            y = 130
            for line in wrapped_title[:4]:
                self._draw_text_with_shadow(draw, (60, y), line, font=title_font, fill=colors["text"], shadow_color=(0,0,0,150), offset=(2,2))
                y += FONT_SIZES["title"] + 8

            if pub.text:
                body_text_clean = strip_html(pub.text[:250])
                body_font = _get_font(FONT_SIZES["body"])
                body_lines = textwrap.wrap(body_text_clean, width=55)
                y += 20
                for line in body_lines[:4]:
                    draw.text((60, y), line, font=body_font, fill=colors["subtext"])
                    y += FONT_SIZES["body"] + 4

            draw.text((60, self._height - 60), "⚽ Football News", font=_get_font(FONT_SIZES["caption"]), fill=colors["subtext"])
            return self._save_image(image, f"news_{pub.pub_id[:8]}")
        except Exception as exc:
            logger.error("image_generation_failed", format="news", error=str(exc))
            return None

    # ======== КАРТОЧКА МАТЧА ========
    def generate_match_card(self, match: Match) -> Optional[str]:
        try:
            colors = CARD_COLORS["match"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_radial_gradient(draw, (20,60,30), colors["bg"])
            draw.rectangle([(0, 0), (self._width, 6)], fill=colors["accent"])

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

    # ======== КАРТОЧКА ТАБЛИЦЫ ========
    def generate_standings_card(self, league_name: str, top_rows: list[tuple[int, str, int]]) -> Optional[str]:
        try:
            colors = CARD_COLORS["standings"]
            image = Image.new("RGB", (self._width, self._height), colors["bg"])
            draw = ImageDraw.Draw(image, "RGBA")
            self._draw_radial_gradient(draw, (10,60,100), colors["bg"])
            draw.rectangle([(0, 0), (self._width, 6)], fill=colors["accent"])

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

    # ======== ГЛАВНЫЙ ДИСПЕТЧЕР ========
    async def generate_for_publication(self, pub: Publication, source_item: Optional[NewsItem] = None, match: Optional[Match] = None) -> Optional[str]:
        if pub.format == PublicationFormat.INTERESTING_FACT:
            return self.generate_fact_card(pub)

        if pub.format in {PublicationFormat.BREAKING_NEWS, PublicationFormat.TRANSFER_NEWS}:
            if self._image_search:
                query = None
                if source_item:
                    words = source_item.title.split()[:5]
                    query = " ".join(words) + " football"
                else:
                    words = pub.title.split()[:5]
                    query = " ".join(words) + " football"
                if query:
                    photo_url = await self._image_search.search_photo(query)
                    if photo_url:
                        dest_path = self._output_dir / f"real_{uuid.uuid4().hex[:8]}.jpg"
                        local_path = await self._download_image(photo_url, dest_path)
                        if local_path:
                            return local_path
            return self.generate_news_card(pub)

        if match:
            return self.generate_match_card(match)

        if pub.text:
            return self.generate_fact_card(pub)

        return None

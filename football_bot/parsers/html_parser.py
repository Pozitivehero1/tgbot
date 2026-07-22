"""HTML parser for structured football data pages (standings, fixtures, stats)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser as SelectolaxParser

from football_bot.core.models.match import Match, MatchStatus
from football_bot.core.models.news import NewsItem, NewsReliability
from football_bot.core.models.standing import Standing, StandingsTable
from football_bot.parsers.base_parser import BaseParser, make_item_id
from football_bot.utils.logger import get_logger

logger = get_logger(__name__)


class HTMLParser(BaseParser):
    """Scrapes structured football data from HTML pages using selectolax + BS4."""

    @property
    def source_name(self) -> str:
        return "HTMLParser"

    async def fetch(self, url: str) -> list[NewsItem]:
        """Generic HTML news page scraper — extracts article links and headlines."""
        raw = await self._fetch_raw(url)
        if not raw:
            return []
        try:
            tree = SelectolaxParser(raw)
            items: list[NewsItem] = []
            for node in tree.css("article, .article, .news-item, .story"):
                title_node = node.css_first("h1, h2, h3, .title, .headline")
                link_node = node.css_first("a[href]")
                if not title_node or not link_node:
                    continue
                title = title_node.text(strip=True)
                href = link_node.attributes.get("href", "")
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                if not title or not href:
                    continue
                item = NewsItem(
                    item_id=make_item_id(href, title),
                    source_name=url,
                    source_url=url,
                    article_url=href,
                    title=title,
                    published_at=datetime.utcnow(),
                    reliability=NewsReliability.UNCONFIRMED,
                )
                items.append(item)
            return items
        except Exception as exc:
            logger.warning("html_parse_error", url=url, error=str(exc))
            return []

    async def fetch_article_text(self, url: str) -> str:
        """Extract the main article text from a given URL."""
        raw = await self._fetch_raw(url)
        if not raw:
            return ""
        try:
            soup = BeautifulSoup(raw, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                tag.decompose()
            candidates = soup.select(
                "article, .article-body, .story-body, .content-body, main, #main-content"
            )
            if candidates:
                return candidates[0].get_text(separator="\n", strip=True)[:8000]
            return soup.get_text(separator="\n", strip=True)[:4000]
        except Exception as exc:
            logger.warning("article_text_error", url=url, error=str(exc))
            return ""

    async def parse_standings_from_html(self, url: str, league_code: str) -> Optional[StandingsTable]:
        """Generic standings table scraper — works for most football table HTML layouts."""
        raw = await self._fetch_raw(url)
        if not raw:
            return None
        try:
            soup = BeautifulSoup(raw, "lxml")
            table = soup.find("table", class_=re.compile(r"table|standing|league", re.I))
            if not table:
                return None
            standings: list[Standing] = []
            rows = table.find_all("tr")[1:]  # skip header
            for i, row in enumerate(rows, start=1):
                cols = row.find_all(["td", "th"])
                if len(cols) < 6:
                    continue
                texts = [c.get_text(strip=True) for c in cols]
                try:
                    position = int(texts[0]) if texts[0].isdigit() else i
                    team_name = texts[1]
                    played = int(texts[2]) if texts[2].isdigit() else 0
                    won = int(texts[3]) if texts[3].isdigit() else 0
                    drawn = int(texts[4]) if texts[4].isdigit() else 0
                    lost = int(texts[5]) if texts[5].isdigit() else 0
                    goals_raw = texts[6] if len(texts) > 6 else "0:0"
                    if ":" in goals_raw:
                        gf_str, ga_str = goals_raw.split(":", 1)
                        goals_for = int(gf_str.strip()) if gf_str.strip().isdigit() else 0
                        goals_against = int(ga_str.strip()) if ga_str.strip().isdigit() else 0
                    else:
                        goals_for = goals_against = 0
                    gd_raw = texts[7] if len(texts) > 7 else "0"
                    goal_difference = int(gd_raw.lstrip("+")) if re.match(r"[+-]?\d+", gd_raw) else goals_for - goals_against
                    points_raw = texts[8] if len(texts) > 8 else "0"
                    points = int(points_raw) if points_raw.isdigit() else 0
                    standings.append(
                        Standing(
                            position=position,
                            team_name=team_name,
                            played=played,
                            won=won,
                            drawn=drawn,
                            lost=lost,
                            goals_for=goals_for,
                            goals_against=goals_against,
                            goal_difference=goal_difference,
                            points=points,
                        )
                    )
                except (ValueError, IndexError):
                    continue
            if not standings:
                return None
            return StandingsTable(
                league_code=league_code,
                league_name=league_code,
                standings=standings,
                fetched_at=datetime.utcnow(),
                source=url,
            )
        except Exception as exc:
            logger.warning("standings_parse_error", url=url, error=str(exc))
            return None

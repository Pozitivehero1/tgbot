"""Repository implementations."""

from football_bot.repositories.news_repository import NewsRepository
from football_bot.repositories.match_repository import MatchRepository
from football_bot.repositories.publication_repository import PublicationRepository

__all__ = ["NewsRepository", "MatchRepository", "PublicationRepository"]

"""Parser package."""

from football_bot.parsers.rss_parser import RSSParser
from football_bot.parsers.html_parser import HTMLParser
from football_bot.parsers.transfer_parser import TransferParser

__all__ = ["RSSParser", "HTMLParser", "TransferParser"]

"""TelegramFormatter — ensures all text respects Telegram limits and HTML tags."""

from __future__ import annotations

import html
import re

_TELEGRAM_MAX_CAPTION = 1024
_TELEGRAM_MAX_MESSAGE = 4096


class TelegramFormatter:
    """Sanitises and truncates text for Telegram HTML parse mode."""

    _ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre", "tg-spoiler"}
    _HTML_TAG_RE = re.compile(r"<(/?)([a-z][a-z0-9]*)[^>]*>", re.IGNORECASE)
    _MULTIPLE_NEWLINES_RE = re.compile(r"\n{3,}")
    _MULTIPLE_SPACES_RE = re.compile(r"[ \t]{2,}")

    @classmethod
    def sanitise(cls, text: str) -> str:
        """Strip disallowed HTML tags and normalise whitespace."""
        def _replace_tag(match: re.Match) -> str:
            closing = match.group(1)
            tag = match.group(2).lower()
            if tag in cls._ALLOWED_TAGS:
                return match.group(0)
            return ""

        cleaned = cls._HTML_TAG_RE.sub(_replace_tag, text)
        cleaned = cls._MULTIPLE_NEWLINES_RE.sub("\n\n", cleaned)
        cleaned = cls._MULTIPLE_SPACES_RE.sub(" ", cleaned)
        return cleaned.strip()

    @classmethod
    def truncate_message(cls, text: str, max_length: int = _TELEGRAM_MAX_MESSAGE) -> str:
        """Truncate text to Telegram's message limit, preserving whole words."""
        if len(text) <= max_length:
            return text
        truncated = text[: max_length - 4]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.8:
            truncated = truncated[:last_space]
        return truncated + " ..."

    @classmethod
    def truncate_caption(cls, text: str) -> str:
        return cls.truncate_message(text, _TELEGRAM_MAX_CAPTION)

    @classmethod
    def format_message(cls, text: str) -> str:
        return cls.truncate_message(cls.sanitise(text))

    @classmethod
    def format_caption(cls, text: str) -> str:
        return cls.truncate_caption(cls.sanitise(text))

    @classmethod
    def escape(cls, text: str) -> str:
        """HTML-escape plain text for safe inclusion inside HTML messages."""
        return html.escape(text)

    @staticmethod
    def build_hashtags(tags: list[str]) -> str:
        return " ".join(f"#{tag.replace(' ', '_').lower()}" for tag in tags if tag)

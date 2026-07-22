"""Application settings via Pydantic BaseSettings."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration — loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: str = Field(..., description="Telegram Bot API token")
    channel_id: str = Field(..., description="Telegram channel ID, e.g. @mychannel or -100...")

    # ── Mistral AI ────────────────────────────────────────────────────────────
    mistral_api_key: str = Field(..., description="Mistral AI API key")
    mistral_model: str = Field(
        default="mistral-large-latest",
        description="Mistral model identifier",
    )
    mistral_fallback_model: str = Field(
        default="mistral-small-latest",
        description="Fallback model if primary is unavailable",
    )
    mistral_timeout: float = Field(default=120.0, description="Request timeout in seconds")
    mistral_max_retries: int = Field(default=3, description="Max retries per request")
    mistral_rate_limit_rpm: int = Field(default=30, description="Max requests per minute")
    mistral_cache_ttl_seconds: int = Field(default=3600, description="LLM response cache TTL")

    # ── Database ──────────────────────────────────────────────────────────────
    database_path: str = Field(default="data/football_bot.db", description="SQLite DB file path")

    # ── Storage ───────────────────────────────────────────────────────────────
    data_dir: str = Field(default="data", description="Data directory for state files")
    assets_dir: str = Field(default="football_bot/assets", description="Static assets directory")
    images_dir: str = Field(default="data/images", description="Generated images output")

    # ── Publisher ─────────────────────────────────────────────────────────────
    max_publications_per_run: int = Field(
        default=5,
        description="Max posts to publish in a single GitHub Actions run",
    )
    min_reliability_score: float = Field(
        default=0.6,
        description="Minimum fact-check score (0–1) required to publish",
    )
    publication_delay_seconds: float = Field(
        default=3.0,
        description="Delay between Telegram messages to respect rate limits",
    )

    # ── News aggregation ──────────────────────────────────────────────────────
    max_news_age_hours: int = Field(default=24, description="Ignore news older than N hours")
    max_articles_per_source: int = Field(default=10, description="Max articles per source per run")
    deduplication_threshold: float = Field(
        default=0.85,
        description="Cosine similarity threshold for duplicate detection",
    )

    # ── Scheduling metadata ───────────────────────────────────────────────────
    run_mode: Literal["news", "live", "digest_daily", "digest_weekly", "digest_monthly", "facts", "standings", "analytics"] = Field(
        default="news",
        description="Which pipeline to run in this GitHub Actions execution",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    # ── Analytics & self-learning ─────────────────────────────────────────────
    analytics_window_days: int = Field(
        default=30,
        description="Rolling window for analytics calculations",
    )
    enable_self_learning: bool = Field(
        default=True,
        description="Allow the system to adjust strategy based on analytics",
    )

    # ── Live center ───────────────────────────────────────────────────────────
    live_polling_interval_seconds: int = Field(
        default=60,
        description="How often to poll live match data",
    )
    live_max_duration_minutes: int = Field(
        default=130,
        description="Max minutes to keep polling a live match",
    )

    # ── Image generation ──────────────────────────────────────────────────────
    card_width: int = Field(default=1200, description="Generated image card width in pixels")
    card_height: int = Field(default=675, description="Generated image card height in pixels")

    @field_validator("channel_id")
    @classmethod
    def normalize_channel_id(cls, value: str) -> str:
        value = value.strip()
        if value.lstrip("-").isdigit():
            return value
        if not value.startswith("@"):
            return f"@{value}"
        return value

    @field_validator("database_path", "data_dir", "images_dir", mode="before")
    @classmethod
    def ensure_directory_exists(cls, value: str) -> str:
        directory = os.path.dirname(value) if "." in os.path.basename(value) else value
        if directory:
            os.makedirs(directory, exist_ok=True)
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

"""Publication domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PublicationFormat(str, Enum):
    """Type of content published to the Telegram channel."""

    BREAKING_NEWS = "breaking_news"
    TRANSFER_NEWS = "transfer_news"
    MATCH_PREVIEW = "match_preview"
    MATCH_REPORT = "match_report"
    LIVE_UPDATE = "live_update"
    STANDINGS = "standings"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    MONTHLY_DIGEST = "monthly_digest"
    INTERESTING_FACT = "interesting_fact"
    HISTORICAL_POST = "historical_post"
    ANALYSIS = "analysis"
    STATISTICS = "statistics"
    PLAYER_PROFILE = "player_profile"
    INJURY_UPDATE = "injury_update"


class PublicationStatus(str, Enum):
    """Lifecycle state of a publication."""

    DRAFT = "draft"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


class PublicationMetrics(BaseModel):
    """Engagement metrics for a published post."""

    views: int = 0
    reactions: int = 0
    shares: int = 0
    comments: int = 0
    reach: int = 0
    engagement_rate: float = 0.0
    collected_at: Optional[datetime] = None


class Publication(BaseModel):
    """A single piece of content published or queued for publishing."""

    pub_id: str = Field(..., description="Unique publication identifier")
    format: PublicationFormat = Field(...)
    status: PublicationStatus = Field(default=PublicationStatus.DRAFT)

    # Content
    title: str = Field(default="")
    text: str = Field(..., description="Telegram-formatted message text")
    image_path: Optional[str] = Field(default=None, description="Local path to card image")

    # Source traceability
    source_item_ids: list[str] = Field(default_factory=list)
    league_code: Optional[str] = Field(default=None)
    match_id: Optional[str] = Field(default=None)

    # Publishing metadata
    telegram_message_id: Optional[int] = Field(default=None)
    published_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_for: Optional[datetime] = Field(default=None)

    # Quality
    ai_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_length: int = Field(default=0, description="Character count of text")

    # Analytics
    metrics: Optional[PublicationMetrics] = Field(default=None)

    # Generation metadata
    model_used: str = Field(default="")
    generation_prompt_hash: str = Field(default="")
    generation_duration_seconds: float = Field(default=0.0)

    def mark_published(self, message_id: int) -> None:
        self.telegram_message_id = message_id
        self.status = PublicationStatus.PUBLISHED
        self.published_at = datetime.utcnow()

    def mark_failed(self) -> None:
        self.status = PublicationStatus.FAILED

    @property
    def has_image(self) -> bool:
        return self.image_path is not None

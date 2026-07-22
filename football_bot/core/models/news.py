"""News domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, computed_field


class NewsCategory(str, Enum):
    """Categorisation of a football news item."""

    TRANSFER = "transfer"
    MATCH_RESULT = "match_result"
    MATCH_PREVIEW = "match_preview"
    INJURY = "injury"
    LINEUP = "lineup"
    TACTICAL = "tactical"
    DISCIPLINARY = "disciplinary"
    OFFICIAL_STATEMENT = "official_statement"
    RUMOUR = "rumour"
    GENERAL = "general"
    STATISTICS = "statistics"
    HISTORICAL = "historical"


class NewsReliability(str, Enum):
    """Fact-check reliability label."""

    OFFICIAL = "official"
    CONFIRMED = "confirmed"
    RUMOUR = "rumour"
    INSIDER = "insider"
    UNCONFIRMED = "unconfirmed"


class NewsItem(BaseModel):
    """A single news article collected from any source."""

    model_config = {"frozen": False}

    # Identity
    item_id: str = Field(..., description="Unique hash of the article")
    source_name: str = Field(..., description="Human-readable source name")
    source_url: str = Field(..., description="Base URL of the source")
    article_url: str = Field(..., description="Direct link to the article")

    # Content
    title: str = Field(..., description="Original article headline")
    summary: str = Field(default="", description="Original summary or first paragraph")
    full_text: str = Field(default="", description="Full scraped article text")
    language: str = Field(default="en", description="ISO 639-1 language code")

    # Classification
    category: NewsCategory = Field(default=NewsCategory.GENERAL)
    reliability: NewsReliability = Field(default=NewsReliability.UNCONFIRMED)
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reliability_reasoning: str = Field(default="")
    red_flags: list[str] = Field(default_factory=list)

    # Timestamps
    published_at: datetime = Field(..., description="Original publication time")
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    # Tags
    teams_mentioned: list[str] = Field(default_factory=list)
    players_mentioned: list[str] = Field(default_factory=list)
    leagues_mentioned: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Processing
    is_duplicate: bool = Field(default=False)
    duplicate_of: Optional[str] = Field(default=None)
    was_published: bool = Field(default=False)
    content_vector: Optional[list[float]] = Field(default=None, exclude=True)

    # Source metadata
    source_reliability: float = Field(default=0.8, ge=0.0, le=1.0)
    corroborating_sources: list[str] = Field(default_factory=list)
    corroboration_count: int = Field(default=1)

    @computed_field
    @property
    def priority_score(self) -> float:
        """Composite priority: reliability × source weight × corroboration bonus."""
        corroboration_bonus = min(self.corroboration_count * 0.05, 0.25)
        return (
            self.reliability_score * 0.5
            + self.source_reliability * 0.3
            + corroboration_bonus
        )

    @computed_field
    @property
    def age_hours(self) -> float:
        """Hours since original publication."""
        delta = datetime.utcnow() - self.published_at
        return delta.total_seconds() / 3600

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Return True if the article is older than the allowed window."""
        return self.age_hours > max_age_hours

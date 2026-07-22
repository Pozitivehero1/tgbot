"""SQLAlchemy ORM schema — all tables for the football bot."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class NewsItemORM(Base):
    __tablename__ = "news_items"

    item_id = Column(String(64), primary_key=True, index=True)
    source_name = Column(String(256), nullable=False)
    source_url = Column(String(2048), nullable=False)
    article_url = Column(String(2048), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, default="")
    full_text = Column(Text, default="")
    language = Column(String(8), default="en")
    category = Column(String(64), default="general")
    reliability = Column(String(32), default="unconfirmed")
    reliability_score = Column(Float, default=0.0)
    reliability_reasoning = Column(Text, default="")
    red_flags = Column(JSON, default=list)
    published_at = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    teams_mentioned = Column(JSON, default=list)
    players_mentioned = Column(JSON, default=list)
    leagues_mentioned = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String(64), nullable=True)
    was_published = Column(Boolean, default=False)
    source_reliability = Column(Float, default=0.8)
    corroborating_sources = Column(JSON, default=list)
    corroboration_count = Column(Integer, default=1)
    content_vector = Column(JSON, nullable=True)


class MatchORM(Base):
    __tablename__ = "matches"

    match_id = Column(String(64), primary_key=True, index=True)
    league_code = Column(String(16), nullable=False, index=True)
    league_name = Column(String(256), default="")
    round_label = Column(String(128), default="")
    home_team = Column(String(256), nullable=False)
    away_team = Column(String(256), nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    home_score_ht = Column(Integer, nullable=True)
    away_score_ht = Column(Integer, nullable=True)
    home_score_et = Column(Integer, nullable=True)
    away_score_et = Column(Integer, nullable=True)
    home_score_pen = Column(Integer, nullable=True)
    away_score_pen = Column(Integer, nullable=True)
    status = Column(String(32), default="scheduled")
    kickoff_time = Column(DateTime, nullable=False)
    current_minute = Column(Integer, nullable=True)
    venue = Column(String(512), default="")
    referee = Column(String(256), default="")
    attendance = Column(Integer, nullable=True)
    events = Column(JSON, default=list)
    statistics = Column(JSON, nullable=True)
    home_lineup = Column(JSON, nullable=True)
    away_lineup = Column(JSON, nullable=True)
    player_stats = Column(JSON, default=list)
    best_player = Column(String(256), nullable=True)
    source = Column(String(256), default="")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    live_published_events = Column(JSON, default=list)


class PublicationORM(Base):
    __tablename__ = "publications"

    pub_id = Column(String(64), primary_key=True, index=True)
    format = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="draft", index=True)
    title = Column(Text, default="")
    text = Column(Text, nullable=False)
    image_path = Column(String(2048), nullable=True)
    source_item_ids = Column(JSON, default=list)
    league_code = Column(String(16), nullable=True)
    match_id = Column(String(64), nullable=True)
    telegram_message_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_for = Column(DateTime, nullable=True)
    ai_quality_score = Column(Float, default=0.0)
    reliability_score = Column(Float, default=0.0)
    estimated_length = Column(Integer, default=0)
    metrics = Column(JSON, nullable=True)
    model_used = Column(String(128), default="")
    generation_prompt_hash = Column(String(64), default="")
    generation_duration_seconds = Column(Float, default=0.0)


class LiveEventORM(Base):
    __tablename__ = "live_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    minute = Column(Integer, nullable=True)
    message_text = Column(Text, nullable=False)
    telegram_message_id = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)


class AnalyticsEventORM(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pub_id = Column(String(64), nullable=False, index=True)
    format = Column(String(64), nullable=False)
    league_code = Column(String(16), nullable=True)
    published_at = Column(DateTime, nullable=True)
    hour_of_day = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    views = Column(Integer, default=0)
    reactions = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    ai_quality_score = Column(Float, default=0.0)
    text_length = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class SelfLearningStateORM(Base):
    __tablename__ = "self_learning_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LLMCacheORM(Base):
    __tablename__ = "llm_cache"

    prompt_hash = Column(String(64), primary_key=True)
    response_text = Column(Text, nullable=False)
    model = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    hit_count = Column(Integer, default=0)

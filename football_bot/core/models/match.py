"""Match and live event domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    """Current state of a football match."""

    SCHEDULED = "scheduled"
    LINEUP_ANNOUNCED = "lineup_announced"
    LIVE = "live"
    HALF_TIME = "half_time"
    EXTRA_TIME = "extra_time"
    PENALTY_SHOOTOUT = "penalty_shootout"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class MatchEvent(BaseModel):
    """A discrete event during a live match."""

    event_type: str = Field(..., description="Type from LIVE_EVENT_TYPES constant")
    minute: Optional[int] = Field(default=None, description="Match minute")
    extra_time_minute: Optional[int] = Field(default=None)
    player_name: Optional[str] = Field(default=None)
    player_assist: Optional[str] = Field(default=None)
    team: Optional[str] = Field(default=None)
    description: str = Field(default="")
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    is_var_checked: bool = Field(default=False)
    var_outcome: Optional[str] = Field(default=None)


class PlayerStats(BaseModel):
    """Individual player statistics for a match."""

    player_name: str
    team: str
    minutes_played: int = 0
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes: int = 0
    pass_accuracy: float = 0.0
    dribbles_completed: int = 0
    tackles: int = 0
    interceptions: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 0.0


class TeamLineup(BaseModel):
    """Team lineup for a match."""

    team_name: str
    formation: str = Field(default="")
    starting_xi: list[str] = Field(default_factory=list)
    substitutes: list[str] = Field(default_factory=list)
    manager: str = Field(default="")


class MatchStatistics(BaseModel):
    """Aggregate match statistics."""

    home_possession: float = 50.0
    away_possession: float = 50.0
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    home_corners: int = 0
    away_corners: int = 0
    home_fouls: int = 0
    away_fouls: int = 0
    home_yellow_cards: int = 0
    away_yellow_cards: int = 0
    home_red_cards: int = 0
    away_red_cards: int = 0
    home_offsides: int = 0
    away_offsides: int = 0
    home_xg: float = 0.0
    away_xg: float = 0.0
    home_passes: int = 0
    away_passes: int = 0
    home_pass_accuracy: float = 0.0
    away_pass_accuracy: float = 0.0


class Match(BaseModel):
    """Full match data model."""

    match_id: str = Field(..., description="Unique match identifier")
    league_code: str = Field(..., description="League code from LEAGUES constant")
    league_name: str = Field(default="")
    round_label: str = Field(default="")

    home_team: str = Field(...)
    away_team: str = Field(...)
    home_score: Optional[int] = Field(default=None)
    away_score: Optional[int] = Field(default=None)
    home_score_ht: Optional[int] = Field(default=None)
    away_score_ht: Optional[int] = Field(default=None)
    home_score_et: Optional[int] = Field(default=None)
    away_score_et: Optional[int] = Field(default=None)
    home_score_pen: Optional[int] = Field(default=None)
    away_score_pen: Optional[int] = Field(default=None)

    status: MatchStatus = Field(default=MatchStatus.SCHEDULED)
    kickoff_time: datetime = Field(...)
    current_minute: Optional[int] = Field(default=None)
    venue: str = Field(default="")
    referee: str = Field(default="")
    attendance: Optional[int] = Field(default=None)

    events: list[MatchEvent] = Field(default_factory=list)
    statistics: Optional[MatchStatistics] = Field(default=None)
    home_lineup: Optional[TeamLineup] = Field(default=None)
    away_lineup: Optional[TeamLineup] = Field(default=None)
    player_stats: list[PlayerStats] = Field(default_factory=list)

    best_player: Optional[str] = Field(default=None)
    source: str = Field(default="")
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    live_published_events: list[str] = Field(
        default_factory=list,
        description="event_type strings already pushed to Telegram",
    )

    @property
    def score_display(self) -> str:
        home = self.home_score if self.home_score is not None else "–"
        away = self.away_score if self.away_score is not None else "–"
        return f"{home} : {away}"

    @property
    def is_live(self) -> bool:
        return self.status in {MatchStatus.LIVE, MatchStatus.HALF_TIME, MatchStatus.EXTRA_TIME, MatchStatus.PENALTY_SHOOTOUT}

    @property
    def result_label(self) -> str:
        if self.home_score is None or self.away_score is None:
            return ""
        if self.home_score > self.away_score:
            return f"Победа {self.home_team}"
        if self.away_score > self.home_score:
            return f"Победа {self.away_team}"
        return "Ничья"


class LiveUpdate(BaseModel):
    """A single live update already sent to Telegram."""

    match_id: str
    event_type: str
    minute: Optional[int] = None
    message_text: str
    telegram_message_id: Optional[int] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow)

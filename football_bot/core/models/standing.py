"""Standing / league table domain models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Standing(BaseModel):
    """A single team's standing in a league table."""

    position: int = Field(..., ge=1)
    team_name: str = Field(...)
    team_short: str = Field(default="")
    played: int = Field(default=0, ge=0)
    won: int = Field(default=0, ge=0)
    drawn: int = Field(default=0, ge=0)
    lost: int = Field(default=0, ge=0)
    goals_for: int = Field(default=0, ge=0)
    goals_against: int = Field(default=0, ge=0)
    goal_difference: int = Field(default=0)
    points: int = Field(default=0, ge=0)
    form: str = Field(default="", description="Last 5 results, e.g. 'WDLWW'")
    is_champions_league: bool = Field(default=False)
    is_europa_league: bool = Field(default=False)
    is_relegation: bool = Field(default=False)

    @property
    def goals_display(self) -> str:
        return f"{self.goals_for}:{self.goals_against}"


class StandingsTable(BaseModel):
    """Full standings table for a competition."""

    league_code: str
    league_name: str
    season: str = Field(default="")
    matchday: int = Field(default=0, ge=0)
    standings: list[Standing] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="")

    def top(self, n: int = 5) -> list[Standing]:
        return sorted(self.standings, key=lambda s: s.position)[:n]

    def bottom(self, n: int = 3) -> list[Standing]:
        return sorted(self.standings, key=lambda s: s.position)[-n:]

    def for_team(self, team_name: str) -> Standing | None:
        name_lower = team_name.lower()
        for row in self.standings:
            if name_lower in row.team_name.lower() or name_lower in row.team_short.lower():
                return row
        return None

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DemoUserCreate(BaseModel):
    email: EmailStr


class DemoUserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LeaderboardEntry(BaseModel):
    rank: int
    team_name: str
    team_tag: str
    team_id: str
    division: Optional[str] = None
    conference: Optional[str] = None
    wins: int
    losses: int
    points: int
    logo_url: Optional[str] = None


class LeaderboardResponse(BaseModel):
    data: List[LeaderboardEntry]
    total: int
    is_demo_limited: bool = False


class TeamMember(BaseModel):
    puuid: str
    name: str
    tag: str
    role: Optional[str] = None


class TeamInfo(BaseModel):
    team_id: str
    team_name: str
    team_tag: str
    division: Optional[str] = None
    conference: Optional[str] = None
    region: str
    wins: int
    losses: int
    points: int
    logo_url: Optional[str] = None
    members: List[TeamMember]
    created_at: Optional[str] = None


class MatchHistoryEntry(BaseModel):
    match_id: str
    map_name: str
    game_mode: str
    started_at: str
    rounds_won: int
    rounds_lost: int
    result: str


class TeamHistoryResponse(BaseModel):
    team_info: TeamInfo
    matches: List[MatchHistoryEntry]
    is_demo_limited: bool = False


class PlayerMMR(BaseModel):
    current_tier: int
    current_tier_name: str
    ranking_in_tier: int
    mmr_change: int
    elo: int
    games_needed_for_rating: int


class PlayerProfile(BaseModel):
    puuid: str
    name: str
    tag: str
    account_level: int
    card_url: Optional[str] = None
    mmr: Optional[PlayerMMR] = None


class MatchDetails(BaseModel):
    match_id: str
    map_name: str
    game_mode: str
    started_at: str
    team_won: str
    rounds: List[Dict[str, Any]]
    players: List[Dict[str, Any]]


class SearchResult(BaseModel):
    teams: List[TeamInfo]
    total: int
    is_demo_limited: bool = False


class ConferenceInfo(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None


class SeasonInfo(BaseModel):
    id: str
    name: str
    start_date: str
    end_date: str


class HealthCheck(BaseModel):
    status: str
    version: str
    demo_mode: bool
    timestamp: datetime

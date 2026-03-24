"""
Router /api/v1/my-team — gestión del equipo vinculado del usuario autenticado.

Endpoints:
  POST   /my-team/link               Vincula equipo + snapshot inicial
  GET    /my-team                    Datos en vivo del equipo
  GET    /my-team/snapshots          Historial de snapshots + tendencias
  GET    /my-team/players/snapshots  MMR histórico de todos los jugadores
  DELETE /my-team                    Desvincular (conserva historial)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlayerSnapshot, SavedTeam, TeamSnapshot
from app.db.session import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.services import snapshot_service
from app.services.valorant_api import ValorantAPIClient

router = APIRouter()
_api = ValorantAPIClient()


# ─────────────────────────────────────────
# Schemas internos del router
# ─────────────────────────────────────────


class TeamLinkRequest(BaseModel):
    team_id: str = Field(..., description="ID interno de Premier en Henrik API")
    team_name: str = Field(..., max_length=255)
    team_tag: str = Field(..., max_length=50)
    region: str = Field(..., pattern="^(NA|EU|AP|KR|LATAM|BR)$")
    division: Optional[str] = None
    conference: Optional[str] = None


class SavedTeamOut(BaseModel):
    id: str
    team_id: str
    team_name: str
    team_tag: str
    region: str
    division: Optional[str]
    conference: Optional[str]
    linked_at: datetime
    is_primary: bool

    class Config:
        from_attributes = True


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────


async def _get_primary_team(db: AsyncSession, user: User) -> Optional[SavedTeam]:
    result = await db.execute(
        select(SavedTeam).where(
            SavedTeam.user_id == user.id,
            SavedTeam.is_primary.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _require_team(db: AsyncSession, user: User) -> SavedTeam:
    team = await _get_primary_team(db, user)
    if not team:
        raise HTTPException(status_code=404, detail="No tienes un equipo vinculado")
    return team


# ─────────────────────────────────────────
# POST /my-team/link
# ─────────────────────────────────────────


@router.post("/link", status_code=201)
async def link_team(
    body: TeamLinkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Vincula un equipo Premier al usuario. Dispara snapshot inicial."""
    existing = await db.execute(
        select(SavedTeam).where(
            SavedTeam.user_id == user.id,
            SavedTeam.team_id == body.team_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Ya tienes este equipo vinculado",
            headers={"X-Error-Code": "TEAM_ALREADY_LINKED"},
        )

    # Si ya tiene un equipo primario, quitarle el flag
    existing_primary = await _get_primary_team(db, user)
    if existing_primary:
        existing_primary.is_primary = False

    saved = SavedTeam(
        user_id=user.id,
        team_id=body.team_id,
        team_name=body.team_name,
        team_tag=body.team_tag,
        region=body.region,
        division=body.division,
        conference=body.conference,
        is_primary=True,
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)

    # Snapshot inicial del equipo
    ts = await snapshot_service.take_team_snapshot(
        db, body.team_id, body.region, source="onboarding"
    )

    # Snapshot inicial de jugadores del roster
    try:
        raw = await _api.get_team_by_id(body.team_id)
        roster: List[Dict[str, Any]] = (raw.get("data") or {}).get("members", [])
    except Exception:
        roster = []

    for member in roster:
        puuid = member.get("puuid") or ""
        name = member.get("name") or ""
        tag = member.get("tag") or ""
        if puuid and name and tag:
            await snapshot_service.take_player_snapshot(
                db,
                puuid=puuid,
                team_id=body.team_id,
                player_name=name,
                player_tag=tag,
                region=body.region,
            )

    initial_snapshot = None
    if ts:
        initial_snapshot = {
            "rank_position": ts.rank_position,
            "wins": ts.wins,
            "losses": ts.losses,
        }

    return {
        "team": {
            "id": str(saved.id),
            "team_id": saved.team_id,
            "team_name": saved.team_name,
            "team_tag": saved.team_tag,
            "region": saved.region,
            "division": saved.division,
            "conference": saved.conference,
            "linked_at": saved.linked_at.isoformat() if saved.linked_at else None,
        },
        "initial_snapshot": initial_snapshot,
    }


# ─────────────────────────────────────────
# GET /my-team
# ─────────────────────────────────────────


@router.get("")
async def get_my_team(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retorna el equipo principal del usuario con datos en tiempo real desde Henrik."""
    saved = await _require_team(db, user)

    live_data: Dict[str, Any] = {}
    roster: List[Dict[str, Any]] = []

    try:
        raw = await _api.get_team_by_id(saved.team_id)
        data = raw.get("data") or {}
        live_data = {
            "rank_position": data.get("placement"),
            "wins": data.get("wins"),
            "losses": data.get("losses"),
            "division": data.get("division"),
            "conference": data.get("conference"),
        }
        members = data.get("members") or []
        for m in members:
            roster.append(
                {
                    "puuid": m.get("puuid"),
                    "name": m.get("name"),
                    "tag": m.get("tag"),
                }
            )
    except Exception:
        pass

    # Último snapshot para `last_snapshot_at`
    snap_result = await db.execute(
        select(TeamSnapshot)
        .where(TeamSnapshot.team_id == saved.team_id)
        .order_by(TeamSnapshot.snapshot_at.desc())
        .limit(1)
    )
    last_snap = snap_result.scalar_one_or_none()

    return {
        "saved_team": {
            "id": str(saved.id),
            "team_id": saved.team_id,
            "team_name": saved.team_name,
            "team_tag": saved.team_tag,
            "region": saved.region,
            "division": saved.division,
            "conference": saved.conference,
            "linked_at": saved.linked_at.isoformat() if saved.linked_at else None,
        },
        "live": live_data,
        "roster": roster,
        "last_snapshot_at": (
            last_snap.snapshot_at.isoformat() if last_snap and last_snap.snapshot_at else None
        ),
    }


# ─────────────────────────────────────────
# GET /my-team/snapshots
# ─────────────────────────────────────────


@router.get("/snapshots")
async def get_team_snapshots(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Historial de snapshots del equipo + tendencias de rank y win_rate."""
    saved = await _require_team(db, user)

    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(TeamSnapshot)
        .where(
            TeamSnapshot.team_id == saved.team_id,
            TeamSnapshot.snapshot_at >= since,
        )
        .order_by(TeamSnapshot.snapshot_at.asc())
    )
    snaps = list(result.scalars().all())

    trend = await snapshot_service.get_team_trend(db, saved.team_id, days)

    return {
        "team_id": saved.team_id,
        "snapshots": [
            {
                "snapshot_at": s.snapshot_at.isoformat(),
                "rank_position": s.rank_position,
                "wins": s.wins,
                "losses": s.losses,
                "points": s.points,
            }
            for s in snaps
        ],
        "trend": trend,
    }


# ─────────────────────────────────────────
# GET /my-team/players/snapshots
# ─────────────────────────────────────────


@router.get("/players/snapshots")
async def get_player_snapshots(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """MMR histórico de todos los jugadores del equipo con tendencias."""
    saved = await _require_team(db, user)
    players = await snapshot_service.get_player_trends(db, saved.team_id, days)
    return {"players": players}


# ─────────────────────────────────────────
# DELETE /my-team
# ─────────────────────────────────────────


@router.delete("")
async def unlink_team(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Desvincular equipo principal. Los snapshots históricos se conservan."""
    saved = await _require_team(db, user)
    await db.delete(saved)
    await db.commit()
    return {"message": "Equipo desvinculado. El historial se conserva."}

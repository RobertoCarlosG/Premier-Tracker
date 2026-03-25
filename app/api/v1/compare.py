"""
Router /api/v1/compare — comparativa entre el equipo del usuario y un rival.

Endpoints:
  GET /compare/teams   Compara mi equipo vs un equipo rival
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.api.v1.my_team import _require_team
from app.services import snapshot_service
from app.services.valorant_api import ValorantAPIClient

router = APIRouter()
_api = ValorantAPIClient()


def _calc_win_rate(wins: Optional[int], losses: Optional[int]) -> Optional[float]:
    if wins is None or losses is None:
        return None
    total = wins + losses
    return round(wins / total, 4) if total > 0 else None


def _build_team_data(
    name: str,
    tag: str,
    live: Dict[str, Any],
    rank_trend_7d: Optional[int],
) -> Dict[str, Any]:
    wins = live.get("wins")
    losses = live.get("losses")
    return {
        "name": name,
        "tag": tag,
        "rank_position": live.get("placement") or live.get("rank_position"),
        "wins": wins,
        "losses": losses,
        "win_rate": _calc_win_rate(wins, losses),
        "rank_trend_7d": rank_trend_7d,
        "division": live.get("division"),
        "conference": live.get("conference"),
    }


@router.get("/teams")
async def compare_teams(
    rival_team_id: str = Query(..., description="ID del equipo rival en Henrik API"),
    rival_region: str = Query("NA", description="Región del equipo rival"),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Compara el equipo principal del usuario vs un equipo rival.
    Retorna datos en vivo de ambos + tendencias del equipo propio.
    """
    # Obtener equipo del usuario
    my_saved = await _require_team(db, user)

    # Obtener datos en vivo de mi equipo
    try:
        my_raw = await _api.get_team_by_id(my_saved.team_id)
        my_live: Dict[str, Any] = my_raw.get("data") or {}
    except Exception:
        my_live = {
            "wins": None,
            "losses": None,
            "placement": None,
            "division": my_saved.division,
            "conference": my_saved.conference,
        }

    # Obtener datos en vivo del rival
    try:
        rival_raw = await _api.get_team_by_id(rival_team_id)
        rival_live: Dict[str, Any] = rival_raw.get("data") or {}
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron datos del equipo rival",
        )

    if not rival_live:
        raise HTTPException(status_code=404, detail="Equipo rival no encontrado")

    # Tendencia de mi equipo desde snapshots
    my_trend = await snapshot_service.get_team_trend(db, my_saved.team_id, days)
    my_rank_trend_7d: Optional[int] = my_trend.get("rank_delta_7d")

    # Construir datos de cada lado
    my_team_data = _build_team_data(
        name=my_saved.team_name,
        tag=my_saved.team_tag,
        live=my_live,
        rank_trend_7d=my_rank_trend_7d,
    )
    rival_team_data = _build_team_data(
        name=rival_live.get("name") or "Rival",
        tag=rival_live.get("tag") or "",
        live=rival_live,
        rank_trend_7d=None,  # No tenemos snapshots del rival
    )

    # Métricas de comparación
    my_pos = my_team_data["rank_position"]
    rival_pos = rival_team_data["rank_position"]
    rank_gap = None
    my_team_better = None
    if my_pos is not None and rival_pos is not None:
        # Posición menor = mejor rank
        rank_gap = abs(my_pos - rival_pos)
        my_team_better = my_pos < rival_pos

    my_wr = my_team_data["win_rate"] or 0.0
    rival_wr = rival_team_data["win_rate"] or 0.0
    win_rate_gap = round(abs(my_wr - rival_wr), 4)

    return {
        "my_team": my_team_data,
        "rival_team": rival_team_data,
        "comparison": {
            "rank_gap": rank_gap,
            "win_rate_gap": win_rate_gap,
            "my_team_better": my_team_better,
        },
    }

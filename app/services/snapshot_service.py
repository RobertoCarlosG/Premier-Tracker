"""
Servicio de snapshots: captura y análisis de tendencias para equipos y jugadores.

Flujo principal:
  take_team_snapshot  → llama Henrik Premier API → inserta TeamSnapshot
  take_player_snapshot → llama Henrik MMR v2     → inserta PlayerSnapshot
  get_team_trend      → calcula deltas de rank/win_rate en ventanas de tiempo
  get_player_trends   → agrega tendencias de MMR por jugador del equipo
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlayerSnapshot, SavedTeam, TeamSnapshot
from app.services.valorant_api import ValorantAPIClient

logger = logging.getLogger(__name__)

_api = ValorantAPIClient()


# ─────────────────────────────────────────
# Team snapshots
# ─────────────────────────────────────────


async def take_team_snapshot(
    db: AsyncSession,
    team_id: str,
    region: str,
    source: str = "cron",
) -> Optional[TeamSnapshot]:
    """
    Obtiene datos actuales del equipo desde Henrik y guarda un TeamSnapshot.
    Retorna el snapshot creado, o None si Henrik no devuelve datos.
    """
    try:
        raw = await _api.get_team_by_id(team_id)
    except Exception:
        logger.warning("Henrik no respondió para team_id=%s", team_id)
        return None

    data: Dict[str, Any] = raw.get("data") or {}
    if not data:
        logger.warning("Henrik devolvió data vacía para team_id=%s", team_id)
        return None

    snapshot = TeamSnapshot(
        team_id=team_id,
        region=region,
        rank_position=data.get("placement"),
        division=data.get("division"),
        conference=data.get("conference"),
        wins=data.get("wins"),
        losses=data.get("losses"),
        points=data.get("score"),
        source=source,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def take_player_snapshot(
    db: AsyncSession,
    puuid: str,
    team_id: str,
    player_name: str,
    player_tag: str,
    region: str,
) -> Optional[PlayerSnapshot]:
    """
    Obtiene el MMR actual del jugador desde Henrik v2 y guarda un PlayerSnapshot.
    """
    try:
        raw = await _api.get_mmr(region, player_name, player_tag)
    except Exception:
        logger.warning("Henrik MMR falló para %s#%s", player_name, player_tag)
        return None

    data: Dict[str, Any] = raw.get("data") or {}
    if not data:
        return None

    snapshot = PlayerSnapshot(
        team_id=team_id,
        puuid=puuid,
        player_name=player_name,
        player_tag=player_tag,
        region=region,
        mmr_current=data.get("elo"),
        rank_tier=data.get("currenttierpatched"),
        rr_current=data.get("ranking_in_tier"),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


# ─────────────────────────────────────────
# Team trend
# ─────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_team_trend(
    db: AsyncSession,
    team_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Calcula tendencias de posición y win_rate para un equipo en la ventana dada.

    Retorna:
        rank_delta_7d, rank_delta_30d, win_rate_7d, win_rate_30d
    """
    since = _utcnow() - timedelta(days=days)
    result = await db.execute(
        select(TeamSnapshot)
        .where(
            TeamSnapshot.team_id == team_id,
            TeamSnapshot.snapshot_at >= since,
        )
        .order_by(TeamSnapshot.snapshot_at.asc())
    )
    snapshots: List[TeamSnapshot] = list(result.scalars().all())

    def _delta_rank(window_days: int) -> Optional[int]:
        cutoff = _utcnow() - timedelta(days=window_days)
        window = [s for s in snapshots if s.snapshot_at >= cutoff]
        if len(window) < 2:
            return None
        first_rank = window[0].rank_position
        last_rank = window[-1].rank_position
        if first_rank is None or last_rank is None:
            return None
        # Negativo = mejora de posición (bajó el número de rank)
        return last_rank - first_rank

    def _win_rate(window_days: int) -> Optional[float]:
        cutoff = _utcnow() - timedelta(days=window_days)
        window = [s for s in snapshots if s.snapshot_at >= cutoff]
        if not window:
            return None
        latest = window[-1]
        w = latest.wins or 0
        l = latest.losses or 0
        total = w + l
        return round(w / total, 4) if total > 0 else None

    return {
        "rank_delta_7d": _delta_rank(7),
        "rank_delta_30d": _delta_rank(30),
        "win_rate_7d": _win_rate(7),
        "win_rate_30d": _win_rate(30),
    }


# ─────────────────────────────────────────
# Player trends
# ─────────────────────────────────────────


async def get_player_trends(
    db: AsyncSession,
    team_id: str,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Retorna snapshots y tendencias de MMR por jugador del equipo.
    """
    since = _utcnow() - timedelta(days=days)
    result = await db.execute(
        select(PlayerSnapshot)
        .where(
            PlayerSnapshot.team_id == team_id,
            PlayerSnapshot.snapshot_at >= since,
        )
        .order_by(PlayerSnapshot.puuid, PlayerSnapshot.snapshot_at.asc())
    )
    rows: List[PlayerSnapshot] = list(result.scalars().all())

    # Agrupar por puuid
    by_puuid: Dict[str, List[PlayerSnapshot]] = {}
    for row in rows:
        by_puuid.setdefault(row.puuid, []).append(row)

    players = []
    for puuid, snaps in by_puuid.items():
        snap_list = [
            {
                "snapshot_at": s.snapshot_at.isoformat(),
                "mmr_current": s.mmr_current,
                "rank_tier": s.rank_tier,
                "rr_current": s.rr_current,
            }
            for s in snaps
        ]

        def _mmr_delta(window_days: int) -> Optional[int]:
            cutoff = _utcnow() - timedelta(days=window_days)
            window = [s for s in snaps if s.snapshot_at >= cutoff]
            if len(window) < 2:
                return None
            first = window[0].mmr_current
            last = window[-1].mmr_current
            if first is None or last is None:
                return None
            return last - first

        latest = snaps[-1]
        players.append(
            {
                "puuid": puuid,
                "name": latest.player_name,
                "tag": latest.player_tag,
                "snapshots": snap_list,
                "trend": {
                    "mmr_delta_7d": _mmr_delta(7),
                    "mmr_delta_30d": _mmr_delta(30),
                },
            }
        )

    return players


# ─────────────────────────────────────────
# Bulk snapshot (usado por el cron job)
# ─────────────────────────────────────────


async def snapshot_all_teams(db: AsyncSession) -> None:
    """
    Recorre todos los saved_teams y toma un snapshot diario de cada uno.
    Llamado por el scheduler APScheduler.
    """
    result = await db.execute(select(SavedTeam))
    teams: List[SavedTeam] = list(result.scalars().all())
    logger.info("Iniciando snapshot diario para %d equipos", len(teams))

    for team in teams:
        ts = await take_team_snapshot(db, team.team_id, team.region, source="cron")
        if ts is None:
            continue

        # Obtener roster desde Henrik para tomar snapshots de jugadores
        try:
            raw = await _api.get_team_by_id(team.team_id)
            roster: List[Dict[str, Any]] = (raw.get("data") or {}).get("members", [])
        except Exception:
            roster = []

        for member in roster:
            puuid = member.get("puuid") or ""
            name = member.get("name") or ""
            tag = member.get("tag") or ""
            if puuid and name and tag:
                await take_player_snapshot(
                    db,
                    puuid=puuid,
                    team_id=team.team_id,
                    player_name=name,
                    player_tag=tag,
                    region=team.region,
                )

    logger.info("Snapshot diario completado.")

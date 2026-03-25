"""
Tests unitarios de snapshot_service (Fase 3).

Estrategia: todos los tests usan mocks para DB y Henrik API.
No requieren base de datos real.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import snapshot_service
from app.db.models import TeamSnapshot, PlayerSnapshot, SavedTeam


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────


def _make_team_snapshot(
    team_id: str = "team-abc",
    rank_position: int = 5,
    wins: int = 8,
    losses: int = 2,
    days_ago: float = 0.0,
) -> MagicMock:
    snap = MagicMock(spec=TeamSnapshot)
    snap.team_id = team_id
    snap.rank_position = rank_position
    snap.wins = wins
    snap.losses = losses
    snap.snapshot_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return snap


def _make_player_snapshot(
    puuid: str = "puuid-1",
    player_name: str = "Player",
    player_tag: str = "123",
    team_id: str = "team-abc",
    mmr_current: int = 1800,
    rank_tier: str = "Immortal 1",
    rr_current: int = 30,
    days_ago: float = 0.0,
) -> MagicMock:
    snap = MagicMock(spec=PlayerSnapshot)
    snap.puuid = puuid
    snap.player_name = player_name
    snap.player_tag = player_tag
    snap.team_id = team_id
    snap.mmr_current = mmr_current
    snap.rank_tier = rank_tier
    snap.rr_current = rr_current
    snap.snapshot_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return snap


def _mock_db_scalars(rows: List[Any]) -> AsyncMock:
    """Devuelve un AsyncSession mock que retorna rows en execute().scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db = AsyncMock()
    db.execute.return_value = result
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ─────────────────────────────────────────
# get_team_trend — sin snapshots
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_team_trend_no_snapshots():
    """Sin snapshots → todos los deltas son None."""
    db = _mock_db_scalars([])
    trend = await snapshot_service.get_team_trend(db, "team-xyz", days=30)

    assert trend["rank_delta_7d"] is None
    assert trend["rank_delta_30d"] is None
    assert trend["win_rate_7d"] is None
    assert trend["win_rate_30d"] is None


@pytest.mark.asyncio
async def test_get_team_trend_single_snapshot():
    """Un único snapshot → no hay delta (necesita al menos 2)."""
    snap = _make_team_snapshot(rank_position=10, wins=5, losses=2, days_ago=3)
    db = _mock_db_scalars([snap])

    trend = await snapshot_service.get_team_trend(db, "team-abc", days=30)
    assert trend["rank_delta_7d"] is None


@pytest.mark.asyncio
async def test_get_team_trend_improvement():
    """Equipo subió de posición #10 → #7 en 7 días (delta = -3 = mejora)."""
    old = _make_team_snapshot(rank_position=10, wins=5, losses=2, days_ago=6)
    new = _make_team_snapshot(rank_position=7, wins=8, losses=2, days_ago=0)
    db = _mock_db_scalars([old, new])

    trend = await snapshot_service.get_team_trend(db, "team-abc", days=30)
    assert trend["rank_delta_7d"] == -3   # bajó número = mejora
    assert trend["win_rate_7d"] == 0.8    # 8 / (8+2)


@pytest.mark.asyncio
async def test_get_team_trend_regression():
    """Equipo bajó de posición #5 → #9 (delta = +4 = empeora)."""
    old = _make_team_snapshot(rank_position=5, wins=10, losses=2, days_ago=6)
    new = _make_team_snapshot(rank_position=9, wins=10, losses=5, days_ago=0)
    db = _mock_db_scalars([old, new])

    trend = await snapshot_service.get_team_trend(db, "team-abc", days=30)
    assert trend["rank_delta_7d"] == 4


# ─────────────────────────────────────────
# get_player_trends — sin jugadores
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_player_trends_empty():
    """Sin snapshots de jugadores → lista vacía."""
    db = _mock_db_scalars([])
    players = await snapshot_service.get_player_trends(db, "team-abc", days=30)
    assert players == []


@pytest.mark.asyncio
async def test_get_player_trends_groups_by_puuid():
    """Dos snapshots del mismo jugador → un solo resultado con trend."""
    # Ventana 7d: evitar days_ago=7 justo en el borde (clock skew hace caer un punto fuera).
    old = _make_player_snapshot(puuid="p1", player_name="Ace", mmr_current=1700, days_ago=3)
    new = _make_player_snapshot(puuid="p1", player_name="Ace", mmr_current=1800, days_ago=0)
    db = _mock_db_scalars([old, new])

    players = await snapshot_service.get_player_trends(db, "team-abc", days=30)
    assert len(players) == 1
    assert players[0]["name"] == "Ace"
    assert players[0]["trend"]["mmr_delta_7d"] == 100


@pytest.mark.asyncio
async def test_get_player_trends_multiple_players():
    """Dos jugadores distintos → dos entradas en la lista."""
    snap_p1 = _make_player_snapshot(puuid="p1", player_name="PlayerA", days_ago=0)
    snap_p2 = _make_player_snapshot(puuid="p2", player_name="PlayerB", days_ago=0)
    db = _mock_db_scalars([snap_p1, snap_p2])

    players = await snapshot_service.get_player_trends(db, "team-abc", days=30)
    assert len(players) == 2
    names = {p["name"] for p in players}
    assert names == {"PlayerA", "PlayerB"}


# ─────────────────────────────────────────
# take_team_snapshot — manejo de errores de Henrik
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_team_snapshot_henrik_error_returns_none():
    """Si Henrik lanza excepción, retorna None sin propagar el error."""
    db = _mock_db_scalars([])

    with patch.object(snapshot_service._api, "get_team_by_id", side_effect=Exception("timeout")):
        result = await snapshot_service.take_team_snapshot(db, "team-abc", "NA", source="cron")

    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_take_team_snapshot_empty_data_returns_none():
    """Si Henrik devuelve data vacía, retorna None."""
    db = _mock_db_scalars([])

    with patch.object(snapshot_service._api, "get_team_by_id", return_value={"data": {}}):
        result = await snapshot_service.take_team_snapshot(db, "team-abc", "NA")

    assert result is None


@pytest.mark.asyncio
async def test_take_team_snapshot_success():
    """Henrik devuelve datos válidos → crea y retorna snapshot."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    henrik_response = {
        "data": {
            "placement": 4,
            "wins": 8,
            "losses": 2,
            "score": 350,
            "division": "Division 3",
            "conference": "East",
        }
    }

    with patch.object(snapshot_service._api, "get_team_by_id", return_value=henrik_response):
        result = await snapshot_service.take_team_snapshot(db, "team-abc", "NA", source="onboarding")

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert isinstance(result, TeamSnapshot)


# ─────────────────────────────────────────
# take_player_snapshot — manejo de errores
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_player_snapshot_henrik_error_returns_none():
    """Si Henrik MMR falla, retorna None sin propagar."""
    db = _mock_db_scalars([])

    with patch.object(snapshot_service._api, "get_mmr", side_effect=Exception("API error")):
        result = await snapshot_service.take_player_snapshot(
            db, puuid="p1", team_id="team-abc",
            player_name="Ace", player_tag="9999", region="NA"
        )

    assert result is None


# ─────────────────────────────────────────
# snapshot_all_teams
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_all_teams_no_teams():
    """Sin equipos → no llama a Henrik."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute.return_value = result

    with patch.object(snapshot_service._api, "get_team_by_id") as mock_api:
        await snapshot_service.snapshot_all_teams(db)
        mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_all_teams_calls_henrik_per_team():
    """Con un equipo, llama a Henrik y procesa snapshots."""
    team = MagicMock(spec=SavedTeam)
    team.team_id = "team-001"
    team.region = "EU"

    result = MagicMock()
    result.scalars.return_value.all.return_value = [team]
    db = AsyncMock()
    db.execute.return_value = result
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    henrik_team = {"data": {"placement": 3, "wins": 10, "losses": 3, "members": []}}

    with patch.object(snapshot_service._api, "get_team_by_id", return_value=henrik_team):
        await snapshot_service.snapshot_all_teams(db)

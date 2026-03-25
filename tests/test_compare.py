"""
Tests del endpoint /api/v1/compare (Fase 4).

Estrategia:
- Tests sin auth: verifican protección del endpoint (401).
- Tests con auth: usan JWT sintético + mocks de DB y Henrik API.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.main import app
from app.db.models import SavedTeam, User

JWT_SECRET = settings.JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"
BASE = "/api/v1/compare"

_FAKE_USER_ID = str(uuid.uuid4())
_FAKE_TEAM_ID = "premier-team-abc123"
_RIVAL_TEAM_ID = "premier-rival-xyz789"


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────


def _make_token(user_id: str | None = None, role: str = "user") -> str:
    uid = user_id or str(uuid.uuid4())
    now = datetime.utcnow()
    payload = {
        "sub": uid,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid.UUID(_FAKE_USER_ID)
    user.email = "test@example.com"
    user.display_name = "TestUser"
    user.role = "user"
    user.is_verified = True
    return user


def _fake_saved_team() -> MagicMock:
    team = MagicMock(spec=SavedTeam)
    team.id = uuid.uuid4()
    team.team_id = _FAKE_TEAM_ID
    team.team_name = "Sharpshooters"
    team.team_tag = "SHRP"
    team.region = "NA"
    team.division = "Division 3"
    team.conference = "East"
    team.is_primary = True
    return team


def _henrik_team_response(
    name: str = "TestTeam",
    tag: str = "TEST",
    placement: int = 4,
    wins: int = 8,
    losses: int = 2,
    division: str = "Division 3",
    conference: str = "East",
) -> dict:
    return {
        "data": {
            "name": name,
            "tag": tag,
            "placement": placement,
            "wins": wins,
            "losses": losses,
            "division": division,
            "conference": conference,
        }
    }


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────
# Tests de protección
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_requires_auth(client: AsyncClient):
    """GET /compare/teams sin token → 401."""
    response = await client.get(
        f"{BASE}/teams",
        params={"rival_team_id": _RIVAL_TEAM_ID, "rival_region": "NA"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_compare_missing_rival_team_id(client: AsyncClient):
    """GET /compare/teams sin rival_team_id → 422 (campo requerido)."""
    token = _make_token(_FAKE_USER_ID)
    response = await client.get(
        f"{BASE}/teams",
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


# ─────────────────────────────────────────
# Tests con auth + BD mockeada
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_no_team_linked(client: AsyncClient):
    """Usuario sin equipo vinculado → 404."""
    token = _make_token(_FAKE_USER_ID)

    fake_user = _fake_user()

    with (
        patch("app.dependencies.get_current_user", return_value=fake_user),
        patch("app.api.v1.compare._require_team", side_effect=Exception("No tienes un equipo vinculado")),
    ):
        from fastapi import HTTPException
        with patch(
            "app.api.v1.compare._require_team",
            side_effect=HTTPException(status_code=404, detail="No tienes un equipo vinculado"),
        ):
            response = await client.get(
                f"{BASE}/teams",
                headers=_auth_headers(token),
                params={"rival_team_id": _RIVAL_TEAM_ID, "rival_region": "NA"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_rival_not_found(client: AsyncClient):
    """Henrik devuelve data vacía para el rival → 404."""
    token = _make_token(_FAKE_USER_ID)
    fake_user = _fake_user()
    fake_team = _fake_saved_team()

    with (
        patch("app.dependencies.get_current_user", return_value=fake_user),
        patch("app.api.v1.compare._require_team", return_value=fake_team),
        patch(
            "app.api.v1.compare._api.get_team_by_id",
            side_effect=[
                _henrik_team_response(),  # mi equipo OK
                Exception("not found"),   # rival falla
            ],
        ),
        patch(
            "app.services.snapshot_service.get_team_trend",
            return_value={"rank_delta_7d": None, "rank_delta_30d": None,
                          "win_rate_7d": None, "win_rate_30d": None},
        ),
    ):
        response = await client.get(
            f"{BASE}/teams",
            headers=_auth_headers(token),
            params={"rival_team_id": _RIVAL_TEAM_ID, "rival_region": "NA"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_success(client: AsyncClient):
    """Comparativa exitosa: retorna my_team, rival_team y comparison."""
    token = _make_token(_FAKE_USER_ID)
    fake_user = _fake_user()
    fake_team = _fake_saved_team()

    my_henrik = _henrik_team_response(name="Sharpshooters", tag="SHRP", placement=4, wins=8, losses=2)
    rival_henrik = _henrik_team_response(name="Rival Squad", tag="RIVL", placement=7, wins=6, losses=4)

    with (
        patch("app.dependencies.get_current_user", return_value=fake_user),
        patch("app.api.v1.compare._require_team", return_value=fake_team),
        patch(
            "app.api.v1.compare._api.get_team_by_id",
            side_effect=[my_henrik, rival_henrik],
        ),
        patch(
            "app.services.snapshot_service.get_team_trend",
            return_value={"rank_delta_7d": -2, "rank_delta_30d": -5,
                          "win_rate_7d": 0.75, "win_rate_30d": 0.70},
        ),
    ):
        response = await client.get(
            f"{BASE}/teams",
            headers=_auth_headers(token),
            params={"rival_team_id": _RIVAL_TEAM_ID, "rival_region": "NA"},
        )

    assert response.status_code == 200
    body = response.json()

    # Shape correcta
    assert "my_team" in body
    assert "rival_team" in body
    assert "comparison" in body

    # Mi equipo
    assert body["my_team"]["name"] == "Sharpshooters"
    assert body["my_team"]["wins"] == 8
    assert body["my_team"]["rank_position"] == 4
    assert body["my_team"]["win_rate"] == 0.8
    assert body["my_team"]["rank_trend_7d"] == -2

    # Rival
    assert body["rival_team"]["name"] == "Rival Squad"
    assert body["rival_team"]["rank_position"] == 7

    # Comparación
    comparison = body["comparison"]
    assert comparison["rank_gap"] == 3        # |4 - 7|
    assert comparison["my_team_better"] is True  # posición menor = mejor
    assert comparison["win_rate_gap"] == pytest.approx(0.2, abs=0.01)


@pytest.mark.asyncio
async def test_compare_both_same_rank(client: AsyncClient):
    """Misma posición → rank_gap = 0, my_team_better = False."""
    token = _make_token(_FAKE_USER_ID)
    fake_user = _fake_user()
    fake_team = _fake_saved_team()

    tied_henrik = _henrik_team_response(placement=5, wins=6, losses=4)

    with (
        patch("app.dependencies.get_current_user", return_value=fake_user),
        patch("app.api.v1.compare._require_team", return_value=fake_team),
        patch(
            "app.api.v1.compare._api.get_team_by_id",
            side_effect=[tied_henrik, tied_henrik],
        ),
        patch(
            "app.services.snapshot_service.get_team_trend",
            return_value={"rank_delta_7d": 0, "rank_delta_30d": 0,
                          "win_rate_7d": 0.6, "win_rate_30d": 0.6},
        ),
    ):
        response = await client.get(
            f"{BASE}/teams",
            headers=_auth_headers(token),
            params={"rival_team_id": _RIVAL_TEAM_ID, "rival_region": "NA"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["comparison"]["rank_gap"] == 0
    assert body["comparison"]["my_team_better"] is False

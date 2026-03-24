"""
Tests de /api/v1/my-team (Fase 2).

Estrategia:
- Tests sin auth: verifican que los endpoints están protegidos (no necesitan BD).
- Tests con auth: usan un JWT sintético válido + mocks de la BD y de Henrik API
  para no depender de servicios externos.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.main import app

JWT_SECRET = settings.JWT_SECRET or settings.SECRET_KEY
ALGORITHM = "HS256"

BASE = "/api/v1/my-team"


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────


def _make_token(user_id: str | None = None, role: str = "user") -> str:
    """Genera un JWT de acceso válido para tests."""
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


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────
# Tests de protección (sin BD real)
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_my_team_requires_auth(client: AsyncClient):
    """GET /my-team sin token → 401."""
    response = await client.get(BASE)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_link_team_requires_auth(client: AsyncClient):
    """POST /my-team/link sin token → 401."""
    response = await client.post(f"{BASE}/link", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_snapshots_requires_auth(client: AsyncClient):
    """GET /my-team/snapshots sin token → 401."""
    response = await client.get(f"{BASE}/snapshots")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_player_snapshots_requires_auth(client: AsyncClient):
    """GET /my-team/players/snapshots sin token → 401."""
    response = await client.get(f"{BASE}/players/snapshots")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_my_team_requires_auth(client: AsyncClient):
    """DELETE /my-team sin token → 401."""
    response = await client.delete(BASE)
    assert response.status_code == 401


# ─────────────────────────────────────────
# Tests con usuario autenticado + BD mockeada
# ─────────────────────────────────────────

_FAKE_USER_ID = str(uuid.uuid4())
_FAKE_TEAM_ID = "premier-team-abc123"


def _fake_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.UUID(_FAKE_USER_ID)
    user.email = "test@example.com"
    user.display_name = "TestUser"
    user.role = "user"
    user.is_verified = True
    return user


@pytest.mark.asyncio
async def test_get_my_team_no_team_linked(client: AsyncClient):
    """GET /my-team con usuario válido pero sin equipo → 404."""
    token = _make_token(_FAKE_USER_ID)

    with (
        patch("app.dependencies.get_current_user", return_value=_fake_user()),
        patch(
            "app.api.v1.my_team._get_primary_team",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await client.get(BASE, headers=_auth_headers(token))

    assert response.status_code == 404
    assert "equipo" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_link_team_validation_error(client: AsyncClient):
    """POST /my-team/link con región inválida → 422."""
    token = _make_token(_FAKE_USER_ID)

    with patch("app.dependencies.get_current_user", return_value=_fake_user()):
        response = await client.post(
            f"{BASE}/link",
            headers=_auth_headers(token),
            json={
                "team_id": "abc",
                "team_name": "MyTeam",
                "team_tag": "MT",
                "region": "INVALID_REGION",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_link_team_duplicate(client: AsyncClient):
    """POST /my-team/link con equipo ya vinculado → 409."""
    token = _make_token(_FAKE_USER_ID)

    fake_saved = MagicMock()
    fake_saved.id = uuid.uuid4()
    fake_saved.team_id = _FAKE_TEAM_ID

    with (
        patch("app.dependencies.get_current_user", return_value=_fake_user()),
        # Simula que el SELECT retorna un equipo ya existente
        patch(
            "app.api.v1.my_team._get_primary_team",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("app.db.session.AsyncSessionLocal"),
        patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute",
            new_callable=AsyncMock,
        ) as mock_exec,
    ):
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = fake_saved
        mock_exec.return_value = scalar_result

        response = await client.post(
            f"{BASE}/link",
            headers=_auth_headers(token),
            json={
                "team_id": _FAKE_TEAM_ID,
                "team_name": "My Team",
                "team_tag": "MT",
                "region": "NA",
            },
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_snapshots_no_team(client: AsyncClient):
    """GET /my-team/snapshots sin equipo vinculado → 404."""
    token = _make_token(_FAKE_USER_ID)

    with (
        patch("app.dependencies.get_current_user", return_value=_fake_user()),
        patch(
            "app.api.v1.my_team._get_primary_team",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await client.get(f"{BASE}/snapshots", headers=_auth_headers(token))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_player_snapshots_no_team(client: AsyncClient):
    """GET /my-team/players/snapshots sin equipo vinculado → 404."""
    token = _make_token(_FAKE_USER_ID)

    with (
        patch("app.dependencies.get_current_user", return_value=_fake_user()),
        patch(
            "app.api.v1.my_team._get_primary_team",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await client.get(
            f"{BASE}/players/snapshots", headers=_auth_headers(token)
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_team_no_team(client: AsyncClient):
    """DELETE /my-team sin equipo vinculado → 404."""
    token = _make_token(_FAKE_USER_ID)

    with (
        patch("app.dependencies.get_current_user", return_value=_fake_user()),
        patch(
            "app.api.v1.my_team._get_primary_team",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = await client.delete(BASE, headers=_auth_headers(token))

    assert response.status_code == 404


# ─────────────────────────────────────────
# Tests de snapshot service (unitarios)
# ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_team_snapshot_empty_data():
    """take_team_snapshot retorna None cuando Henrik devuelve data vacía."""
    from app.services import snapshot_service

    mock_db = AsyncMock()

    with patch.object(
        snapshot_service._api,
        "get_team_by_id",
        new_callable=AsyncMock,
        return_value={"status": 200, "data": None},
    ):
        result = await snapshot_service.take_team_snapshot(
            mock_db, "team-123", "NA", source="cron"
        )

    assert result is None
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_take_team_snapshot_api_error():
    """take_team_snapshot retorna None cuando Henrik falla con excepción."""
    from app.services import snapshot_service

    mock_db = AsyncMock()

    with patch.object(
        snapshot_service._api,
        "get_team_by_id",
        new_callable=AsyncMock,
        side_effect=Exception("Connection error"),
    ):
        result = await snapshot_service.take_team_snapshot(
            mock_db, "team-123", "NA", source="cron"
        )

    assert result is None


@pytest.mark.asyncio
async def test_take_player_snapshot_api_error():
    """take_player_snapshot retorna None cuando Henrik MMR falla."""
    from app.services import snapshot_service

    mock_db = AsyncMock()

    with patch.object(
        snapshot_service._api,
        "get_mmr",
        new_callable=AsyncMock,
        side_effect=Exception("timeout"),
    ):
        result = await snapshot_service.take_player_snapshot(
            mock_db,
            puuid="riot-puuid-123",
            team_id="team-123",
            player_name="PlayerX",
            player_tag="1234",
            region="NA",
        )

    assert result is None


@pytest.mark.asyncio
async def test_get_team_trend_no_snapshots():
    """get_team_trend retorna Nones cuando no hay snapshots."""
    from app.services import snapshot_service
    from unittest.mock import MagicMock

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    trend = await snapshot_service.get_team_trend(mock_db, "team-123", days=30)

    assert trend["rank_delta_7d"] is None
    assert trend["rank_delta_30d"] is None
    assert trend["win_rate_7d"] is None
    assert trend["win_rate_30d"] is None

"""
Tests de autenticación (Fase 1).
Requiere BD con tablas auth (ejecutar scripts/migrate_auth.py).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    """POST /auth/register crea usuario y retorna mensaje."""
    email = f"test_register_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "display_name": "TestUser",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "correo" in data["message"].lower() or "verificar" in data["message"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """POST /auth/register con email existente retorna 409."""
    email = "dup@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "display_name": "User1", "password": "pass12345"},
    )
    response = await client.post(
        "/auth/register",
        json={"email": email, "display_name": "User2", "password": "pass12345"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_unverified(client: AsyncClient):
    """Login con usuario no verificado retorna 403."""
    email = "unverified@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "display_name": "Unverified", "password": "pass12345"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "pass12345"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login con contraseña incorrecta retorna 401."""
    email = "wrongpass@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "display_name": "User", "password": "correctpass"},
    )
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """GET /auth/verify-email con token inválido redirige a login?verified=false."""
    response = await client.get("/auth/verify-email?token=invalid-token")
    assert response.status_code == 302
    assert "verified=false" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_users_me_unauthorized(client: AsyncClient):
    """GET /users/me sin token retorna 401."""
    response = await client.get("/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """POST /auth/logout sin body retorna 200."""
    response = await client.post("/auth/logout")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_without_token(client: AsyncClient):
    """POST /auth/refresh sin token retorna 401."""
    response = await client.post("/auth/refresh", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_google_auth_redirect(client: AsyncClient):
    """GET /auth/google redirige a Google (o 503 si no configurado)."""
    response = await client.get("/auth/google", follow_redirects=False)
    assert response.status_code in (302, 503)

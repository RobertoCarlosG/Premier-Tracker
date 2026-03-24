"""
Servicio de autenticación: JWT, bcrypt, Google OAuth.
Implementación según 02_AUTH.md.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Tuple
from uuid import UUID, uuid4

import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import OAuthAccount, OAuthState, RefreshToken, User

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
JWT_SECRET = settings.JWT_SECRET or settings.SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def create_access_token(user_id: str | UUID, role: str = "user") -> str:
    """Genera un JWT access token (15 min)."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token() -> Tuple[str, str]:
    """Retorna (token_raw, token_hash). Guarda solo el hash en DB."""
    raw = str(uuid4())
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_password(password: str) -> str:
    """Hashea password con bcrypt (cost 12)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verifica password contra hash."""
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_email_verification_token(user_id: str | UUID) -> str:
    """Token JWT para verificación de email. Scope=email_verification, exp 24h."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "scope": "email_verification",
        "type": "email_verification",
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def verify_email_token(token: str) -> str | None:
    """Decodifica token de verificación. Retorna user_id o None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "email_verification" or payload.get("scope") != "email_verification":
            return None
        return payload.get("sub")
    except JWTError:
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Busca usuario por email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str | UUID) -> User | None:
    """Busca usuario por id."""
    return await db.get(User, UUID(str(user_id)) if isinstance(user_id, str) else user_id)


async def get_oauth_account(db: AsyncSession, provider: str, provider_id: str) -> OAuthAccount | None:
    """Busca OAuthAccount por provider y provider_id."""
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider, OAuthAccount.provider_id == provider_id
        )
    )
    return result.scalar_one_or_none()


async def save_oauth_state(db: AsyncSession, state: str) -> None:
    """Guarda state para CSRF. TTL 5 min."""
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    entry = OAuthState(state=state, expires_at=expires_at)
    db.add(entry)
    await db.commit()


async def validate_oauth_state(db: AsyncSession, state: str) -> bool:
    """Valida state y lo elimina. Retorna True si válido."""
    result = await db.execute(
        select(OAuthState).where(OAuthState.state == state, OAuthState.expires_at > datetime.utcnow())
    )
    entry = result.scalar_one_or_none()
    if not entry:
        return False
    await db.delete(entry)
    await db.commit()
    return True


def build_google_auth_url(state: str, redirect_uri: str) -> str:
    """Construye URL de autorización de Google con parámetros correctamente encoded."""
    from urllib.parse import urlencode

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str, redirect_uri: str) -> Tuple[str, str, str, str] | None:
    """
    Intercambia code por tokens y obtiene perfil.
    Retorna (sub, email, name) o None si falla.
    """
    async with httpx.AsyncClient() as client:
        # 1. Intercambiar code por tokens
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            return None
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            return None

        # 2. Obtener userinfo
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return None
        info = userinfo_resp.json()
        return (
            info.get("id"),  # sub
            info.get("email", ""),
            info.get("name", info.get("email", "User")),
            access_token,
        )

"""Router de autenticación según 02_AUTH.md."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import OAuthAccount, RefreshToken, User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import (
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    exchange_google_code,
    get_oauth_account,
    get_user_by_email,
    hash_password,
    save_oauth_state,
    validate_oauth_state,
    verify_email_token,
    verify_password,
)
from app.services.auth_service import build_google_auth_url
from app.services.email_service import send_verification_email
from app.middleware.rate_limit import check_login_rate_limit

router = APIRouter()
oauth2_scheme = HTTPBearer(auto_error=False)

ACCESS_EXPIRE = 15 * 60  # segundos
COOKIE_MAX_AGE_ACCESS = 900  # 15 min
COOKIE_MAX_AGE_REFRESH = 30 * 24 * 60 * 60  # 30 días


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Establece cookies httpOnly para tokens.
    En producción (HTTPS) usa SameSite=none para permitir peticiones cross-origin
    entre el frontend (Vercel) y el backend (Render).
    En desarrollo usa SameSite=lax (mismo origen).
    """
    is_secure = settings.FRONTEND_URL.startswith("https")
    samesite = "none" if is_secure else "lax"

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=COOKIE_MAX_AGE_ACCESS,
        httponly=True,
        secure=is_secure,
        samesite=samesite,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=COOKIE_MAX_AGE_REFRESH,
        httponly=True,
        secure=is_secure,
        samesite=samesite,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Elimina cookies de auth."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def _user_to_out(user: User, has_team: bool = False, team_id: str | None = None) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        has_team=has_team,
        team_id=team_id,
    )


async def _issue_tokens(
    db: AsyncSession,
    user: User,
    request: Request,
) -> tuple[str, str]:
    """Genera access + refresh, guarda refresh en DB. Retorna (access, refresh)."""
    access = create_access_token(user.id, user.role)
    refresh_raw, refresh_hash = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=30)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(rt)
    await db.commit()
    return access, refresh_raw


@router.post("/register")
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Registro con email + contraseña.
    No genera JWT hasta verificar email.
    """
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    user = User(
        email=data.email,
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    verification_token = create_email_verification_token(user.id)
    verification_url = f"{settings.BACKEND_URL}/auth/verify-email?token={verification_token}"
    await send_verification_email(data.email, verification_url)

    return {"message": "Revisa tu correo para verificar la cuenta"}


@router.post("/login")
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Login con email + contraseña. Retorna TokenResponse y setea cookies httpOnly."""
    ip = request.client.host if request.client else "unknown"
    if not check_login_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera 1 minuto.")

    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Debes verificar tu email antes de iniciar sesión. Revisa tu correo.",
        )

    user.last_login_at = datetime.utcnow()
    await db.commit()

    access, refresh = await _issue_tokens(db, user, request)
    _set_auth_cookies(response, access, refresh)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=ACCESS_EXPIRE,
        user=_user_to_out(user),
    )


@router.get("/google")
async def google_auth(
    request: Request,
    redirect_uri: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Inicia flujo OAuth de Google. Redirige al consent screen."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google OAuth no configurado")

    state = secrets.token_urlsafe(32)
    await save_oauth_state(db, state)

    # Prioridad: 1) query param explícito (dev), 2) GOOGLE_REDIRECT_URI del .env, 3) construido desde BACKEND_URL
    uri = (
        redirect_uri
        or settings.GOOGLE_REDIRECT_URI
        or f"{settings.BACKEND_URL}/auth/google/callback"
    )
    url = build_google_auth_url(state, uri)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Callback de Google. Crea/vincula usuario y redirige al frontend con tokens."""
    if not await validate_oauth_state(db, state):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido o expirado")

    redirect_uri = (
        settings.GOOGLE_REDIRECT_URI
        or f"{settings.BACKEND_URL}/auth/google/callback"
    )
    result = await exchange_google_code(code, redirect_uri)
    if not result:
        raise HTTPException(status_code=400, detail="Error al obtener datos de Google")

    google_sub, provider_email, display_name, access_token = result

    oauth_account = await get_oauth_account(db, "google", google_sub)
    if oauth_account:
        user = await db.get(User, oauth_account.user_id)
        if not user:
            raise HTTPException(status_code=500, detail="Usuario OAuth no encontrado")
    else:
        user = await get_user_by_email(db, provider_email)
        if user:
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_id=google_sub,
                provider_email=provider_email,
                access_token=access_token,
            )
            db.add(oauth_account)
        else:
            user = User(
                email=provider_email,
                display_name=display_name,
                password_hash=None,
                is_verified=True,
            )
            db.add(user)
            await db.flush()
            oauth_account = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_id=google_sub,
                provider_email=provider_email,
                access_token=access_token,
            )
            db.add(oauth_account)
        await db.commit()
        await db.refresh(user)

    user.last_login_at = datetime.utcnow()
    await db.commit()

    access, refresh = await _issue_tokens(db, user, request)
    _set_auth_cookies(response, access, refresh)

    from fastapi.responses import RedirectResponse
    redirect_url = f"{settings.FRONTEND_URL}/auth/callback?access_token={access}&refresh_token={refresh}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Rota refresh token. Acepta token en body o en cookie httpOnly."""
    refresh_token = None
    if data and data.refresh_token:
        refresh_token = data.refresh_token
    if not refresh_token:
        refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token requerido")

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow(),
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

    rt.revoked = True
    await db.commit()

    user = await db.get(User, rt.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    access, refresh_raw = await _issue_tokens(db, user, request)
    _set_auth_cookies(response, access, refresh_raw)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh_raw,
        token_type="bearer",
        expires_in=ACCESS_EXPIRE,
        user=_user_to_out(user),
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Revoca el refresh token. Acepta token en body o cookie."""
    _clear_auth_cookies(response)
    token = body.refresh_token if body else request.cookies.get("refresh_token")
    if not token:
        return {"message": "Sesión cerrada"}

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        await db.commit()
    return {"message": "Sesión cerrada"}


@router.get("/verify-email")
async def verify_email_endpoint(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verifica email tras el registro. Redirige al frontend."""
    user_id = verify_email_token(token)
    if not user_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?verified=false", status_code=302)

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user:
        user.is_verified = True
        await db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?verified=true", status_code=302)

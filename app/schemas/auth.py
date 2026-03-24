"""Schemas de autenticación según 02_AUTH.md."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request para POST /auth/register."""

    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    """Request para POST /auth/login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    """Usuario en respuestas de auth."""

    id: str
    email: str
    display_name: str
    has_team: bool = False
    team_id: str | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response de login y refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # segundos (15 min)
    user: UserOut


class RefreshRequest(BaseModel):
    """Request para POST /auth/refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request para POST /auth/logout."""

    refresh_token: str

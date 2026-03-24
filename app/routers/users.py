"""Router de usuarios: GET /users/me."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OAuthAccount, User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.user import UserMeOut

router = APIRouter()


@router.get("/me", response_model=UserMeOut)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserMeOut:
    """Requiere JWT válido. Retorna datos del usuario actual."""
    result = await db.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
    oauth_accounts = result.scalars().all()
    auth_methods = []
    if user.password_hash:
        auth_methods.append("password")
    if any(o.provider == "google" for o in oauth_accounts):
        auth_methods.append("google")

    return UserMeOut(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        has_team=False,
        team_id=None,
        auth_methods=auth_methods,
        created_at=user.created_at,
    )

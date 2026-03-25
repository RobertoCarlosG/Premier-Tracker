"""Router de usuarios: GET /users/me."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OAuthAccount, SavedTeam, User
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

    primary = await db.execute(
        select(SavedTeam).where(
            SavedTeam.user_id == user.id,
            SavedTeam.is_primary.is_(True),
        )
    )
    saved = primary.scalar_one_or_none()
    has_team = saved is not None
    team_id = str(saved.team_id) if saved else None

    return UserMeOut(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        has_team=has_team,
        team_id=team_id,
        auth_methods=auth_methods,
        created_at=user.created_at,
    )

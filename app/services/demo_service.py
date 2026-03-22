from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.demo_user_repository import DemoUserRepository
from app.db.models import DemoUser
from app.core.config import settings
import resend


class DemoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = DemoUserRepository(db)
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY
    
    async def request_demo_access(self, email: str) -> DemoUser:
        existing = await self.user_repo.get_by_email(email)
        
        if existing:
            if existing.is_verified:
                return existing
            user = existing
        else:
            user = await self.user_repo.create(email)
        
        if settings.RESEND_API_KEY and not existing:
            await self._send_verification_email(user)
        
        return user
    
    async def _send_verification_email(self, user: DemoUser) -> None:
        verification_url = f"{settings.FRONTEND_URL}/verify?token={user.verification_token}"
        
        try:
            resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": user.email,
                "subject": "Verify your Valorant Premier Dashboard access",
                "html": f"""
                <h1>Welcome to Valorant Premier Dashboard!</h1>
                <p>Click the link below to verify your email and get full demo access:</p>
                <a href="{verification_url}">Verify Email</a>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                """
            })
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    async def verify_email(self, token: str) -> Optional[DemoUser]:
        return await self.user_repo.verify_user(token)
    
    async def validate_access_token(self, token: str) -> Optional[DemoUser]:
        user = await self.user_repo.get_by_token(token)
        
        if user and user.is_verified:
            await self.user_repo.update_last_access(user)
            return user
        
        return None
    
    def is_demo_mode(self) -> bool:
        return settings.DEMO_MODE
    
    def apply_demo_limits(self, data: list, limit_type: str) -> tuple[list, bool]:
        if not self.is_demo_mode():
            return data, False
        
        limits = {
            "leaderboard": settings.DEMO_LEADERBOARD_LIMIT,
            "search": settings.DEMO_SEARCH_LIMIT,
            "match_history": settings.DEMO_MATCH_HISTORY_LIMIT
        }
        
        limit = limits.get(limit_type, 5)
        is_limited = len(data) > limit
        
        return data[:limit], is_limited

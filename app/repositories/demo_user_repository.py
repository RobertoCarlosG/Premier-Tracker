from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import DemoUser
from app.core.security import create_access_token
import secrets


class DemoUserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_email(self, email: str) -> Optional[DemoUser]:
        stmt = select(DemoUser).where(DemoUser.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_token(self, token: str) -> Optional[DemoUser]:
        stmt = select(DemoUser).where(DemoUser.access_token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create(self, email: str) -> DemoUser:
        verification_token = secrets.token_urlsafe(32)
        
        user = DemoUser(
            email=email,
            verification_token=verification_token,
            is_verified=False
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def verify_user(self, verification_token: str) -> Optional[DemoUser]:
        stmt = select(DemoUser).where(DemoUser.verification_token == verification_token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user and not user.is_verified:
            user.is_verified = True
            user.verified_at = datetime.utcnow()
            
            access_token = create_access_token(data={"sub": user.email})
            user.access_token = access_token
            
            await self.db.commit()
            await self.db.refresh(user)
            return user
        
        return None
    
    async def update_last_access(self, user: DemoUser) -> None:
        user.last_access = datetime.utcnow()
        await self.db.commit()

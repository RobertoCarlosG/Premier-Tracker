from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import CacheEntry
import json


class CacheRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get(self, cache_key: str) -> Optional[dict]:
        stmt = select(CacheEntry).where(
            and_(
                CacheEntry.cache_key == cache_key,
                CacheEntry.expires_at > datetime.utcnow()
            )
        )
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if entry:
            entry.hit_count += 1
            await self.db.commit()
            return entry.data
        
        return None
    
    async def set(
        self, 
        cache_key: str, 
        data: dict, 
        cache_type: str, 
        ttl_seconds: int
    ) -> None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.data = data
            existing.expires_at = expires_at
            existing.hit_count = 0
        else:
            entry = CacheEntry(
                cache_key=cache_key,
                cache_type=cache_type,
                data=data,
                expires_at=expires_at
            )
            self.db.add(entry)
        
        await self.db.commit()
    
    async def delete(self, cache_key: str) -> None:
        stmt = select(CacheEntry).where(CacheEntry.cache_key == cache_key)
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if entry:
            await self.db.delete(entry)
            await self.db.commit()
    
    async def clear_expired(self) -> int:
        stmt = select(CacheEntry).where(CacheEntry.expires_at <= datetime.utcnow())
        result = await self.db.execute(stmt)
        expired = result.scalars().all()
        
        count = len(expired)
        for entry in expired:
            await self.db.delete(entry)
        
        await self.db.commit()
        return count

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.valorant_api import ValorantAPIClient
from app.repositories.cache_repository import CacheRepository
from app.core.config import settings
import hashlib


class CacheService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache_repo = CacheRepository(db)
        self.api_client = ValorantAPIClient()
    
    def _generate_cache_key(self, prefix: str, *args) -> str:
        key_parts = [prefix] + [str(arg) for arg in args]
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def get_or_fetch_leaderboard(
        self,
        region: str,
        conference: Optional[str] = None,
        division: Optional[str] = None,
    ) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("leaderboard", region, conference or "", division or "")
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.get_leaderboard(region, conference, division)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="leaderboard",
            ttl_seconds=settings.CACHE_TTL_LEADERBOARD
        )
        
        return data
    
    async def get_or_fetch_team(
        self,
        team_name: Optional[str] = None,
        team_tag: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if team_id:
            cache_key = self._generate_cache_key("team_id", team_id)
            cached = await self.cache_repo.get(cache_key)
            if cached:
                return cached
            
            data = await self.api_client.get_team_by_id(team_id)
        else:
            cache_key = self._generate_cache_key("team_name", team_name, team_tag)
            cached = await self.cache_repo.get(cache_key)
            if cached:
                return cached
            
            data = await self.api_client.get_team_by_name(team_name, team_tag)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="team",
            ttl_seconds=settings.CACHE_TTL_TEAM
        )
        
        return data
    
    async def get_or_fetch_team_history(
        self,
        team_name: Optional[str] = None,
        team_tag: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if team_id:
            cache_key = self._generate_cache_key("team_history_id", team_id)
            cached = await self.cache_repo.get(cache_key)
            if cached:
                return cached
            
            data = await self.api_client.get_team_history_by_id(team_id)
        else:
            cache_key = self._generate_cache_key("team_history_name", team_name, team_tag)
            cached = await self.cache_repo.get(cache_key)
            if cached:
                return cached
            
            data = await self.api_client.get_team_history_by_name(team_name, team_tag)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="team_history",
            ttl_seconds=settings.CACHE_TTL_MATCH
        )
        
        return data
    
    async def get_or_fetch_player(self, name: str, tag: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("player", name, tag)
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.get_account_by_name(name, tag)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="player",
            ttl_seconds=settings.CACHE_TTL_PLAYER
        )
        
        return data
    
    async def get_or_fetch_mmr(self, region: str, name: str, tag: str) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("mmr", region, name, tag)
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.get_mmr(region, name, tag)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="mmr",
            ttl_seconds=settings.CACHE_TTL_MMR
        )
        
        return data
    
    async def get_or_fetch_mmr_history(self, region: str, name: str, tag: str) -> Dict[str, Any]:
        """Historial MMR (Henrik v1 mmr-history); cache separado del snapshot v2."""
        cache_key = self._generate_cache_key("mmr_history", region, name, tag)
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.get_mmr_history(region, name, tag)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="mmr_history",
            ttl_seconds=settings.CACHE_TTL_MMR,
        )
        
        return data
    
    async def get_or_fetch_match_history(
        self,
        region: str,
        name: str,
        tag: str,
        mode: Optional[str] = None,
        size: int = 20,
    ) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("match_history", region, name, tag, mode or "", size)
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.get_match_history(region, name, tag, mode, size)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="match_history",
            ttl_seconds=settings.CACHE_TTL_MATCH
        )
        
        return data
    
    async def search_teams(
        self,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        division: Optional[str] = None,
        conference: Optional[str] = None
    ) -> Dict[str, Any]:
        cache_key = self._generate_cache_key("search", name or "", tag or "", division or "", conference or "")
        
        cached = await self.cache_repo.get(cache_key)
        if cached:
            return cached
        
        data = await self.api_client.search_teams(name, tag, division, conference)
        
        await self.cache_repo.set(
            cache_key=cache_key,
            data=data,
            cache_type="search",
            ttl_seconds=settings.CACHE_TTL_TEAM
        )
        
        return data

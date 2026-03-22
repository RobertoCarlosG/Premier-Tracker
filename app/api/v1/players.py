from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.session import get_db
from app.services.cache_service import CacheService
from app.services.demo_service import DemoService
from app.api.v1.premier import get_verified_user

router = APIRouter()


@router.get("/account/{name}/{tag}")
async def get_player_account(
    name: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    data = await cache_service.get_or_fetch_player(name, tag)
    return data


@router.get("/mmr/{affinity}/{name}/{tag}")
async def get_player_mmr(
    affinity: str,
    name: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    data = await cache_service.get_or_fetch_mmr(affinity, name, tag)
    return data


@router.get("/matches/{affinity}/{name}/{tag}")
async def get_player_matches(
    affinity: str,
    name: str,
    tag: str,
    mode: Optional[str] = None,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    demo_service = DemoService(db)
    
    data = await cache_service.get_or_fetch_match_history(affinity, name, tag, mode, size)
    
    matches = data.get("data", [])
    limited_matches, is_limited = demo_service.apply_demo_limits(matches, "match_history")
    
    return {
        "data": limited_matches,
        "total": len(matches),
        "is_demo_limited": is_limited
    }


@router.get("/match/{match_id}")
async def get_match_details(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    data = await cache_service.api_client.get_match_details(match_id)
    return data

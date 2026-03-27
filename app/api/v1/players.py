import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, Optional
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


@router.get("/mmr/{region}/{name}/{tag}")
async def get_player_mmr(
    region: str,
    name: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user),
):
    """
    Proxy v2 MMR + v1 mmr-history. El frontend espera `data.mmr_history` para la gráfica;
    Henrik lo devuelve en `GET /valorant/v1/mmr-history/{region}/{name}/{tag}`.
    """
    cache_service = CacheService(db)
    data: Dict[str, Any] = await cache_service.get_or_fetch_mmr(region, name, tag)
    history_list: list = []
    try:
        hist = await cache_service.get_or_fetch_mmr_history(region, name, tag)
        raw = hist.get("data") if isinstance(hist, dict) else None
        if isinstance(raw, list):
            history_list = raw
    except Exception:
        pass
    inner = data.get("data") if isinstance(data, dict) else None
    if isinstance(inner, dict):
        inner["mmr_history"] = history_list
    return data


@router.get("/matches/{region}/{name}/{tag}")
async def get_player_matches(
    region: str,
    name: str,
    tag: str,
    mode: Optional[str] = None,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user),
):
    cache_service = CacheService(db)
    demo_service = DemoService(db)
    
    data = await cache_service.get_or_fetch_match_history(region, name, tag, mode, size)
    
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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.session import get_db
from app.services.cache_service import CacheService
from app.services.demo_service import DemoService
from app.api.v1.premier import get_verified_user
from app.schemas.schemas import TeamInfo, TeamMember, TeamHistoryResponse, MatchHistoryEntry

router = APIRouter()


@router.get("/name/{team_name}/{team_tag}")
async def get_team_by_name(
    team_name: str,
    team_tag: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    data = await cache_service.get_or_fetch_team(team_name=team_name, team_tag=team_tag)
    return data


@router.get("/id/{team_id}")
async def get_team_by_id(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    data = await cache_service.get_or_fetch_team(team_id=team_id)
    return data


@router.get("/name/{team_name}/{team_tag}/history")
async def get_team_history_by_name(
    team_name: str,
    team_tag: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    demo_service = DemoService(db)
    
    data = await cache_service.get_or_fetch_team_history(team_name=team_name, team_tag=team_tag)
    
    matches = data.get("data", [])
    limited_matches, is_limited = demo_service.apply_demo_limits(matches, "match_history")
    
    return {
        "data": limited_matches,
        "total": len(matches),
        "is_demo_limited": is_limited
    }


@router.get("/id/{team_id}/history")
async def get_team_history_by_id(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    cache_service = CacheService(db)
    demo_service = DemoService(db)
    
    data = await cache_service.get_or_fetch_team_history(team_id=team_id)
    
    matches = data.get("data", [])
    limited_matches, is_limited = demo_service.apply_demo_limits(matches, "match_history")
    
    return {
        "data": limited_matches,
        "total": len(matches),
        "is_demo_limited": is_limited
    }

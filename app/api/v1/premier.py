import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.session import get_db
from app.services.cache_service import CacheService
from app.services.demo_service import DemoService
from app.schemas.schemas import LeaderboardResponse, LeaderboardEntry

router = APIRouter()


def _henrik_display_str(value: object) -> str:
    """Henrik a veces envía division como entero (p. ej. 22); el modelo espera string."""
    if value is None:
        return ""
    return str(value)


async def get_verified_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    demo_service = DemoService(db)
    
    if not demo_service.is_demo_mode():
        return None
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Demo mode: authentication required")
    
    token = authorization.replace("Bearer ", "")
    user = await demo_service.validate_access_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


@router.get("/conferences")
async def get_conferences(db: AsyncSession = Depends(get_db)):
    cache_service = CacheService(db)
    data = await cache_service.api_client.get_conferences()
    return data


@router.get("/seasons/{region}")
async def get_seasons(region: str, db: AsyncSession = Depends(get_db)):
    """Proxy a Henrik `GET /valorant/v1/premier/seasons/{region}`. `region` = eu | na | latam | …"""
    cache_service = CacheService(db)
    data = await cache_service.api_client.get_seasons(region)
    return data


@router.get("/leaderboard/{region}", response_model=LeaderboardResponse)
async def get_leaderboard(
    region: str,
    conference: Optional[str] = None,
    division: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user),
):
    """
    Proxy a Henrik Premier leaderboard: `.../premier/leaderboard/{region}` o con conference/division.
    El segmento es la **región** del OpenAPI de Henrik (no un nombre distinto de “affinity”).
    """
    cache_service = CacheService(db)
    demo_service = DemoService(db)
    
    data = await cache_service.get_or_fetch_leaderboard(region, conference, division)
    
    entries = []
    for item in data.get("data", []):
        entry = LeaderboardEntry(
            rank=item.get("placement", 0),
            team_name=item.get("name", ""),
            team_tag=item.get("tag", ""),
            team_id=_henrik_display_str(item.get("id", "")),
            division=_henrik_display_str(item.get("division", "")) or None,
            conference=_henrik_display_str(item.get("conference", "")) or None,
            wins=item.get("wins", 0),
            losses=item.get("losses", 0),
            points=item.get("score", 0),
            logo_url=item.get("customization", {}).get("icon", None)
        )
        entries.append(entry)
    
    limited_entries, is_limited = demo_service.apply_demo_limits(entries, "leaderboard")
    
    return LeaderboardResponse(
        data=limited_entries,
        total=len(entries),
        is_demo_limited=is_limited
    )


@router.get("/search")
async def search_teams(
    name: Optional[str] = None,
    tag: Optional[str] = None,
    division: Optional[str] = None,
    conference: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_verified_user)
):
    if not any([name, tag, division, conference]):
        raise HTTPException(status_code=400, detail="At least one search parameter required")
    
    cache_service = CacheService(db)
    demo_service = DemoService(db)

    try:
        data = await cache_service.search_teams(name, tag, division, conference)
    except httpx.HTTPStatusError as e:
        # Errores de Henrik (400/429/5xx): respuesta JSON con CORS en lugar de 500 sin cuerpo.
        raise HTTPException(
            status_code=502,
            detail="La API de datos de Valorant rechazó la búsqueda. Revisa nombre/tag o inténtalo más tarde.",
        ) from e

    teams = data.get("data", [])
    limited_teams, is_limited = demo_service.apply_demo_limits(teams, "search")
    
    return {
        "data": limited_teams,
        "total": len(teams),
        "is_demo_limited": is_limited
    }

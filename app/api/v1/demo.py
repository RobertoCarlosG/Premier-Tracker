from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.demo_service import DemoService
from app.schemas.schemas import DemoUserCreate, DemoUserResponse, TokenResponse

router = APIRouter()


@router.post("/request-access", response_model=DemoUserResponse)
async def request_demo_access(
    user_data: DemoUserCreate,
    db: AsyncSession = Depends(get_db)
):
    demo_service = DemoService(db)
    
    if not demo_service.is_demo_mode():
        raise HTTPException(
            status_code=400,
            detail="Demo mode is not enabled. Full access is available."
        )
    
    user = await demo_service.request_demo_access(user_data.email)
    
    return DemoUserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        created_at=user.created_at
    )


@router.get("/verify", response_model=TokenResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    demo_service = DemoService(db)
    
    user = await demo_service.verify_email(token)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    return TokenResponse(
        access_token=user.access_token,
        token_type="bearer"
    )


@router.get("/status")
async def get_demo_status(db: AsyncSession = Depends(get_db)):
    demo_service = DemoService(db)
    
    return {
        "demo_mode": demo_service.is_demo_mode(),
        "limits": {
            "leaderboard": demo_service.user_repo.db.bind.url.database if demo_service.is_demo_mode() else None,
            "search": None,
            "match_history": None
        } if demo_service.is_demo_mode() else None
    }

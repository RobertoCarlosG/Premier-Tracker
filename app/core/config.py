from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        # Render/UI often use different casing; FRONTEND_URL must still load for CORS.
        case_sensitive=False,
    )
    # API Configuration
    VALORANT_API_KEY: str
    VALORANT_API_BASE_URL: str = "https://api.henrikdev.xyz/valorant/v1"
    
    # Demo Mode
    DEMO_MODE: bool = False
    DEMO_LEADERBOARD_LIMIT: int = 5
    DEMO_SEARCH_LIMIT: int = 3
    DEMO_MATCH_HISTORY_LIMIT: int = 5
    
    # Database
    DATABASE_URL: str
    
    # Cache TTL (seconds)
    CACHE_TTL_LEADERBOARD: int = 900
    CACHE_TTL_TEAM: int = 300
    CACHE_TTL_PLAYER: int = 300
    CACHE_TTL_MATCH: int = 600
    CACHE_TTL_MMR: int = 300
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_SECRET: Optional[str] = None  # usa SECRET_KEY si None

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    
    # Email
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@example.com"
    
    # CORS (browser Origin has no trailing slash; strip so allow_origins matches)
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"

    @field_validator("FRONTEND_URL", mode="before")
    @classmethod
    def normalize_frontend_url(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().rstrip("/")
        return v
    
    # App
    APP_NAME: str = "Valorant Premier Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
settings = Settings()

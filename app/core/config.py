from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration
    VALORANT_API_KEY: str
    VALORANT_API_BASE_URL: str = "https://api.henrikdev.xyz/valorant/v3"
    
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    
    # Email
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@example.com"
    
    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    
    # App
    APP_NAME: str = "Valorant Premier Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

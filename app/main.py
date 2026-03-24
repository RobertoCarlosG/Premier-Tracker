from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
from app.core.config import settings
from app.api.v1 import premier, teams, players, demo
from app.routers import auth, users

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Modern dashboard for Valorant Premier teams and players",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Añade headers de seguridad a todas las respuestas."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(premier.router, prefix="/api/v1/premier", tags=["Premier"])
app.include_router(teams.router, prefix="/api/v1/teams", tags=["Teams"])
app.include_router(players.router, prefix="/api/v1/players", tags=["Players"])
app.include_router(demo.router, prefix="/api/v1/demo", tags=["Demo"])


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "online"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "demo_mode": settings.DEMO_MODE,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.on_event("startup")
async def startup_event():
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"📊 Demo Mode: {'Enabled' if settings.DEMO_MODE else 'Disabled'}")
    print(f"🌐 Frontend URL: {settings.FRONTEND_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    print("👋 Shutting down...")

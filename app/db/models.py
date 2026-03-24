from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from app.db.session import Base


class User(Base):
    """Usuario del sistema. Soporta email+password y/o Google OAuth."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=True)  # NULL si solo usa OAuth
    is_verified = Column(Boolean, default=False, nullable=False)
    role = Column(String(20), default="user", nullable=False)  # user | admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class OAuthAccount(Base):
    """Cuenta OAuth vinculada a un usuario (ej. Google)."""

    __tablename__ = "oauth_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # "google"
    provider_id = Column(String(255), nullable=False)  # Google sub
    provider_email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("provider", "provider_id"),)
    user = relationship("User", back_populates="oauth_accounts")


class RefreshToken(Base):
    """Refresh token para renovar sesión. Solo se guarda el hash."""

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(INET, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")


class OAuthState(Base):
    """Estado CSRF para flujo OAuth. TTL 5 min."""

    __tablename__ = "oauth_states"

    state = Column(String(255), primary_key=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


# --- Modelos existentes (demo, cache, logs) ---


class DemoUser(Base):
    __tablename__ = "demo_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_access = Column(DateTime(timezone=True), nullable=True)


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True, nullable=False)
    cache_type = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    hit_count = Column(Integer, default=0)


class APILog(Base):
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

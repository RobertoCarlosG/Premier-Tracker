from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.session import Base


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

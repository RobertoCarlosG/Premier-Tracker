#!/usr/bin/env python3
"""
Script de migración para tablas de autenticación (Fase 1).
Ejecutar: python scripts/migrate_auth.py
Requiere DATABASE_URL en el entorno.
"""
import asyncio
import os
import sys

# Añadir backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.db.session import engine


STATEMENTS = [
    'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
    """CREATE TABLE IF NOT EXISTS users (
        id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email         VARCHAR(255) NOT NULL UNIQUE,
        display_name  VARCHAR(100) NOT NULL,
        password_hash VARCHAR(255),
        is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
        role          VARCHAR(20)  NOT NULL DEFAULT 'user',
        created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        last_login_at TIMESTAMPTZ
    )""",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    """CREATE TABLE IF NOT EXISTS oauth_accounts (
        id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider       VARCHAR(50)  NOT NULL,
        provider_id    VARCHAR(255) NOT NULL,
        provider_email VARCHAR(255) NOT NULL,
        access_token   TEXT,
        created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
        UNIQUE (provider, provider_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_oauth_user_id ON oauth_accounts(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth_accounts(provider, provider_id)",
    """CREATE TABLE IF NOT EXISTS refresh_tokens (
        id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(64)  NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ  NOT NULL,
        revoked    BOOLEAN      NOT NULL DEFAULT FALSE,
        user_agent VARCHAR(500),
        ip_address INET,
        created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rt_user_id ON refresh_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_rt_token_hash ON refresh_tokens(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_rt_expires ON refresh_tokens(expires_at) WHERE revoked = FALSE",
    """CREATE TABLE IF NOT EXISTS oauth_states (
        state      VARCHAR(255) PRIMARY KEY,
        expires_at TIMESTAMPTZ  NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON oauth_states(expires_at)",
]


async def run_migration() -> None:
    """Ejecuta el SQL de migración."""
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))
    print("✅ Migración auth completada: users, oauth_accounts, refresh_tokens, oauth_states")


if __name__ == "__main__":
    asyncio.run(run_migration())

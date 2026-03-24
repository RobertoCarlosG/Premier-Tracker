"""
Migración Fase 2 — equipos vinculados + snapshots.

Uso:
    python scripts/migrate_phase2.py

Requiere DATABASE_URL en el entorno o en backend/.env
"""

import asyncio
import os
import sys
from pathlib import Path

# Permitir importar desde la raíz del backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SQL_FILE = Path(__file__).with_suffix(".sql")


async def run() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL no configurado.", file=sys.stderr)
        sys.exit(1)

    # asyncpg no acepta el prefijo 'postgresql+asyncpg://'
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    sql = SQL_FILE.read_text()
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(sql)
        print("Migración Fase 2 completada correctamente.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())

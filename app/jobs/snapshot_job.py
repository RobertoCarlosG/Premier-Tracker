"""
APScheduler jobs:
  - snapshot_daily : toma snapshots de todos los equipos vinculados (06:00 UTC)
  - cache_cleanup  : borra entradas de caché expiradas (cada 10 min)
  - token_cleanup  : borra refresh tokens expirados/revocados (diario)

Uso en main.py:
    from app.jobs.snapshot_job import start_scheduler, stop_scheduler
    app.add_event_handler("startup", start_scheduler)
    app.add_event_handler("shutdown", stop_scheduler)
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db.session import AsyncSessionLocal
from app.services import snapshot_service

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


# ─────────────────────────────────────────
# Jobs
# ─────────────────────────────────────────


async def _job_snapshot_daily() -> None:
    """Snapshot diario de todos los equipos vinculados."""
    logger.info("snapshot_daily: iniciando…")
    async with AsyncSessionLocal() as db:
        await snapshot_service.snapshot_all_teams(db)
    logger.info("snapshot_daily: completado.")


async def _job_cache_cleanup() -> None:
    """Borra entradas de caché expiradas."""
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM cache_entries WHERE expires_at < NOW()"))
        await db.commit()


async def _job_token_cleanup() -> None:
    """Borra refresh tokens expirados o revocados."""
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("DELETE FROM refresh_tokens WHERE expires_at < NOW() OR revoked = TRUE")
        )
        await db.commit()


# ─────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────


async def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")

    _scheduler.add_job(
        _job_snapshot_daily,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="snapshot_daily",
        replace_existing=True,
        name="Snapshot diario de equipos",
    )
    _scheduler.add_job(
        _job_cache_cleanup,
        trigger=IntervalTrigger(minutes=10),
        id="cache_cleanup",
        replace_existing=True,
        name="Limpieza de caché",
    )
    _scheduler.add_job(
        _job_token_cleanup,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="token_cleanup",
        replace_existing=True,
        name="Limpieza de tokens expirados",
    )

    _scheduler.start()
    logger.info("APScheduler iniciado con %d jobs.", len(_scheduler.get_jobs()))


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler detenido.")

"""Collector Lambda için kısa ömürlü async DB session yardımcıları."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.collectors.config import get_collector_settings


@asynccontextmanager
async def collector_db_session() -> AsyncIterator[AsyncSession]:
    """Tek işlem için session açar; başarıda commit, hatada rollback."""
    settings = get_collector_settings()
    if not settings.DATABASE_URL:
        msg = "DATABASE_URL tanımlı değil — collector DB erişimi yapılamaz"
        raise RuntimeError(msg)

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()

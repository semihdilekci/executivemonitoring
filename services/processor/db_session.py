"""Processor Lambda için async DB session yardımcıları."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.processor.config import get_processor_settings


@asynccontextmanager
async def processor_db_session() -> AsyncIterator[AsyncSession]:
    """Tek işlem için session açar; başarıda commit, hatada rollback."""
    settings = get_processor_settings()
    if not settings.DATABASE_URL:
        msg = "DATABASE_URL tanımlı değil — processor DB erişimi yapılamaz"
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


async def create_processor_redis() -> Redis:
    """Processor dedup için Redis bağlantısı."""
    settings = get_processor_settings()
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)

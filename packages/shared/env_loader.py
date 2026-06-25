"""Ortam değişkeni yükleme — `.env` birincil kaynak (`DATABASE_URL`)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
_CI_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/ygip_test"


def repo_root() -> Path:
    """Monorepo kök dizini."""
    return _REPO_ROOT


def load_dotenv_file(*, override: bool = False) -> bool:
    """
    Proje kökündeki `.env` dosyasını process ortamına yükler.

    `override=False` — shell'de export edilmiş değerler korunur.
    """
    if not _ENV_FILE.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    load_dotenv(_ENV_FILE, override=override)
    return True


def get_database_url(*, required: bool = True) -> str | None:
    """
    `DATABASE_URL` çözümlemesi:

    1. Process ortamı (`export DATABASE_URL=...`)
    2. `.env` dosyası (yüklü değilse otomatik yüklenir)
    3. GitHub Actions CI yedek URL
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    load_dotenv_file(override=False)
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    if os.environ.get("GITHUB_ACTIONS") == "true":
        return _CI_DATABASE_URL

    if not required:
        return None
    msg = (
        "DATABASE_URL bulunamadı. `.env` dosyasında tanımlayın "
        f"veya `export DATABASE_URL=...` kullanın (beklenen: {_ENV_FILE})"
    )
    raise RuntimeError(msg)


def safe_database_target(url: str) -> str:
    """Log/skip mesajları için host:port/db (kimlik bilgisi yok)."""
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    db = (parsed.path or "").lstrip("/") or "?"
    return f"{host}{port}/{db}"


def async_to_sync_database_url(url: str) -> str:
    """Alembic / psycopg2 için asyncpg URL'ini sync'e çevirir."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def can_connect_sync(sync_url: str) -> bool:
    """Sync SQLAlchemy engine ile bağlantı testi."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    engine = create_engine(sync_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    finally:
        engine.dispose()


async def can_connect_async(url: str) -> bool:
    """Async SQLAlchemy engine ile bağlantı testi."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def try_resolve_sync_database_url() -> str | None:
    """`.env`/ortam `DATABASE_URL` ile sync bağlantı; başarısızsa None."""
    try:
        url = get_database_url(required=True)
    except RuntimeError:
        return None
    if url is None:
        return None
    sync_url = async_to_sync_database_url(url)
    if can_connect_sync(sync_url):
        return sync_url
    return None

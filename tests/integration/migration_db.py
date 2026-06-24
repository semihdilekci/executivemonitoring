"""Migration integration testleri için güvenli test-DB çözümleme + guard.

Yıkıcı `DROP SCHEMA ... CASCADE` testleri ASLA geliştirme veritabanında
(ör. `ygip_dev`) çalışmamalı. Bu modül iki katman sağlar:

1. **Yönlendirme** — testler `DATABASE_URL`'den türetilen ayrı bir `ygip_test`
   veritabanına (veya `TEST_DATABASE_URL` override'ına) gider.
2. **Guard** — hedef DB adında `test` geçmiyorsa yıkıcı reset reddedilir; bu
   sayede yanlış konfigürasyon dev DB'sini silemez.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

import pytest
from alembic.config import Config
from packages.shared.env_loader import (
    async_to_sync_database_url,
    can_connect_sync,
    get_database_url,
    load_dotenv_file,
)
from sqlalchemy.engine import Engine

TEST_DB_NAME = "ygip_test"


def _swap_db_name(url: str, db_name: str) -> str:
    """URL'deki veritabanı adını değiştirir (ör. ygip_dev -> ygip_test)."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{db_name}"))


def guard_destructive(target: str | Engine) -> None:
    """Hedef DB adında 'test' yoksa yıkıcı işlemi `skip` ile reddeder.

    Geliştirme DB'sinin (ör. ygip_dev) yanlışlıkla `DROP SCHEMA` ile
    boşaltılmasını kesin olarak engeller.
    """
    if isinstance(target, Engine):
        db_name = target.url.database or ""
    else:
        db_name = urlparse(target).path.lstrip("/")
    if "test" not in db_name.lower():
        pytest.skip(
            f"GÜVENLİK: Yıkıcı migration testi yalnızca adında 'test' geçen "
            f"veritabanında çalışır (hedef: {db_name!r}). Dev DB korunuyor."
        )


def resolve_sync_test_database_url() -> str:
    """ygip_test sync URL'i — `TEST_DATABASE_URL` > `DATABASE_URL`'den türetme.

    Bağlanılamazsa testi skip eder; dev DB'sine ASLA düşmez (guard + türetme).
    """
    load_dotenv_file(override=False)
    override = os.environ.get("TEST_DATABASE_URL", "").strip()
    if override:
        sync_url = async_to_sync_database_url(override)
    else:
        try:
            base = get_database_url(required=True)
        except RuntimeError as exc:
            pytest.skip(str(exc))
        sync_url = async_to_sync_database_url(_swap_db_name(base, TEST_DB_NAME))

    guard_destructive(sync_url)

    if not can_connect_sync(sync_url):
        pytest.skip(
            f"Test veritabanına bağlanılamadı ({TEST_DB_NAME}). Bir kez oluşturun:\n"
            f"  createdb -h localhost -p 5433 -U ygip {TEST_DB_NAME}\n"
            f"  DATABASE_URL=...{TEST_DB_NAME} alembic upgrade head\n"
            "veya TEST_DATABASE_URL ortam değişkenini ayarlayın."
        )
    return sync_url


def make_alembic_config() -> Config:
    """Alembic Config — `command.upgrade/downgrade` ygip_test'i hedefler.

    `_sync_database_url` (alembic/env.py) `test_database_url` main-option'ını
    önceler; böylece migration komutları DEV DB'sine (DATABASE_URL) DOKUNMAZ.
    """
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("test_database_url", resolve_sync_test_database_url())
    return cfg

"""Core tablo migration integration testleri."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

# Local docker-compose (Docs/09 §1.3) önce; CI service container yedek
_LOCAL_DEV_URL = "postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev"
_CI_TEST_URL = "postgresql+asyncpg://test:test@localhost:5432/ygip_test"

CORE_TABLES = {
    "users",
    "audit_logs",
    "password_reset_tokens",
    "system_settings",
}

CORE_REVISION = "001_core_tables"


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def _candidate_database_urls() -> list[str]:
    if env_url := os.environ.get("DATABASE_URL"):
        return [_to_sync_url(env_url)]
    return [_to_sync_url(_LOCAL_DEV_URL), _to_sync_url(_CI_TEST_URL)]


def _can_connect(sync_url: str) -> bool:
    engine = create_engine(sync_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    finally:
        engine.dispose()


def _resolve_sync_database_url() -> str | None:
    for url in _candidate_database_urls():
        if _can_connect(url):
            return url
    return None


@pytest.fixture(scope="session")
def sync_database_url() -> str:
    url = _resolve_sync_database_url()
    if url is None:
        pytest.skip("PostgreSQL not available or credentials invalid for integration tests")
    return url


@pytest.fixture
def db_engine(sync_database_url: str) -> Iterator[Engine]:
    engine = create_engine(sync_database_url)
    yield engine
    engine.dispose()


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg


def _reset_public_schema(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()


@pytest.fixture
def migrated_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde core migration uygular, test sonrası geri alır."""
    _reset_public_schema(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CORE_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def test_core_migration_creates_tables(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    tables = set(inspector.get_table_names())
    assert CORE_TABLES | {"alembic_version"} == tables


def test_core_migration_creates_user_role_enum(migrated_db: Engine) -> None:
    with migrated_db.connect() as connection:
        result = connection.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                "WHERE pg_type.typname = 'user_role_enum' "
                "ORDER BY enumsortorder"
            )
        )
        labels = [row[0] for row in result]
    assert labels == ["admin", "viewer"]


def test_core_migration_users_indexes(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("users")}
    assert {"idx_users_email", "idx_users_role"}.issubset(index_names)


def test_core_migration_audit_logs_indexes(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("audit_logs")}
    assert {
        "idx_audit_logs_event_type",
        "idx_audit_logs_actor_user_id",
        "idx_audit_logs_created_at",
        "idx_audit_logs_target",
    }.issubset(index_names)


def test_core_migration_password_reset_indexes(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("password_reset_tokens")}
    assert {
        "idx_password_reset_tokens_user_id",
        "idx_password_reset_tokens_expires_at",
    }.issubset(index_names)


def test_core_migration_unique_constraints(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    users_uq = {uc["name"] for uc in inspector.get_unique_constraints("users")}
    tokens_uq = {uc["name"] for uc in inspector.get_unique_constraints("password_reset_tokens")}
    assert "uq_users_email" in users_uq
    assert "uq_password_reset_tokens_token_hash" in tokens_uq


def test_core_migration_downgrade_removes_tables(db_engine: Engine) -> None:
    _reset_public_schema(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CORE_REVISION)
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(db_engine)
    assert inspector.get_table_names() == ["alembic_version"]


def test_core_migration_downgrade_up_roundtrip(db_engine: Engine) -> None:
    """Kalite kapısı: downgrade -1 ardından upgrade head."""
    _reset_public_schema(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CORE_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, CORE_REVISION)

    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert CORE_TABLES | {"alembic_version"} == tables

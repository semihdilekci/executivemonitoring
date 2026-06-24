"""Core tablo migration integration testleri."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from tests.integration.migration_db import (
    make_alembic_config,
    resolve_sync_test_database_url,
)

CORE_TABLES = {
    "users",
    "audit_logs",
    "password_reset_tokens",
    "system_settings",
}

CORE_REVISION = "001_core_tables"


@pytest.fixture(scope="session")
def sync_database_url() -> str:
    return resolve_sync_test_database_url()


@pytest.fixture
def db_engine(sync_database_url: str) -> Iterator[Engine]:
    engine = create_engine(sync_database_url)
    yield engine
    engine.dispose()


def _alembic_config() -> Config:
    return make_alembic_config()


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

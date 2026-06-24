"""Pipeline tablo migration integration testleri (005_pipeline_tables)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from tests.integration.migration_db import (
    guard_destructive,
    make_alembic_config,
    resolve_sync_test_database_url,
)

PIPELINE_TABLES = {"pipeline_runs", "pipeline_run_steps"}

NOTIFICATION_REVISION = "004_notification_logs"
PIPELINE_REVISION = "005_pipeline_tables"


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


def _reset_database(engine: Engine) -> None:
    guard_destructive(engine)
    with engine.connect() as connection:
        for schema in PROCESSED_ITEM_SCHEMAS:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()


@pytest.fixture
def migrated_pipeline_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde 001→005 migration uygular."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, PIPELINE_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def _enum_labels(connection, enum_name: str) -> list[str]:
    result = connection.execute(
        text(
            "SELECT enumlabel FROM pg_enum "
            "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = :enum_name "
            "ORDER BY enumsortorder"
        ),
        {"enum_name": enum_name},
    )
    return [row[0] for row in result]


def test_pipeline_migration_creates_tables(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    tables = set(inspector.get_table_names())
    assert PIPELINE_TABLES.issubset(tables)


def test_pipeline_migration_enums(migrated_pipeline_db: Engine) -> None:
    expected_enums = {
        "pipeline_run_type_enum": ["collect_pipeline", "digest_update"],
        "pipeline_run_status_enum": [
            "pending",
            "running",
            "completed",
            "partial",
            "failed",
            "cancelled",
        ],
        "pipeline_stage_enum": ["collect", "ingest", "process", "digest"],
        "pipeline_step_status_enum": [
            "pending",
            "running",
            "completed",
            "failed",
            "skipped",
        ],
    }
    with migrated_pipeline_db.connect() as connection:
        for enum_name, expected_labels in expected_enums.items():
            assert _enum_labels(connection, enum_name) == expected_labels


def test_pipeline_runs_indexes(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("pipeline_runs")}
    assert {
        "idx_pipeline_runs_status",
        "idx_pipeline_runs_run_type",
        "idx_pipeline_runs_created_at",
        "idx_pipeline_runs_triggered_by",
    }.issubset(index_names)


def test_pipeline_runs_triggered_by_set_null(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    fks = inspector.get_foreign_keys("pipeline_runs")
    user_fk = next(fk for fk in fks if fk["referred_table"] == "users")
    assert user_fk["options"].get("ondelete") == "SET NULL"


def test_pipeline_run_steps_indexes(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("pipeline_run_steps")}
    assert {
        "idx_pipeline_run_steps_run_id",
        "idx_pipeline_run_steps_status",
    }.issubset(index_names)


def test_pipeline_run_steps_unique_constraint(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("pipeline_run_steps")}
    assert "uq_pipeline_run_steps_run_id_stage" in unique_names


def test_pipeline_run_steps_cascade(migrated_pipeline_db: Engine) -> None:
    inspector = inspect(migrated_pipeline_db)
    fks = inspector.get_foreign_keys("pipeline_run_steps")
    run_fk = next(fk for fk in fks if fk["referred_table"] == "pipeline_runs")
    assert run_fk["options"].get("ondelete") == "CASCADE"


def test_pipeline_migration_full_chain_revision(migrated_pipeline_db: Engine) -> None:
    with migrated_pipeline_db.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        assert result.scalar() == PIPELINE_REVISION


def test_pipeline_migration_downgrade_removes_tables(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, PIPELINE_REVISION)
    command.downgrade(alembic_cfg, NOTIFICATION_REVISION)

    inspector = inspect(db_engine)
    public_tables = set(inspector.get_table_names())
    assert PIPELINE_TABLES.isdisjoint(public_tables)

    with db_engine.connect() as connection:
        assert _enum_labels(connection, "pipeline_run_type_enum") == []
        assert _enum_labels(connection, "pipeline_step_status_enum") == []


def test_pipeline_migration_downgrade_up_roundtrip(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, PIPELINE_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, PIPELINE_REVISION)

    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert PIPELINE_TABLES.issubset(tables)

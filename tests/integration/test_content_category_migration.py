"""content_category kolonu migration integration testleri (006_content_category)."""

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

PIPELINE_REVISION = "005_pipeline_tables"
CONTENT_CATEGORY_REVISION = "006_content_category"


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


def _column_names(engine: Engine, schema: str) -> set[str]:
    inspector = inspect(engine)
    return {col["name"] for col in inspector.get_columns("processed_items", schema=schema)}


def _index_names(engine: Engine, schema: str) -> set[str]:
    inspector = inspect(engine)
    return {idx["name"] for idx in inspector.get_indexes("processed_items", schema=schema)}


@pytest.fixture
def migrated_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde 001→006 migration uygular."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_CATEGORY_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def test_content_category_column_added_all_schemas(migrated_db: Engine) -> None:
    for schema in PROCESSED_ITEM_SCHEMAS:
        assert "content_category" in _column_names(migrated_db, schema)


def test_content_category_index_added_all_schemas(migrated_db: Engine) -> None:
    for schema in PROCESSED_ITEM_SCHEMAS:
        assert (
            f"idx_{schema}_processed_items_content_category"
            in _index_names(migrated_db, schema)
        )


def test_content_category_column_nullable(migrated_db: Engine) -> None:
    inspector = inspect(migrated_db)
    for schema in PROCESSED_ITEM_SCHEMAS:
        column = next(
            col
            for col in inspector.get_columns("processed_items", schema=schema)
            if col["name"] == "content_category"
        )
        assert column["nullable"] is True


def test_content_category_migration_revision(migrated_db: Engine) -> None:
    with migrated_db.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        assert result.scalar() == CONTENT_CATEGORY_REVISION


def test_content_category_downgrade_removes_column(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_CATEGORY_REVISION)
    command.downgrade(alembic_cfg, PIPELINE_REVISION)

    for schema in PROCESSED_ITEM_SCHEMAS:
        assert "content_category" not in _column_names(db_engine, schema)
        assert (
            f"idx_{schema}_processed_items_content_category"
            not in _index_names(db_engine, schema)
        )


def test_content_category_downgrade_up_roundtrip(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_CATEGORY_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, CONTENT_CATEGORY_REVISION)

    for schema in PROCESSED_ITEM_SCHEMAS:
        assert "content_category" in _column_names(db_engine, schema)

"""Veri tablo migration integration testleri (002_data_tables)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from packages.shared.env_loader import (
    get_database_url,
    load_dotenv_file,
    safe_database_target,
    try_resolve_sync_database_url,
)
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

DATA_TABLES = {
    "sources",
    "raw_items",
    "content_chunks",
    "api_keys",
    "api_usage_logs",
}

CORE_REVISION = "001_core_tables"
DATA_REVISION = "002_data_tables"


@pytest.fixture(scope="session")
def sync_database_url() -> str:
    load_dotenv_file(override=False)
    url = try_resolve_sync_database_url()
    if url is None:
        try:
            raw = get_database_url(required=True)
            target = safe_database_target(raw)
        except RuntimeError as exc:
            pytest.skip(str(exc))
        pytest.skip(
            f"DATABASE_URL ile PostgreSQL'e bağlanılamadı ({target}). "
            "`.env` kimlik bilgilerini kontrol edin."
        )
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


def _reset_database(engine: Engine) -> None:
    with engine.connect() as connection:
        for schema in PROCESSED_ITEM_SCHEMAS:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()


@pytest.fixture
def migrated_data_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde core + veri migration uygular."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, DATA_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def test_data_migration_creates_public_tables(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    tables = set(inspector.get_table_names())
    assert DATA_TABLES.issubset(tables)


def test_data_migration_creates_domain_schemas(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    for schema in PROCESSED_ITEM_SCHEMAS:
        assert schema in inspector.get_schema_names()
        assert "processed_items" in inspector.get_table_names(schema=schema)


def test_data_migration_vector_extension(migrated_data_db: Engine) -> None:
    with migrated_data_db.connect() as connection:
        result = connection.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        assert result.scalar() is True


def test_data_migration_enum_types(migrated_data_db: Engine) -> None:
    expected_enums = {
        "source_type_enum": ["rss", "email", "rest_api", "websocket", "gov"],
        "source_status_enum": ["active", "inactive", "error"],
        "source_category_enum": [
            "turkish_media",
            "fmcg",
            "strategy",
            "official",
            "market",
            "geo",
            "transport",
        ],
        "raw_item_status_enum": ["pending", "processing", "processed", "failed"],
        "api_provider_enum": ["groq", "gemini"],
    }
    with migrated_data_db.connect() as connection:
        for enum_name, expected_labels in expected_enums.items():
            result = connection.execute(
                text(
                    "SELECT enumlabel FROM pg_enum "
                    "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                    "WHERE pg_type.typname = :enum_name "
                    "ORDER BY enumsortorder"
                ),
                {"enum_name": enum_name},
            )
            labels = [row[0] for row in result]
            assert labels == expected_labels


def test_data_migration_sources_indexes(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("sources")}
    assert {
        "idx_sources_status",
        "idx_sources_source_type",
        "idx_sources_category",
    }.issubset(index_names)


def test_data_migration_raw_items_unique_constraint(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("raw_items")}
    assert "uq_raw_items_source_id_content_hash" in unique_names


def test_data_migration_processed_items_indexes(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    for schema in PROCESSED_ITEM_SCHEMAS:
        indexes = inspector.get_indexes("processed_items", schema=schema)
        index_names = {idx["name"] for idx in indexes}
        assert {
            f"idx_{schema}_processed_items_source_id",
            f"idx_{schema}_processed_items_topics",
            f"idx_{schema}_processed_items_entities",
        }.issubset(index_names)


def test_data_migration_content_chunks_indexes(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("content_chunks")}
    assert "idx_content_chunks_processed_item_id" in index_names


def test_data_migration_api_usage_logs_indexes(migrated_data_db: Engine) -> None:
    inspector = inspect(migrated_data_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("api_usage_logs")}
    assert {
        "idx_api_usage_logs_api_key_id",
        "idx_api_usage_logs_created_at",
        "idx_api_usage_logs_provider",
        "idx_api_usage_logs_request_type",
    }.issubset(index_names)


def test_data_migration_downgrade_removes_data_tables(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, DATA_REVISION)
    command.downgrade(alembic_cfg, CORE_REVISION)

    inspector = inspect(db_engine)
    public_tables = set(inspector.get_table_names())
    assert DATA_TABLES.isdisjoint(public_tables)

    schema_names = inspector.get_schema_names()
    for schema in PROCESSED_ITEM_SCHEMAS:
        if schema in schema_names:
            assert "processed_items" not in inspector.get_table_names(schema=schema)
        else:
            assert schema not in schema_names


def test_data_migration_downgrade_up_roundtrip(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, DATA_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, DATA_REVISION)

    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert DATA_TABLES.issubset(tables)

"""İçerik tablo migration integration testleri (003_content_tables)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

_LOCAL_DEV_URL = "postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev"
_CI_TEST_URL = "postgresql+asyncpg://test:test@localhost:5432/ygip_test"

CONTENT_TABLES = {
    "prompt_templates",
    "digests",
    "digest_sections",
    "chat_history",
    "notification_preferences",
}

DATA_REVISION = "002_data_tables"
CONTENT_REVISION = "003_content_tables"


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


def _reset_database(engine: Engine) -> None:
    with engine.connect() as connection:
        for schema in PROCESSED_ITEM_SCHEMAS:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()


@pytest.fixture
def migrated_content_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde 001→003 migration uygular."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def test_content_migration_creates_tables(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    tables = set(inspector.get_table_names())
    assert CONTENT_TABLES.issubset(tables)


def test_content_migration_digest_enums(migrated_content_db: Engine) -> None:
    expected_enums = {
        "digest_type_enum": ["turkish_media_weekly", "fmcg_weekly", "strategy_weekly"],
        "digest_status_enum": ["generating", "ready", "failed"],
    }
    with migrated_content_db.connect() as connection:
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


def test_content_migration_prompt_templates_indexes(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("prompt_templates")}
    assert {
        "idx_prompt_templates_digest_type",
        "idx_prompt_templates_is_active",
    }.issubset(index_names)


def test_content_migration_digests_indexes(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("digests")}
    assert {
        "idx_digests_digest_type",
        "idx_digests_status",
        "idx_digests_created_at",
        "idx_digests_period",
    }.issubset(index_names)


def test_content_migration_digest_sections_fk(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    fks = inspector.get_foreign_keys("digest_sections")
    fk_targets = {(fk["referred_table"], tuple(fk["referred_columns"])) for fk in fks}
    assert ("digests", ("id",)) in fk_targets
    assert ("prompt_templates", ("id",)) in fk_targets


def test_content_migration_chat_history_indexes(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    index_names = {idx["name"] for idx in inspector.get_indexes("chat_history")}
    assert {
        "idx_chat_history_user_id",
        "idx_chat_history_created_at",
    }.issubset(index_names)


def test_content_migration_notification_preferences_unique(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    unique_names = {
        uc["name"] for uc in inspector.get_unique_constraints("notification_preferences")
    }
    assert "uq_notification_preferences_user_id" in unique_names


def test_content_migration_prompt_templates_name_unique(migrated_content_db: Engine) -> None:
    inspector = inspect(migrated_content_db)
    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("prompt_templates")}
    assert "uq_prompt_templates_name" in unique_names


def test_content_migration_full_chain_upgrade(migrated_content_db: Engine) -> None:
    """001→003 ardışık upgrade sonrası alembic revision doğrulaması."""
    with migrated_content_db.connect() as connection:
        result = connection.execute(
            text("SELECT version_num FROM alembic_version")
        )
        assert result.scalar() == CONTENT_REVISION


def test_content_migration_downgrade_removes_content_tables(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_REVISION)
    command.downgrade(alembic_cfg, DATA_REVISION)

    inspector = inspect(db_engine)
    public_tables = set(inspector.get_table_names())
    assert CONTENT_TABLES.isdisjoint(public_tables)


def test_content_migration_downgrade_up_roundtrip(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONTENT_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, CONTENT_REVISION)

    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert CONTENT_TABLES.issubset(tables)

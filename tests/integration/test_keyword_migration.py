"""keyword takip tabloları migration integration testleri (007_keyword_tracking)."""

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

CONTENT_CATEGORY_REVISION = "006_content_category"
KEYWORD_REVISION = "007_keyword_tracking"
KEYWORD_TABLES = ("keywords", "keyword_category_ratings")


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


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _index_names(engine: Engine, table: str) -> set[str]:
    return {idx["name"] for idx in inspect(engine).get_indexes(table)}


def _enum_exists(engine: Engine, enum_name: str) -> bool:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": enum_name},
        )
        return result.scalar() is not None


@pytest.fixture
def migrated_db(db_engine: Engine) -> Iterator[Engine]:
    """Temiz DB üzerinde 001→007 migration uygular."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, KEYWORD_REVISION)
    yield db_engine
    command.downgrade(alembic_cfg, "base")


def test_keyword_tables_created(migrated_db: Engine) -> None:
    tables = _table_names(migrated_db)
    for table in KEYWORD_TABLES:
        assert table in tables


def test_keyword_category_enum_created(migrated_db: Engine) -> None:
    assert _enum_exists(migrated_db, "keyword_category_enum")


def test_keyword_indexes_created(migrated_db: Engine) -> None:
    keyword_indexes = _index_names(migrated_db, "keywords")
    assert "uq_keywords_term_tr_lower" in keyword_indexes
    assert "uq_keywords_term_en_lower" in keyword_indexes
    assert "idx_keywords_is_active" in keyword_indexes

    rating_indexes = _index_names(migrated_db, "keyword_category_ratings")
    assert "idx_keyword_category_ratings_keyword_id" in rating_indexes
    assert "idx_keyword_category_ratings_category" in rating_indexes


def test_rating_check_constraint_enforced(migrated_db: Engine) -> None:
    from sqlalchemy.exc import IntegrityError

    with migrated_db.connect() as connection:
        keyword_id = connection.execute(
            text(
                "INSERT INTO keywords (term_tr, term_en) "
                "VALUES ('test', 'test') RETURNING id"
            )
        ).scalar()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO keyword_category_ratings (keyword_id, category, rating) "
                    "VALUES (:kid, 'macro', 11)"
                ),
                {"kid": keyword_id},
            )
        connection.rollback()


def test_keyword_migration_revision(migrated_db: Engine) -> None:
    with migrated_db.connect() as connection:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        assert result.scalar() == KEYWORD_REVISION


def test_keyword_downgrade_removes_tables_and_enum(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, KEYWORD_REVISION)
    command.downgrade(alembic_cfg, CONTENT_CATEGORY_REVISION)

    tables = _table_names(db_engine)
    for table in KEYWORD_TABLES:
        assert table not in tables
    assert not _enum_exists(db_engine, "keyword_category_enum")


def test_keyword_downgrade_up_roundtrip(db_engine: Engine) -> None:
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, KEYWORD_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, KEYWORD_REVISION)

    assert "keywords" in _table_names(db_engine)
    assert _enum_exists(db_engine, "keyword_category_enum")

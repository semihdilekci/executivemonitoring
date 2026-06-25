"""Çeviri altyapısı migration testleri (016_translation_infra, Faz 6.5).

`news.processed_item_translations` sidecar tablo + `api_keys.request_type_scope` +
`translation_min_relevance_score` ayarı. `Docs/08` senaryoları: upgrade şema/kolon/ayar,
downgrade temizliği, round-trip, FK CASCADE + UNIQUE bütünlüğü, seed idempotency.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from scripts.seed import seed_system_settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.migration_db import (
    guard_destructive,
    make_alembic_config,
    resolve_sync_test_database_url,
)

PRIOR_REVISION = "015_fmcg_new_sections"
TRANSLATION_REVISION = "016_translation_infra"


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


def _insert_source(connection: Connection) -> uuid.UUID:
    source_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO sources
                (id, name, source_type, config, polling_interval_minutes,
                 status, error_count, category, target_phase)
            VALUES
                (:id, 'Seed Source', 'rss', '{}'::jsonb, 60,
                 'active', 0, 'macro', '1')
            """
        ),
        {"id": source_id},
    )
    return source_id


def _insert_raw_item(connection: Connection, source_id: uuid.UUID) -> uuid.UUID:
    raw_item_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO raw_items
                (id, source_id, external_id, content_hash, title,
                 raw_content, status)
            VALUES
                (:id, :source_id, 'ext-1', 'hash-1', 'Seed Title',
                 'raw', 'processed')
            """
        ),
        {"id": raw_item_id, "source_id": source_id},
    )
    return raw_item_id


def _insert_processed_item(connection: Connection) -> uuid.UUID:
    source_id = _insert_source(connection)
    raw_item_id = _insert_raw_item(connection, source_id)
    item_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO news.processed_items
                (id, raw_item_id, source_id, title, clean_content, summary,
                 language, relevance_score, topics, entities, published_at,
                 schema_category, content_category)
            VALUES
                (:id, :raw_item_id, :source_id, 'Seed', 'clean', 'summary',
                 'tr', 0.8, '[]'::jsonb, '[]'::jsonb, now(), 'news', 'macro')
            """
        ),
        {"id": item_id, "raw_item_id": raw_item_id, "source_id": source_id},
    )
    return item_id


@pytest.fixture
def migrated_db(db_engine: Engine) -> Iterator[Engine]:
    """015'e (Faz 6.5 head) migrate eder; her test 016'ya kendi yükseltir."""
    _reset_database(db_engine)
    command.upgrade(_alembic_config(), PRIOR_REVISION)
    yield db_engine
    command.downgrade(_alembic_config(), "base")


def _table_exists(connection: Connection, *, schema: str, table: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :name"
            ),
            {"schema": schema, "name": table},
        ).scalar()
    )


def _columns(connection: Connection, *, schema: str, table: str) -> set[str]:
    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": table},
    )
    return {row[0] for row in rows}


def test_upgrade_creates_translations_table(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        assert _table_exists(connection, schema="news", table="processed_item_translations")
        cols = _columns(connection, schema="news", table="processed_item_translations")
        assert {
            "id",
            "processed_item_id",
            "language",
            "title",
            "content",
            "is_original",
            "created_at",
        } <= cols


def test_upgrade_adds_api_key_request_type_scope(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        assert "request_type_scope" in _columns(connection, schema="public", table="api_keys")


def test_upgrade_seeds_translation_min_relevance_score(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        value = connection.execute(
            text(
                "SELECT value FROM system_settings "
                "WHERE key = 'translation_min_relevance_score'"
            )
        ).scalar_one()
        assert value == 75


def test_translation_row_insert_and_cascade(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        item_id = _insert_processed_item(connection)
        connection.execute(
            text(
                """
                INSERT INTO news.processed_item_translations
                    (processed_item_id, language, title, content, is_original)
                VALUES (:item_id, 'en', 'Original EN', 'english body', true)
                """
            ),
            {"item_id": item_id},
        )
        connection.commit()
        # CASCADE: processed_item silinince çeviri de düşer.
        connection.execute(
            text("DELETE FROM news.processed_items WHERE id = :id"), {"id": item_id}
        )
        connection.commit()
        remaining = connection.execute(
            text(
                "SELECT count(*) FROM news.processed_item_translations "
                "WHERE processed_item_id = :id"
            ),
            {"id": item_id},
        ).scalar_one()
        assert remaining == 0


def test_translation_unique_item_language(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        item_id = _insert_processed_item(connection)
        connection.execute(
            text(
                """
                INSERT INTO news.processed_item_translations
                    (processed_item_id, language, title, content)
                VALUES (:item_id, 'en', 'A', 'a')
                """
            ),
            {"item_id": item_id},
        )
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO news.processed_item_translations
                        (processed_item_id, language, title, content)
                    VALUES (:item_id, 'en', 'B', 'b')
                    """
                ),
                {"item_id": item_id},
            )
            connection.commit()


def test_upgrade_revision_is_translation_infra(migrated_db: Engine) -> None:
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version == TRANSLATION_REVISION


def test_downgrade_removes_translation_infra(migrated_db: Engine) -> None:
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, TRANSLATION_REVISION)
    command.downgrade(alembic_cfg, "-1")
    with migrated_db.connect() as connection:
        assert not _table_exists(
            connection, schema="news", table="processed_item_translations"
        )
        assert "request_type_scope" not in _columns(
            connection, schema="public", table="api_keys"
        )
        present = connection.execute(
            text(
                "SELECT count(*) FROM system_settings "
                "WHERE key = 'translation_min_relevance_score'"
            )
        ).scalar_one()
        assert present == 0


def test_downgrade_upgrade_roundtrip(migrated_db: Engine) -> None:
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, TRANSLATION_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, TRANSLATION_REVISION)
    with migrated_db.connect() as connection:
        assert _table_exists(connection, schema="news", table="processed_item_translations")


def test_seed_system_settings_translation_idempotent(
    db_engine: Engine, sync_database_url: str
) -> None:
    """Fresh head DB'de translation eşiği seed edilir; ikinci çalıştırma atlar."""
    _reset_database(db_engine)
    command.upgrade(_alembic_config(), TRANSLATION_REVISION)

    async def _run() -> tuple[int, int]:
        async_url = sync_database_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://", 1
        )
        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                first = await seed_system_settings(session)
                await session.commit()
                second = await seed_system_settings(session)
                await session.commit()
            return first.skipped, second.skipped
        finally:
            await engine.dispose()

    first_skipped, second_skipped = asyncio.run(_run())
    # Migration zaten translation eşiğini seed'ler → ilk seed onu atlar.
    assert first_skipped >= 1
    assert second_skipped >= 1

    with db_engine.connect() as connection:
        value = connection.execute(
            text(
                "SELECT value FROM system_settings "
                "WHERE key = 'translation_min_relevance_score'"
            )
        ).scalar_one()
        assert value == 75

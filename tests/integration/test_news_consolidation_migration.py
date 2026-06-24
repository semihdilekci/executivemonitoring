"""Haber schema konsolidasyonu migration testleri (009_news_consolidation, Faz 6.4).

Fixture: migration öncesi çoklu schema seed -> upgrade -> assert tek schema (`news`).
`Docs/08` §3.9 senaryoları: upgrade veri taşıma + bütünlük, downgrade round-trip.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from tests.integration.migration_db import (
    guard_destructive,
    make_alembic_config,
    resolve_sync_test_database_url,
)

UNIFY_REVISION = "008_unify_source_categories"
CONSOLIDATION_REVISION = "009_news_consolidation"
FK_REVISION = "010_content_chunks_fk"
FK_NAME = "fk_content_chunks_processed_item_id"

# Seed planı: her satır (schema, content_category, beklenen downgrade hedef schema'sı).
# news satırları yerinde kalır; legacy satırlar upgrade ile news'e taşınır.
SEED_PLAN = [
    {"schema": "news", "content_category": "macro", "downgrade_schema": "news"},
    {"schema": "news", "content_category": "strategy", "downgrade_schema": "news"},
    {"schema": "market", "content_category": "finance", "downgrade_schema": "market"},
    {"schema": "geo", "content_category": "geopolitical", "downgrade_schema": "geo"},
    {"schema": "fmcg", "content_category": "fmcg", "downgrade_schema": "fmcg"},
]


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


def _insert_raw_item(connection: Connection, source_id: uuid.UUID, marker: str) -> uuid.UUID:
    raw_item_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO raw_items
                (id, source_id, external_id, content_hash, title,
                 raw_content, status)
            VALUES
                (:id, :source_id, :external_id, :content_hash, 'Seed Title',
                 'raw', 'processed')
            """
        ),
        {
            "id": raw_item_id,
            "source_id": source_id,
            "external_id": f"ext-{marker}",
            "content_hash": f"hash-{marker}",
        },
    )
    return raw_item_id


def _insert_processed_item(
    connection: Connection,
    *,
    schema: str,
    source_id: uuid.UUID,
    raw_item_id: uuid.UUID,
    content_category: str,
) -> uuid.UUID:
    item_id = uuid.uuid4()
    connection.execute(
        text(
            f"""
            INSERT INTO {schema}.processed_items
                (id, raw_item_id, source_id, title, clean_content, summary,
                 language, relevance_score, topics, entities, published_at,
                 schema_category, content_category)
            VALUES
                (:id, :raw_item_id, :source_id, :title, 'clean', 'summary',
                 'tr', 0.8, '[]'::jsonb, '[]'::jsonb, now(),
                 :schema_category, :content_category)
            """
        ),
        {
            "id": item_id,
            "raw_item_id": raw_item_id,
            "source_id": source_id,
            "title": f"{schema}-{content_category}",
            "schema_category": schema,
            "content_category": content_category,
        },
    )
    return item_id


def _insert_chunk(connection: Connection, processed_item_id: uuid.UUID) -> uuid.UUID:
    chunk_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO content_chunks
                (id, processed_item_id, chunk_index, chunk_text, token_count, embedding)
            VALUES
                (:id, :processed_item_id, 0, 'chunk', 3, :embedding)
            """
        ),
        {
            "id": chunk_id,
            "processed_item_id": processed_item_id,
            "embedding": "[" + ",".join(["0"] * 1536) + "]",
        },
    )
    return chunk_id


def _count(connection: Connection, schema: str) -> int:
    return int(
        connection.execute(
            text(f"SELECT count(*) FROM {schema}.processed_items")
        ).scalar_one()
    )


@pytest.fixture
def seeded_db(db_engine: Engine) -> Iterator[dict[str, object]]:
    """008'e kadar migrate eder, çoklu schema haber + chunk seed eder."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, UNIFY_REVISION)

    seeded: list[dict[str, object]] = []
    with db_engine.connect() as connection:
        source_id = _insert_source(connection)
        for index, plan in enumerate(SEED_PLAN):
            raw_item_id = _insert_raw_item(connection, source_id, marker=str(index))
            item_id = _insert_processed_item(
                connection,
                schema=str(plan["schema"]),
                source_id=source_id,
                raw_item_id=raw_item_id,
                content_category=str(plan["content_category"]),
            )
            chunk_id = _insert_chunk(connection, item_id)
            seeded.append(
                {
                    "item_id": item_id,
                    "chunk_id": chunk_id,
                    "content_category": plan["content_category"],
                    "origin_schema": plan["schema"],
                    "downgrade_schema": plan["downgrade_schema"],
                }
            )
        connection.commit()

    yield {"engine": db_engine, "seeded": seeded}
    command.downgrade(alembic_cfg, "base")


def test_upgrade_moves_all_news_rows_to_news_schema(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)

    with engine.connect() as connection:
        assert _count(connection, "news") == len(SEED_PLAN)
        for schema in ("market", "geo", "transport", "fmcg"):
            assert _count(connection, schema) == 0


def test_upgrade_preserves_uuid_and_content_category(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    seeded: list[dict[str, object]] = seeded_db["seeded"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)

    with engine.connect() as connection:
        for row in seeded:
            result = connection.execute(
                text(
                    "SELECT schema_category, content_category "
                    "FROM news.processed_items WHERE id = :id"
                ),
                {"id": row["item_id"]},
            ).one()
            # UUID korunur (kayıt id ile bulunur), schema_category news, content_category değişmez.
            assert result.schema_category == "news"
            assert result.content_category == row["content_category"]


def test_upgrade_keeps_chunk_references_intact(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    seeded: list[dict[str, object]] = seeded_db["seeded"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)

    with engine.connect() as connection:
        for row in seeded:
            linked = connection.execute(
                text(
                    "SELECT count(*) FROM content_chunks cc "
                    "JOIN news.processed_items p ON p.id = cc.processed_item_id "
                    "WHERE cc.id = :chunk_id"
                ),
                {"chunk_id": row["chunk_id"]},
            ).scalar_one()
            assert linked == 1


def test_upgrade_revision_is_consolidation(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)

    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version == CONSOLIDATION_REVISION


def test_downgrade_redistributes_by_content_category(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    seeded: list[dict[str, object]] = seeded_db["seeded"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)
    command.downgrade(alembic_cfg, "-1")

    with engine.connect() as connection:
        for row in seeded:
            target = str(row["downgrade_schema"])
            placement = connection.execute(
                text(
                    f"SELECT schema_category FROM {target}.processed_items "
                    "WHERE id = :id"
                ),
                {"id": row["item_id"]},
            ).one()
            assert placement.schema_category == target


def test_downgrade_upgrade_roundtrip_lands_in_news(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, CONSOLIDATION_REVISION)

    with engine.connect() as connection:
        assert _count(connection, "news") == len(SEED_PLAN)
        for schema in ("market", "geo", "transport", "fmcg"):
            assert _count(connection, schema) == 0


def _fk_exists(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE constraint_name = :name AND constraint_type = 'FOREIGN KEY'"
            ),
            {"name": FK_NAME},
        ).scalar()
    )


def test_fk_added_after_upgrade(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, FK_REVISION)

    with engine.connect() as connection:
        # Konsolide chunk'lar (009 sonrası news'e bağlı) FK ile uyumlu — upgrade geçti.
        assert _fk_exists(connection)


def test_fk_rejects_orphan_chunk(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, FK_REVISION)

    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                """
                INSERT INTO content_chunks
                    (id, processed_item_id, chunk_index, chunk_text, token_count, embedding)
                VALUES
                    (:id, :pid, 0, 'orphan', 3, :embedding)
                """
            ),
            {
                "id": uuid.uuid4(),
                "pid": uuid.uuid4(),  # news.processed_items'ta yok → FK ihlali
                "embedding": "[" + ",".join(["0"] * 1536) + "]",
            },
        )


def test_fk_cascades_on_processed_item_delete(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    seeded: list[dict[str, object]] = seeded_db["seeded"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, FK_REVISION)

    target = seeded[0]
    with engine.connect() as connection:
        connection.execute(
            text("DELETE FROM news.processed_items WHERE id = :id"),
            {"id": target["item_id"]},
        )
        connection.commit()
        remaining = connection.execute(
            text("SELECT count(*) FROM content_chunks WHERE id = :chunk_id"),
            {"chunk_id": target["chunk_id"]},
        ).scalar_one()
        assert remaining == 0


def test_fk_downgrade_removes_constraint(seeded_db: dict[str, object]) -> None:
    engine: Engine = seeded_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, FK_REVISION)
    command.downgrade(alembic_cfg, "-1")  # 009'a dön — FK kalkar

    with engine.connect() as connection:
        assert not _fk_exists(connection)

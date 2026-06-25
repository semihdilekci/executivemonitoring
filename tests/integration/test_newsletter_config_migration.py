"""Newsletter config migration testleri (013_newsletter_config, Faz 6.5, ADR-0003).

`prompt_templates` → `newsletter_templates`/`newsletter_sections` migrate→drop;
`digests` enum→FK+slug+summary; `digest_sections` provenance rename; global anlık-prompt
seed. `Docs/08` §3.10 senaryoları: upgrade veri taşıma + bütünlük, downgrade round-trip,
seed idempotency.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from packages.shared.enums import PROCESSED_ITEM_SCHEMAS
from scripts.seed import seed_newsletter_templates
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.migration_db import (
    guard_destructive,
    make_alembic_config,
    resolve_sync_test_database_url,
)

PRIOR_REVISION = "012_api_key_model"
NEWSLETTER_REVISION = "013_newsletter_config"

# Migrate öncesi prompt_templates seed planı: (digest_type, section_key).
# 2 bülten tipi; strategy 2 bölüm, fmcg 1 bölüm → 2 newsletter_template, 3 newsletter_section.
PROMPT_SEED = [
    ("strategy_weekly", "executive_summary"),
    ("strategy_weekly", "global_trends"),
    ("fmcg_weekly", "market_overview"),
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


def _insert_prompt_template(
    connection: Connection,
    *,
    digest_type: str,
    section_key: str,
    version: int,
) -> uuid.UUID:
    template_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO prompt_templates
                (id, name, digest_type, section_key, system_prompt,
                 user_prompt_template, model_preference, is_active, version)
            VALUES
                (:id, :name, :digest_type, :section_key, :system_prompt,
                 :user_prompt, 'groq', true, :version)
            """
        ),
        {
            "id": template_id,
            "name": f"{digest_type}_{section_key}",
            "digest_type": digest_type,
            "section_key": section_key,
            "system_prompt": f"system::{section_key}",
            "user_prompt": f"user::{section_key} {{{{articles}}}}",
            "version": version,
        },
    )
    return template_id


def _insert_digest(connection: Connection, *, digest_type: str) -> uuid.UUID:
    digest_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO digests
                (id, digest_type, title, status, period_start, period_end,
                 total_sources_used, generation_metadata)
            VALUES
                (:id, :digest_type, 'Seed Digest', 'ready', now() - interval '7 days',
                 now(), 0, '{}'::jsonb)
            """
        ),
        {"id": digest_id, "digest_type": digest_type},
    )
    return digest_id


def _insert_digest_section(
    connection: Connection,
    *,
    digest_id: uuid.UUID,
    prompt_template_id: uuid.UUID,
) -> uuid.UUID:
    section_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO digest_sections
                (id, digest_id, section_order, section_title, ai_summary,
                 impact_note, source_references, prompt_template_id)
            VALUES
                (:id, :digest_id, 0, 'Seed Section', 'snapshot özet',
                 'snapshot etki', '[]'::jsonb, :prompt_template_id)
            """
        ),
        {
            "id": section_id,
            "digest_id": digest_id,
            "prompt_template_id": prompt_template_id,
        },
    )
    return section_id


@pytest.fixture
def migrated_db(db_engine: Engine) -> Iterator[dict[str, object]]:
    """012'ye migrate eder, prompt_templates + digest + digest_section seed eder."""
    _reset_database(db_engine)
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, PRIOR_REVISION)

    with db_engine.connect() as connection:
        first_template_id: uuid.UUID | None = None
        for index, (digest_type, section_key) in enumerate(PROMPT_SEED):
            template_id = _insert_prompt_template(
                connection,
                digest_type=digest_type,
                section_key=section_key,
                version=index,
            )
            if first_template_id is None:
                first_template_id = template_id

        digest_id = _insert_digest(connection, digest_type="strategy_weekly")
        assert first_template_id is not None
        section_id = _insert_digest_section(
            connection,
            digest_id=digest_id,
            prompt_template_id=first_template_id,
        )
        connection.commit()

    yield {"engine": db_engine, "digest_id": digest_id, "section_id": section_id}
    command.downgrade(alembic_cfg, "base")


def _table_exists(connection: Connection, table: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :name"
            ),
            {"name": table},
        ).scalar()
    )


def _columns(connection: Connection, table: str) -> set[str]:
    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table},
    )
    return {row[0] for row in rows}


def test_upgrade_creates_newsletter_tables(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        assert _table_exists(connection, "newsletter_templates")
        assert _table_exists(connection, "newsletter_sections")
        assert not _table_exists(connection, "prompt_templates")


def test_upgrade_migrates_templates_and_sections(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        # 2 distinct digest_type → 2 newsletter_template
        slugs = {
            row[0]
            for row in connection.execute(text("SELECT slug FROM newsletter_templates"))
        }
        assert slugs == {"strategy_weekly", "fmcg_weekly"}
        # 3 prompt_templates satırı → 3 newsletter_section (section_key → name)
        section_count = connection.execute(
            text("SELECT count(*) FROM newsletter_sections")
        ).scalar_one()
        assert section_count == len(PROMPT_SEED)
        # strategy bülteni 2 bölüm, sort_order 0/1 benzersiz
        orders = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT ns.sort_order FROM newsletter_sections ns "
                    "JOIN newsletter_templates nt ON nt.id = ns.newsletter_template_id "
                    "WHERE nt.slug = 'strategy_weekly' ORDER BY ns.sort_order"
                )
            )
        ]
        assert orders == [0, 1]


def test_upgrade_alters_digests(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    digest_id = migrated_db["digest_id"]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        cols = _columns(connection, "digests")
        assert {"newsletter_slug", "newsletter_template_id", "summary"} <= cols
        assert "digest_type" not in cols
        row = connection.execute(
            text(
                "SELECT d.newsletter_slug, d.summary, nt.slug "
                "FROM digests d JOIN newsletter_templates nt "
                "ON nt.id = d.newsletter_template_id WHERE d.id = :id"
            ),
            {"id": digest_id},
        ).one()
        assert row.newsletter_slug == "strategy_weekly"
        assert row.summary is None
        assert row[2] == "strategy_weekly"  # FK doğru bültene bağlandı


def test_upgrade_renames_digest_section_provenance(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    section_id = migrated_db["section_id"]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        cols = _columns(connection, "digest_sections")
        assert "newsletter_section_id" in cols
        assert "prompt_template_id" not in cols
        # snapshot içerik korunur; provenance NULL'a çekilir (eski tablo düştü)
        row = connection.execute(
            text(
                "SELECT ai_summary, newsletter_section_id "
                "FROM digest_sections WHERE id = :id"
            ),
            {"id": section_id},
        ).one()
        assert row.ai_summary == "snapshot özet"
        assert row.newsletter_section_id is None


def test_upgrade_seeds_global_impact_settings(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        keys = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT key FROM system_settings "
                    "WHERE key LIKE 'newsletter_impact_%'"
                )
            )
        }
        assert keys == {
            "newsletter_impact_system_prompt",
            "newsletter_impact_user_prompt",
        }


def test_upgrade_revision_is_newsletter_config(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    command.upgrade(_alembic_config(), NEWSLETTER_REVISION)
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert version == NEWSLETTER_REVISION


def test_downgrade_restores_prompt_templates(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, NEWSLETTER_REVISION)
    command.downgrade(alembic_cfg, "-1")
    with engine.connect() as connection:
        assert _table_exists(connection, "prompt_templates")
        assert not _table_exists(connection, "newsletter_templates")
        cols = _columns(connection, "digests")
        assert "digest_type" in cols
        assert "newsletter_slug" not in cols
        # digest_type slug'dan geri türetildi
        dtype = connection.execute(
            text("SELECT digest_type FROM digests WHERE id = :id"),
            {"id": migrated_db["digest_id"]},
        ).scalar_one()
        assert dtype == "strategy_weekly"


def test_downgrade_upgrade_roundtrip_lands_at_head(migrated_db: dict[str, object]) -> None:
    engine: Engine = migrated_db["engine"]  # type: ignore[assignment]
    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, NEWSLETTER_REVISION)
    command.downgrade(alembic_cfg, "-1")
    command.upgrade(alembic_cfg, NEWSLETTER_REVISION)
    with engine.connect() as connection:
        assert _table_exists(connection, "newsletter_templates")
        assert not _table_exists(connection, "prompt_templates")


def test_seed_newsletter_templates_idempotent(
    db_engine: Engine, sync_database_url: str
) -> None:
    """Fresh head DB'de seed 3 bülten oluşturur, ikinci çalıştırma 0 (slug upsert).

    `seed_newsletter_templates` güncel ORM modelini kullanır (`content_categories`
    014'te, fmcg bölümleri 015'te eklendi); bu yüzden seed öncesi şema **head**'e
    çekilir — yalnızca 013'e upgrade seed'i `UndefinedColumn` ile kırardı.
    """
    _reset_database(db_engine)
    command.upgrade(_alembic_config(), "head")

    async def _run() -> tuple[int, int]:
        async_url = sync_database_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://", 1
        )
        engine = create_async_engine(async_url)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                first = await seed_newsletter_templates(session)
                await session.commit()
                second = await seed_newsletter_templates(session)
                await session.commit()
            return first.created, second.created
        finally:
            await engine.dispose()

    first_created, second_created = asyncio.run(_run())
    assert first_created == 3
    assert second_created == 0

    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM newsletter_templates")
        ).scalar_one()
        section_count = connection.execute(
            text("SELECT count(*) FROM newsletter_sections")
        ).scalar_one()
    assert count == 3
    assert section_count == 9  # strategy(2) + turkish_media(2) + fmcg(5) — 015 fmcg bölümleri

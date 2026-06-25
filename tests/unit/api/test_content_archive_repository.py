"""İçerik Arşivi repository + service unit testleri (Faz 6.2 — İterasyon 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from apps.api.core.exceptions import ValidationException
from apps.api.repositories.digest_usage_repository import (
    DigestUsageRepository,
    DigestUsageRow,
    _extract_referenced_ids,
)
from apps.api.repositories.processed_item_repository import (
    ProcessedItemListFilters,
    ProcessedItemRepository,
    decode_cursor,
    encode_cursor,
)
from apps.api.services.content_archive_service import ContentArchiveService
from sqlalchemy.ext.asyncio import AsyncSession


def _make_row(*, schema: str = "news", item_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id or uuid.uuid4(),
        schema_category=schema,
        content_category="macro",
        source_id=uuid.uuid4(),
        source_name="Bloomberg HT RSS",
        source_type="rss",
        title="TCMB faiz kararı",
        url="https://www.bloomberght.com/haber/tcmb",
        language="tr",
        relevance_score=0.82,
        topics=["tcmb", "faiz"],
        published_at=datetime(2026, 6, 18, 9, 30, tzinfo=UTC),
        processed_at=datetime(2026, 6, 18, 9, 31, tzinfo=UTC),
    )


def _result_with_rows(rows: list[object]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


# --- cursor helpers ---------------------------------------------------------


def test_encode_decode_cursor_round_trip() -> None:
    item_id = uuid.uuid4()
    cursor = encode_cursor("market", item_id)
    assert cursor == f"market:{item_id}"
    assert decode_cursor(cursor) == ("market", item_id)


@pytest.mark.parametrize("bad", ["", "news:", "unknown:" + str(uuid.uuid4()), "news:not-a-uuid"])
def test_decode_cursor_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        decode_cursor(bad)


# --- repository list --------------------------------------------------------


async def test_list_has_more_and_next_cursor() -> None:
    repo = ProcessedItemRepository()
    rows = [_make_row(), _make_row(), _make_row()]
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows(rows)

    page, next_cursor, has_more = await repo.list(
        db,
        filters=ProcessedItemListFilters(),
        limit=2,
    )

    assert has_more is True
    assert len(page) == 2
    assert next_cursor == encode_cursor(page[-1].schema_category, page[-1].id)
    # cursor yokken yalnızca birleşik sorgu çalışır (cursor lookup execute yok)
    db.execute.assert_awaited_once()


async def test_list_no_more_when_under_limit() -> None:
    repo = ProcessedItemRepository()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows([_make_row()])

    page, next_cursor, has_more = await repo.list(
        db,
        filters=ProcessedItemListFilters(),
        limit=20,
    )

    assert has_more is False
    assert next_cursor is None
    assert len(page) == 1


async def test_list_single_schema_skips_union() -> None:
    repo = ProcessedItemRepository()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows([_make_row(schema="fmcg")])

    page, _, _ = await repo.list(
        db,
        filters=ProcessedItemListFilters(schema_category="fmcg"),
        limit=20,
    )
    assert len(page) == 1


@pytest.mark.parametrize(
    ("has_digest", "expect_negated"),
    [(True, False), (False, True)],
)
async def test_list_has_digest_renders_jsonb_exists_in_sql(
    has_digest: bool, expect_negated: bool
) -> None:
    """has_digest filtresi DB seviyesinde korelasyonlu JSONB EXISTS üretmeli.

    Regresyon koruması: filtre pagination'dan önce uygulanmalı, aksi halde
    varsayılan sıralamada (processed_at desc) bülten kullanan içerikler
    ilk sayfaya hiç düşmeyebilir.
    """
    repo = ProcessedItemRepository()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows([])

    await repo.list(
        db,
        filters=ProcessedItemListFilters(schema_category="news", has_digest=has_digest),
        limit=20,
    )

    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "exists" in sql
    assert "source_references" in sql
    assert "@>" in sql
    assert ("not (exists" in sql or "not exists" in sql) is expect_negated


async def test_list_no_has_digest_skips_exists() -> None:
    repo = ProcessedItemRepository()
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows([])

    await repo.list(
        db,
        filters=ProcessedItemListFilters(schema_category="news"),
        limit=20,
    )

    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "source_references" not in sql


async def test_list_unknown_schema_returns_empty() -> None:
    repo = ProcessedItemRepository()
    db = AsyncMock(spec=AsyncSession)

    page, next_cursor, has_more = await repo.list(
        db,
        filters=ProcessedItemListFilters(schema_category="does-not-exist"),
        limit=20,
    )

    assert page == []
    assert next_cursor is None
    assert has_more is False
    db.execute.assert_not_awaited()


# --- digest usage repository ------------------------------------------------


def test_extract_referenced_ids() -> None:
    pid = str(uuid.uuid4())
    refs = [
        {"processed_item_id": pid, "title": "x"},
        {"title": "no id"},
        "garbage",
    ]
    assert _extract_referenced_ids(refs) == {pid}
    assert _extract_referenced_ids(None) == set()


async def test_find_for_processed_item_ids_maps_usages() -> None:
    repo = DigestUsageRepository()
    pid = uuid.uuid4()
    section = SimpleNamespace(
        source_references=[{"processed_item_id": str(pid), "title": "x"}],
        section_title="Makroekonomik Gelişmeler",
        section_order=0,
    )
    digest = SimpleNamespace(
        id=uuid.uuid4(),
        newsletter_slug="strategy_weekly",
        title="Strateji Haftalık",
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _result_with_rows([(section, digest)])

    usages = await repo.find_for_processed_item_ids(db, [pid])

    assert len(usages[pid]) == 1
    assert usages[pid][0].digest_id == digest.id
    assert usages[pid][0].section_title == "Makroekonomik Gelişmeler"


async def test_find_for_processed_item_ids_empty_input() -> None:
    repo = DigestUsageRepository()
    db = AsyncMock(spec=AsyncSession)
    assert await repo.find_for_processed_item_ids(db, []) == {}
    db.execute.assert_not_awaited()


# --- service ----------------------------------------------------------------


def _usage_row(digest_id: uuid.UUID) -> DigestUsageRow:
    return DigestUsageRow(
        digest_id=digest_id,
        newsletter_slug="strategy_weekly",
        digest_title="Strateji Haftalık",
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
        section_title="Makroekonomik Gelişmeler",
    )


async def test_service_maps_rows_and_excludes_clean_content() -> None:
    row = _make_row()
    items_repo = MagicMock()
    items_repo.list = AsyncMock(return_value=([row], "news:abc", True))
    usages_repo = MagicMock()
    usages_repo.find_for_processed_item_ids = AsyncMock(return_value={row.id: []})
    service = ContentArchiveService(processed_items=items_repo, digest_usages=usages_repo)
    db = AsyncMock(spec=AsyncSession)

    response = await service.list_items(db, limit=20)

    assert len(response.data) == 1
    assert response.pagination.has_more is True
    assert response.pagination.next_cursor == "news:abc"
    assert not hasattr(response.data[0], "clean_content")


async def test_service_dedupes_digest_usages_by_digest_id() -> None:
    row = _make_row()
    digest_id = uuid.uuid4()
    items_repo = MagicMock()
    items_repo.list = AsyncMock(return_value=([row], None, False))
    usages_repo = MagicMock()
    usages_repo.find_for_processed_item_ids = AsyncMock(
        return_value={row.id: [_usage_row(digest_id), _usage_row(digest_id)]}
    )
    service = ContentArchiveService(processed_items=items_repo, digest_usages=usages_repo)
    db = AsyncMock(spec=AsyncSession)

    response = await service.list_items(db)

    assert len(response.data[0].digest_usages) == 1


@pytest.mark.parametrize("has_digest", [True, False, None])
async def test_service_propagates_has_digest_to_repository(has_digest: bool | None) -> None:
    """has_digest DB seviyesinde filtrelenir: servis repo'ya filtre olarak geçirmeli."""
    row = _make_row()
    items_repo = MagicMock()
    items_repo.list = AsyncMock(return_value=([row], None, False))
    usages_repo = MagicMock()
    usages_repo.find_for_processed_item_ids = AsyncMock(return_value={row.id: []})
    service = ContentArchiveService(processed_items=items_repo, digest_usages=usages_repo)
    db = AsyncMock(spec=AsyncSession)

    await service.list_items(db, has_digest=has_digest)

    passed_filters = items_repo.list.await_args.kwargs["filters"]
    assert passed_filters.has_digest is has_digest


async def test_service_invalid_cursor_raises_validation() -> None:
    items_repo = MagicMock()
    items_repo.list = AsyncMock(side_effect=ValueError("bad cursor"))
    usages_repo = MagicMock()
    service = ContentArchiveService(processed_items=items_repo, digest_usages=usages_repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValidationException):
        await service.list_items(db, cursor="garbage")

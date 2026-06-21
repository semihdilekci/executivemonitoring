"""İçerik Arşivi cross-schema veri erişimi (Faz 6.2) — `Docs/04` §8.8.

5 domain schema (`news`/`market`/`geo`/`transport`/`fmcg`) `processed_items`
tablolarını `UNION ALL` ile birleştirir; cursor pagination `{schema}:{uuid}`.
Liste yanıtında `clean_content` yer almaz (performans + detay endpoint ayrımı).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from packages.shared.models.content_chunk import ContentChunk
from packages.shared.models.digest_section import DigestSection
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS, ProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import Select, String, and_, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProcessedItemListFilters:
    """`GET /admin/processed-items` filtre seti (`Docs/03` §11.6)."""

    source_id: uuid.UUID | None = None
    schema_category: str | None = None
    content_category: str | None = None
    published_from: date | None = None
    published_to: date | None = None
    min_score: float | None = None
    topic: str | None = None
    q: str | None = None
    has_digest: bool | None = None


def encode_cursor(schema_category: str, item_id: uuid.UUID) -> str:
    """`{schema}:{uuid}` cursor üretir."""
    return f"{schema_category}:{item_id}"


def decode_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    """`{schema}:{uuid}` cursor çözer; geçersizse `ValueError`."""
    schema, _, raw_id = cursor.partition(":")
    if schema not in PROCESSED_ITEM_MODELS or not raw_id:
        raise ValueError("Geçersiz cursor formatı.")
    return schema, uuid.UUID(raw_id)


# Sıralanabilir alanlar (`Docs/03` §11.6). Hepsi keyset cursor ile uyumlu;
# `published_at` nullable olduğundan `processed_at` ile coalesce edilerek
# null değer üretmez (tie-break daima `id`).
SORT_FIELDS: frozenset[str] = frozenset(
    {"processed_at", "published_at", "relevance_score", "title"}
)
DEFAULT_SORT_FIELD = "processed_at"
DEFAULT_SORT_DIR = "desc"


def _sort_expression(model: type[ProcessedItem], sort_by: str) -> Any:
    """Seçilen alan için keyset/order_by ifadesi (asla null dönmez)."""
    if sort_by == "published_at":
        return func.coalesce(model.published_at, model.processed_at)
    if sort_by == "relevance_score":
        return model.relevance_score
    if sort_by == "title":
        return model.title
    return model.processed_at


class ProcessedItemRepository:
    """5 schema processed_items birleşik sorgu + cursor pagination."""

    def _target_schemas(self, schema_category: str | None) -> list[str]:
        if schema_category is not None:
            return [schema_category] if schema_category in PROCESSED_ITEM_MODELS else []
        return list(PROCESSED_ITEM_MODELS)

    def _build_schema_select(
        self,
        schema: str,
        model: type[ProcessedItem],
        filters: ProcessedItemListFilters,
        *,
        sort_by: str,
        sort_dir: str,
        cursor_sort_value: Any,
        cursor_id: uuid.UUID | None,
    ) -> Select[Any]:
        sort_expr = _sort_expression(model, sort_by)
        stmt: Select[Any] = (
            select(
                model.id.label("id"),
                literal(schema).label("schema_category"),
                model.content_category.label("content_category"),
                model.source_id.label("source_id"),
                Source.name.label("source_name"),
                Source.source_type.label("source_type"),
                model.title.label("title"),
                RawItem.raw_metadata["url"].astext.label("url"),
                model.language.label("language"),
                model.relevance_score.label("relevance_score"),
                model.topics.label("topics"),
                model.published_at.label("published_at"),
                model.processed_at.label("processed_at"),
                sort_expr.label("sort_key"),
            )
            .join(Source, Source.id == model.source_id)
            .join(RawItem, RawItem.id == model.raw_item_id)
        )

        if filters.source_id is not None:
            stmt = stmt.where(model.source_id == filters.source_id)
        if filters.content_category is not None:
            stmt = stmt.where(model.content_category == filters.content_category)
        if filters.min_score is not None:
            stmt = stmt.where(model.relevance_score >= filters.min_score)
        if filters.published_from is not None:
            start_dt = datetime.combine(filters.published_from, time.min, tzinfo=UTC)
            stmt = stmt.where(model.published_at >= start_dt)
        if filters.published_to is not None:
            end_exclusive = datetime.combine(
                filters.published_to + timedelta(days=1),
                time.min,
                tzinfo=UTC,
            )
            stmt = stmt.where(model.published_at < end_exclusive)
        if filters.topic is not None:
            stmt = stmt.where(model.topics.contains([filters.topic]))
        if filters.q is not None:
            stmt = stmt.where(model.title.ilike(f"%{filters.q}%"))
        if filters.has_digest is not None:
            # Bülten kullanımı: `digest_sections.source_references` JSONB içinde bu
            # processed_item id'sine referans veren section var mı? Korelasyonlu
            # EXISTS → filtre DB seviyesinde, pagination'dan ÖNCE uygulanır.
            ref_match = func.jsonb_build_array(
                func.jsonb_build_object("processed_item_id", cast(model.id, String))
            )
            usage_exists = (
                select(literal(1))
                .where(DigestSection.source_references.op("@>")(ref_match))
                .exists()
            )
            stmt = stmt.where(usage_exists if filters.has_digest else ~usage_exists)

        if cursor_sort_value is not None and cursor_id is not None:
            if sort_dir == "asc":
                stmt = stmt.where(
                    or_(
                        sort_expr > cursor_sort_value,
                        and_(sort_expr == cursor_sort_value, model.id > cursor_id),
                    )
                )
            else:
                stmt = stmt.where(
                    or_(
                        sort_expr < cursor_sort_value,
                        and_(sort_expr == cursor_sort_value, model.id < cursor_id),
                    )
                )
        return stmt

    async def _resolve_cursor(
        self,
        db: AsyncSession,
        schema: str,
        item_id: uuid.UUID,
        sort_by: str,
    ) -> Any:
        """Cursor satırının sıralama anahtarı değerini getirir; yoksa None."""
        model = PROCESSED_ITEM_MODELS.get(schema)
        if model is None:
            return None
        result = await db.execute(
            select(_sort_expression(model, sort_by)).where(model.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        *,
        filters: ProcessedItemListFilters,
        limit: int = 20,
        cursor: str | None = None,
        sort_by: str = DEFAULT_SORT_FIELD,
        sort_dir: str = DEFAULT_SORT_DIR,
    ) -> tuple[list[Any], str | None, bool]:
        """Birleşik liste — keyset sıralama `sort_key {dir}, id {dir}`; `limit+1` has_more."""
        resolved_sort = sort_by if sort_by in SORT_FIELDS else DEFAULT_SORT_FIELD
        resolved_dir = "asc" if sort_dir == "asc" else "desc"

        schemas = self._target_schemas(filters.schema_category)
        if not schemas:
            return [], None, False

        cursor_sort_value: Any = None
        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            cursor_schema, cursor_id = decode_cursor(cursor)
            cursor_sort_value = await self._resolve_cursor(
                db, cursor_schema, cursor_id, resolved_sort
            )
            if cursor_sort_value is None:
                cursor_id = None  # cursor satırı yok → filtre uygulanmaz

        subqueries = [
            self._build_schema_select(
                schema,
                PROCESSED_ITEM_MODELS[schema],
                filters,
                sort_by=resolved_sort,
                sort_dir=resolved_dir,
                cursor_sort_value=cursor_sort_value,
                cursor_id=cursor_id,
            )
            for schema in schemas
        ]

        if len(subqueries) == 1:
            combined = subqueries[0].subquery()
        else:
            combined = union_all(*subqueries).subquery()

        order_cols = (
            (combined.c.sort_key.asc(), combined.c.id.asc())
            if resolved_dir == "asc"
            else (combined.c.sort_key.desc(), combined.c.id.desc())
        )
        query = select(combined).order_by(*order_cols).limit(limit + 1)
        result = await db.execute(query)
        rows = list(result.all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        next_cursor = (
            encode_cursor(rows[-1].schema_category, rows[-1].id) if has_more and rows else None
        )
        return rows, next_cursor, has_more

    async def get_by_id(
        self,
        db: AsyncSession,
        schema_category: str,
        item_id: uuid.UUID,
    ) -> Any | None:
        """Tek detay satırı — `clean_content` + `entities` dahil; source adı join.

        `schema_category` hangi tabloda aranacağını belirler; geçersiz şema → None.
        """
        model = PROCESSED_ITEM_MODELS.get(schema_category)
        if model is None:
            return None

        stmt: Select[Any] = (
            select(
                model.id.label("id"),
                literal(schema_category).label("schema_category"),
                model.content_category.label("content_category"),
                model.source_id.label("source_id"),
                Source.name.label("source_name"),
                Source.source_type.label("source_type"),
                model.title.label("title"),
                RawItem.raw_metadata["url"].astext.label("url"),
                model.clean_content.label("clean_content"),
                model.summary.label("summary"),
                model.language.label("language"),
                model.relevance_score.label("relevance_score"),
                model.topics.label("topics"),
                model.entities.label("entities"),
                model.published_at.label("published_at"),
                model.processed_at.label("processed_at"),
            )
            .join(Source, Source.id == model.source_id)
            .join(RawItem, RawItem.id == model.raw_item_id)
            .where(model.id == item_id)
        )
        result = await db.execute(stmt)
        return result.first()

    async def count_chunks(self, db: AsyncSession, item_id: uuid.UUID) -> int:
        """`content_chunks` (mantıksal FK) sayısı — detay `chunk_count`."""
        result = await db.execute(
            select(func.count())
            .select_from(ContentChunk)
            .where(ContentChunk.processed_item_id == item_id)
        )
        return int(result.scalar_one() or 0)

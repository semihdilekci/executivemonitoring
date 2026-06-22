"""Pipeline run içerik kırılımı repository — okunan/işlenen/elenen raw_items (Faz 6.3).

`İşleme` adımındaki "Elendi" (gate/dedup) ile "Hatalı" (gerçek hata) ayrımını ve elenen
içeriğin kendisini gösterir (`Docs/04` §8.3 keyword gate). Run penceresi `[started_at,
finished_at]` (bitmemişse `now`) ile `raw_items` taranır; her kayıt processed_items
partition'larında karşılığı var mı (işlendi), `FAILED` mı (hata), yoksa elendi mi diye
sınıflanır. Yalnızca okuma; raw SQL yok. Run'a FK yok — zaman penceresiyle eşlenir
(observer kalıbıyla aynı, `db_observers`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from packages.shared.enums import RawItemStatus
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ItemOutcome = Literal["processed", "filtered", "failed"]

_SNIPPET_MAX_CHARS = 280


@dataclass(slots=True)
class RunItem:
    """Run penceresindeki tek ham içerik + akıbeti."""

    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    title: str | None
    url: str | None
    snippet: str
    outcome: ItemOutcome
    content_category: str | None
    relevance_score: float | None
    fetched_at: datetime


@dataclass(slots=True)
class SourceBreakdown:
    """Kaynak bazlı okunan/işlenen/elenen/hata kırılımı."""

    source_id: uuid.UUID
    source_name: str
    collected: int
    processed: int
    filtered: int
    failed: int


@dataclass(slots=True)
class RunItemsResult:
    """Endpoint payload'u: özet sayaçlar + kaynak kırılımı + (filtreli) içerik listesi."""

    collected: int
    processed: int
    filtered: int
    failed: int
    by_source: list[SourceBreakdown]
    items: list[RunItem]
    total: int


def _snippet(raw_content: str | None) -> str:
    if not raw_content:
        return ""
    collapsed = " ".join(raw_content.split())
    if len(collapsed) <= _SNIPPET_MAX_CHARS:
        return collapsed
    return collapsed[:_SNIPPET_MAX_CHARS].rstrip() + "…"


class PipelineItemsRepository:
    """Run penceresindeki `raw_items` akıbet sınıflandırması (`Docs/04` §8.3)."""

    async def _processed_meta(
        self, db: AsyncSession, *, start: datetime, end: datetime
    ) -> dict[uuid.UUID, tuple[str | None, float]]:
        """Pencerede işlenen raw_item_id → (content_category, relevance_score)."""
        meta: dict[uuid.UUID, tuple[str | None, float]] = {}
        for model in PROCESSED_ITEM_MODELS.values():
            result = await db.execute(
                select(
                    model.raw_item_id,
                    model.content_category,
                    model.relevance_score,
                ).where(
                    model.processed_at >= start,
                    model.processed_at <= end,
                )
            )
            for raw_item_id, category, score in result.all():
                meta[raw_item_id] = (category, float(score))
        return meta

    async def get_run_items(
        self,
        db: AsyncSession,
        *,
        run: PipelineRun,
        outcome: ItemOutcome | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> RunItemsResult:
        if run.started_at is None:
            return RunItemsResult(
                collected=0,
                processed=0,
                filtered=0,
                failed=0,
                by_source=[],
                items=[],
                total=0,
            )

        start = run.started_at
        end = run.finished_at or datetime.now(UTC)

        processed_meta = await self._processed_meta(db, start=start, end=end)

        rows = await db.execute(
            select(RawItem, Source.name)
            .join(Source, Source.id == RawItem.source_id)
            .where(RawItem.fetched_at >= start, RawItem.fetched_at <= end)
            .order_by(RawItem.fetched_at.desc())
        )

        all_items: list[RunItem] = []
        breakdown: dict[uuid.UUID, SourceBreakdown] = {}
        collected = processed = filtered = failed = 0

        for raw, source_name in rows.all():
            if raw.status == RawItemStatus.FAILED:
                item_outcome: ItemOutcome = "failed"
            elif raw.id in processed_meta:
                item_outcome = "processed"
            else:
                item_outcome = "filtered"

            category, score = processed_meta.get(raw.id, (None, None))
            url = None
            if isinstance(raw.raw_metadata, dict):
                raw_url = raw.raw_metadata.get("url")
                url = str(raw_url) if isinstance(raw_url, str) and raw_url else None

            all_items.append(
                RunItem(
                    id=raw.id,
                    source_id=raw.source_id,
                    source_name=source_name,
                    title=raw.title,
                    url=url,
                    snippet=_snippet(raw.raw_content),
                    outcome=item_outcome,
                    content_category=category,
                    relevance_score=score,
                    fetched_at=raw.fetched_at,
                )
            )

            collected += 1
            agg = breakdown.get(raw.source_id)
            if agg is None:
                agg = SourceBreakdown(
                    source_id=raw.source_id,
                    source_name=source_name,
                    collected=0,
                    processed=0,
                    filtered=0,
                    failed=0,
                )
                breakdown[raw.source_id] = agg
            agg.collected += 1
            if item_outcome == "processed":
                processed += 1
                agg.processed += 1
            elif item_outcome == "failed":
                failed += 1
                agg.failed += 1
            else:
                filtered += 1
                agg.filtered += 1

        selected = (
            [item for item in all_items if item.outcome == outcome]
            if outcome is not None
            else all_items
        )
        total = len(selected)
        offset = (page - 1) * page_size
        page_items = selected[offset : offset + page_size]

        by_source = sorted(
            breakdown.values(), key=lambda b: b.collected, reverse=True
        )

        return RunItemsResult(
            collected=collected,
            processed=processed,
            filtered=filtered,
            failed=failed,
            by_source=by_source,
            items=page_items,
            total=total,
        )


pipeline_items_repository = PipelineItemsRepository()

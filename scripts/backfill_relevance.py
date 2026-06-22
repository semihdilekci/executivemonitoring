"""Mevcut processed_items kayıtlarının relevance_score'unu yeni formülle yeniden hesaplar.

Faz 3 scorer formülü değişti (`Docs/04` §8.4):
- Eski: `(eşleşen / master_havuz) × freq × 0.6 + freshness × 0.4` → keyword katkısı
  ~0.18'e eziliyordu; hiçbir haber %40'ı geçemiyordu.
- Yeni: saf keyword ilgisi `0.7 * coverage + 0.3 * freq` (freshness yok), kelime-sınırı eşleşme.

Bu script idempotenttir: `topics` + `clean_content`'ten keyword'leri yeni (kelime-sınırlı)
matcher ile yeniden türetir, `relevance_score` ve `topics`'i günceller. Tekrar çalıştırmak
aynı değerleri üretir. `--dry-run` ile sadece raporlar, yazmaz.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.core.config import get_settings  # noqa: E402
from packages.shared.env_loader import load_dotenv_file  # noqa: E402
from packages.shared.models.processed_item import (  # noqa: E402
    PROCESSED_ITEM_MODELS,
    ProcessedItem,
)
from services.processor.keyword_pool import (  # noqa: E402
    KeywordPools,
    build_pools,
    count_matches_by_category,
    find_matching_keywords,
)
from services.processor.keyword_repository import load_active_keywords  # noqa: E402
from services.processor.scorer import calculate_relevance_score  # noqa: E402

logger = logging.getLogger("ygip.backfill_relevance")

_SCORE_EPSILON = 1e-4


def _recompute(item: ProcessedItem, pools: KeywordPools) -> tuple[list[str], float]:
    """Title + clean_content'ten kelime-sınırlı keyword'leri ve yeni skoru üretir.

    `topics` master havuzdan türetilir (davranış değişmez); `relevance_score`
    ise yalnızca kalıcı `content_category`'ye ait eşleşen keyword'lerle
    rating-ağırlıklı hesaplanır (`Docs/04` §8.4 — K5). Kategori yoksa veya o
    kategoride eşleşme yoksa skor `0.0`.
    """
    title = item.title or ""
    content = item.clean_content or ""
    matched = find_matching_keywords(title, content, pools.master_pool)

    scored = []
    if item.content_category:
        by_category = count_matches_by_category(title, content, pools.category_pool)
        scored = by_category.get(item.content_category, [])
    score = calculate_relevance_score(content, scored)
    return matched, score


async def backfill_schema(
    session: AsyncSession,
    schema: str,
    model_cls: type[ProcessedItem],
    *,
    pools: KeywordPools,
    dry_run: bool,
) -> tuple[int, int]:
    """Tek schema tablosunu yeniden skorlar → (güncellenen, değişmeyen)."""
    rows = (await session.execute(select(model_cls))).scalars().all()
    updated = 0
    unchanged = 0
    for item in rows:
        matched, new_score = _recompute(item, pools)
        score_changed = abs(float(item.relevance_score) - new_score) > _SCORE_EPSILON
        topics_changed = list(item.topics or []) != matched
        if not score_changed and not topics_changed:
            unchanged += 1
            continue
        logger.info(
            "backfill_rescore",
            extra={
                "schema": schema,
                "processed_item_id": str(item.id),
                "old_score": round(float(item.relevance_score), 4),
                "new_score": new_score,
                "matched_count": len(matched),
            },
        )
        if not dry_run:
            item.relevance_score = new_score
            item.topics = matched
        updated += 1
    return updated, unchanged


async def run_backfill(session: AsyncSession, *, dry_run: bool) -> dict[str, tuple[int, int]]:
    """Aktif keyword havuzunu DB'den yükler, tüm schema tablolarını yeniden skorlar."""
    pools = build_pools(await load_active_keywords(session))
    summary: dict[str, tuple[int, int]] = {}
    for schema, model_cls in PROCESSED_ITEM_MODELS.items():
        summary[schema] = await backfill_schema(
            session, schema, model_cls, pools=pools, dry_run=dry_run
        )
    return summary


async def _run_cli(*, database_url: str | None, dry_run: bool) -> dict[str, tuple[int, int]]:
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            summary = await run_backfill(session, dry_run=dry_run)
            if dry_run:
                await session.rollback()
            else:
                await session.commit()
            return summary
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    load_dotenv_file(override=False)
    parser = argparse.ArgumentParser(
        description="processed_items.relevance_score yeniden hesaplama (idempotent)"
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Yazma yapmadan sadece raporla",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        summary = asyncio.run(_run_cli(database_url=args.database_url, dry_run=args.dry_run))
    except Exception:
        logger.exception("backfill_failed")
        return 1

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    total_updated = sum(u for u, _ in summary.values())
    total_unchanged = sum(c for _, c in summary.values())
    for schema, (updated, unchanged) in summary.items():
        print(f"{schema}: {updated} güncellendi, {unchanged} değişmedi")
    print(f"[{mode}] toplam: {total_updated} güncellendi, {total_unchanged} değişmedi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

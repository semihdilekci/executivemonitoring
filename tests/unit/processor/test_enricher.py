"""EnricherProcessor unit testleri — kategori, schema routing, topics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from services.processor.enricher import EnricherProcessor
from services.processor.keyword_pool import resolve_content_category, resolve_schema_category
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput

_FILLER = (
    "Piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor "
    "çünkü küresel ekonomide belirsizlik devam ediyor."
)


def _ctx(**overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Haber",
        "content": _FILLER,
        "content_hash": "sha256:abc",
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    return ProcessorContext(input=item, data=ProcessorOutput.from_input(item))


def _with_config(
    ctx: ProcessorContext,
    ingest_mode: str,
    default_category: str,
) -> ProcessorContext:
    ctx.data.extras["source_config"] = {
        "ingest_mode": ingest_mode,
        "default_category": default_category,
    }
    return ctx


@pytest.mark.asyncio
async def test_enricher_finance_keywords_routes_to_market_schema() -> None:
    processor = EnricherProcessor()
    ctx = _with_config(
        _ctx(title="BIST hisse analizi", content=f"Borsa ve tahvil piyasası {_FILLER}"),
        "filtered",
        "macro",
    )

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["category"] == "finance"
    assert result.extras["schema_category"] == "market"
    assert "borsa" in result.extras["topics"] or "hisse" in result.extras["topics"]


@pytest.mark.asyncio
async def test_enricher_ingest_mode_all_uses_default_category() -> None:
    processor = EnricherProcessor()
    ctx = _with_config(
        _ctx(title="TCMB faiz kararı", content=f"Merkez bankası enflasyon {_FILLER}"),
        "all",
        "fmcg",
    )

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["category"] == "fmcg"
    assert result.extras["schema_category"] == "fmcg"


@pytest.mark.asyncio
async def test_enricher_tie_break_uses_default_category() -> None:
    tie_content = f"tcmb faiz borsa hisse {_FILLER}"
    category, _ = resolve_content_category(
        "Haber",
        tie_content,
        ingest_mode="filtered",
        default_category="finance",
    )

    assert category == "finance"


@pytest.mark.asyncio
async def test_enricher_topics_deduped_and_entities_empty() -> None:
    processor = EnricherProcessor()
    ctx = _with_config(
        _ctx(
            title="Faiz faiz",
            content=f"Faiz kararı faiz oranı enflasyon büyüme {_FILLER}",
        ),
        "filtered",
        "macro",
    )

    result = await processor.process(ctx)

    assert result is not None
    topics = result.extras["topics"]
    assert isinstance(topics, list)
    assert len(topics) == len(set(topics))
    assert result.extras["entities"] == []


def test_schema_routing_macro_to_news() -> None:
    assert resolve_schema_category("macro") == "news"
    assert resolve_schema_category("strategy") == "news"
    assert resolve_schema_category("regulatory") == "news"


def test_schema_routing_geopolitical_to_geo() -> None:
    assert resolve_schema_category("geopolitical") == "geo"


def test_schema_routing_transport_falls_back_to_news() -> None:
    """MVP-0'da transport schema routing kullanılmaz."""
    assert resolve_schema_category("transport") == "news"

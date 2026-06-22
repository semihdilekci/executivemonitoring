"""GateProcessor unit testleri — ingest_mode, master keyword (DB havuz), NFC."""

from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime

import pytest
from services.processor.gate_processor import (
    GateProcessor,
    StaticSourceConfigResolver,
)
from services.processor.keyword_pool import (
    KeywordPoolProvider,
    KeywordRecord,
    build_pools,
    find_matching_keywords,
    has_master_match,
    static_keyword_pool_provider,
)
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput

_LONG_CONTENT = (
    "Piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor "
    "çünkü küresel ekonomide belirsizlik devam ediyor."
)


def _keyword_records() -> list[KeywordRecord]:
    """Gate testleri için temsili aktif keyword havuzu (tr/en + rating)."""
    return [
        KeywordRecord("tcmb", "central bank of turkey", {"macro": 8}),
        KeywordRecord("faiz", "interest rate", {"macro": 8, "finance": 7}),
        KeywordRecord("enflasyon", "inflation", {"macro": 9, "finance": 6}),
        KeywordRecord("merkez bankası", "central bank", {"macro": 9}),
        KeywordRecord("borsa", "stock market", {"finance": 8}),
        KeywordRecord("hisse", "share", {"finance": 7}),
    ]


def _provider() -> KeywordPoolProvider:
    return static_keyword_pool_provider(_keyword_records())


def _master_pool() -> tuple[str, ...]:
    return build_pools(_keyword_records()).master_pool


def _sample_context(**overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Genel ekonomi haberi",
        "content": _LONG_CONTENT,
        "content_hash": "sha256:abc",
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)
    return ProcessorContext(input=item, data=ProcessorOutput.from_input(item))


def _ctx_with_config(ingest_mode: str, **overrides: object) -> ProcessorContext:
    ctx = _sample_context(**overrides)
    ctx.data.extras["source_config"] = {
        "ingest_mode": ingest_mode,
        "default_category": "finance",
    }
    return ctx


@pytest.mark.asyncio
async def test_gate_ingest_mode_all_passes_without_keyword() -> None:
    processor = GateProcessor(keyword_pool_provider=_provider())
    ctx = _ctx_with_config("all")

    result = await processor.process(ctx)

    assert result is ctx.data


@pytest.mark.asyncio
async def test_gate_filtered_with_keyword_match_passes() -> None:
    processor = GateProcessor(keyword_pool_provider=_provider())
    ctx = _ctx_with_config(
        "filtered",
        title="TCMB faiz kararı",
        content=_LONG_CONTENT,
    )

    result = await processor.process(ctx)

    assert result is ctx.data


@pytest.mark.asyncio
async def test_gate_filtered_english_surface_match_passes() -> None:
    """İngilizce yüzey (`inflation`) de master havuzda eşleşir."""
    processor = GateProcessor(keyword_pool_provider=_provider())
    ctx = _ctx_with_config(
        "filtered",
        title="Markets watch inflation data",
        content="Investors monitor the latest inflation report this week closely.",
    )

    result = await processor.process(ctx)

    assert result is ctx.data


@pytest.mark.asyncio
async def test_gate_filtered_no_match_drops() -> None:
    processor = GateProcessor(keyword_pool_provider=_provider())
    ctx = _ctx_with_config("filtered")

    result = await processor.process(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_gate_turkish_nfc_keyword_match() -> None:
    processor = GateProcessor(keyword_pool_provider=_provider())
    nfc_keyword = "enflasyon"
    decomposed = unicodedata.normalize("NFD", nfc_keyword)
    content = (
        f"{decomposed} beklentileri yükselirken piyasa analistleri bu hafta "
        "sonu gelişmeleri yakından izliyor ve yatırımcılar farklı senaryolar "
        "üzerinde değerlendirme yapıyor çünkü küresel ekonomide belirsizlik devam ediyor."
    )
    ctx = _ctx_with_config("filtered", content=content)

    result = await processor.process(ctx)

    assert result is ctx.data
    assert has_master_match(ctx.data.title, content, _master_pool())


@pytest.mark.asyncio
async def test_gate_uses_static_config_resolver() -> None:
    source_id = uuid.uuid4()
    resolver = StaticSourceConfigResolver(
        configs={source_id: {"ingest_mode": "all", "default_category": "fmcg"}},
    )
    processor = GateProcessor(
        source_config_resolver=resolver,
        keyword_pool_provider=_provider(),
    )
    ctx = _sample_context(source_id=source_id)

    result = await processor.process(ctx)

    assert result is ctx.data


@pytest.mark.asyncio
async def test_gate_invalid_ingest_mode_treated_as_filtered() -> None:
    processor = GateProcessor(keyword_pool_provider=_provider())
    ctx = _ctx_with_config("invalid_mode")

    result = await processor.process(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_gate_without_provider_drops_filtered() -> None:
    """Provider yoksa master havuz boş → filtered kaynak DROP (güvenli varsayılan)."""
    processor = GateProcessor()
    ctx = _ctx_with_config("filtered", title="TCMB faiz kararı")

    result = await processor.process(ctx)

    assert result is None


def test_master_pool_not_empty() -> None:
    assert len(_master_pool()) > 0


def test_master_pool_dedupes_and_unions_tr_en() -> None:
    pool = _master_pool()
    assert "merkez bankası" in pool
    assert "central bank" in pool
    # tr + en yüzeyleri ayrı ayrı havuzda
    assert "inflation" in pool
    assert "enflasyon" in pool


def test_find_matching_keywords_long_phrase_first() -> None:
    matched = find_matching_keywords(
        "Merkez Bankası açıklaması",
        "Ekonomi haberleri devam ediyor merkez bankası politikası.",
        _master_pool(),
    )
    assert "merkez bankası" in matched


def test_find_matching_keywords_empty_pool_returns_empty() -> None:
    assert not find_matching_keywords("başlık", "içerik metni", ())

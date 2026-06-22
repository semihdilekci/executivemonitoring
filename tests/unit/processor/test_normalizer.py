"""NormalizerProcessor unit testleri — HTML, Unicode, dil, min length."""

from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput
from services.processor.normalizer import (
    MIN_WORD_COUNT,
    NormalizerProcessor,
    collapse_whitespace,
    detect_language,
    normalize_published_at,
    normalize_text,
    unescape_entities,
    word_count,
)

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")

_LONG_TR_CONTENT = (
    "İstanbul merkez bankası faiz kararını açıkladı ve piyasalar "
    "bu gelişmeyi yakından takip ediyor çünkü enflasyon beklentileri "
    "önemli ölçüde değişebilir."
)


def _sample_context(**overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "TCMB Faiz Kararı",
        "content": _LONG_TR_CONTENT,
        "content_hash": "sha256:abc",
        "published_at": datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    return ProcessorContext(input=item, data=ProcessorOutput.from_input(item))


@pytest.mark.asyncio
async def test_normalizer_strips_html_and_collapses_whitespace() -> None:
    processor = NormalizerProcessor()
    html_content = (
        "<p>İstanbul</p>   <div>merkez bankası faiz kararını açıkladı ve "
        "piyasalar bu gelişmeyi yakından takip ediyor çünkü enflasyon "
        "beklentileri önemli ölçüde değişebilir.</div>"
    )
    ctx = _sample_context(content=html_content, title="<b>  Başlık  </b>")

    result = await processor.process(ctx)

    assert result is not None
    assert "<" not in result.content
    assert result.title == "Başlık"
    assert "  " not in result.content
    assert result.extras["clean_content"] == result.content


@pytest.mark.asyncio
async def test_normalizer_unicode_nfc_turkish() -> None:
    processor = NormalizerProcessor()
    nfc_word = "ışığın"
    decomposed = unicodedata.normalize("NFD", nfc_word)
    assert decomposed != nfc_word
    content = (
        f"{decomposed} enerjisi {decomposed} enerjisi İstanbul şehir merkezinde "
        "görülmesi beklenen önemli bir gelişme olarak değerlendiriliyor."
    )
    ctx = _sample_context(content=content, title=f"İstanbul ve {decomposed}")

    result = await processor.process(ctx)

    assert result is not None
    assert unicodedata.is_normalized("NFC", result.content)
    assert nfc_word in result.content


@pytest.mark.asyncio
async def test_normalizer_detects_turkish_language() -> None:
    processor = NormalizerProcessor()
    ctx = _sample_context()

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["language"] == "tr"


@pytest.mark.asyncio
async def test_normalizer_short_content_skips() -> None:
    processor = NormalizerProcessor()
    short = "bir iki üç dört beş altı yedi sekiz dokuz"
    assert word_count(short) == 9
    ctx = _sample_context(content=short)

    result = await processor.process(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_normalizer_passes_at_min_word_count() -> None:
    processor = NormalizerProcessor()
    exact = "bir iki üç dört beş altı yedi sekiz dokuz on"
    assert word_count(exact) == MIN_WORD_COUNT
    ctx = _sample_context(content=exact)

    result = await processor.process(ctx)

    assert result is not None
    assert result.content == exact


@pytest.mark.asyncio
async def test_normalizer_published_at_to_istanbul() -> None:
    processor = NormalizerProcessor()
    utc_dt = datetime(2026, 6, 17, 9, 30, tzinfo=UTC)
    ctx = _sample_context(published_at=utc_dt)

    result = await processor.process(ctx)

    assert result is not None
    assert result.published_at is not None
    assert result.published_at.tzinfo == ISTANBUL_TZ
    assert result.published_at.hour == 12
    assert result.published_at.minute == 30


@pytest.mark.asyncio
async def test_normalizer_malformed_date_fallback_none() -> None:
    processor = NormalizerProcessor()
    ctx = _sample_context(published_at=None)

    result = await processor.process(ctx)

    assert result is not None
    assert result.published_at is None


@pytest.mark.asyncio
async def test_normalizer_naive_datetime_assumes_utc() -> None:
    naive = datetime(2026, 1, 1, 0, 0)
    normalized = normalize_published_at(naive)

    assert normalized is not None
    assert normalized.tzinfo == ISTANBUL_TZ
    assert normalized.hour == 3


def test_strip_html_malformed_graceful() -> None:
    raw = "<p>metin<p>devam <span>açık"
    assert normalize_text(raw) == "metin devam açık"


def test_unescape_double_encoded_entities() -> None:
    raw = "TÜİK&amp;#039;ten gelecek veri &amp;quot;zam&amp;quot; bekleniyor."
    assert unescape_entities(raw) == 'TÜİK\'ten gelecek veri "zam" bekleniyor.'


def test_unescape_single_encoded_entities() -> None:
    assert unescape_entities("emekli &#039;maaş&#039; &quot;zam&quot;") == ("emekli 'maaş' \"zam\"")


def test_normalize_text_decodes_double_encoded_entities() -> None:
    raw = "Milyonlar TÜİK&amp;#039;ten gelecek veriyi &amp;quot;zam&amp;quot; diye bekliyor."
    assert normalize_text(raw) == ('Milyonlar TÜİK\'ten gelecek veriyi "zam" diye bekliyor.')


def test_normalize_text_decodes_entities_inside_html() -> None:
    raw = "<p>TÜİK&amp;#039;ten &amp;quot;veri&amp;quot;</p>"
    assert normalize_text(raw) == 'TÜİK\'ten "veri"'


def test_collapse_whitespace() -> None:
    assert collapse_whitespace("  foo \n\n bar  ") == "foo bar"


def test_detect_language_english() -> None:
    text = (
        "The central bank announced its interest rate decision and markets "
        "are closely watching this development because inflation expectations "
        "may change significantly in the coming weeks."
    )
    assert detect_language(text) == "en"

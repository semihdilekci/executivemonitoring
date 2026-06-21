"""Normalizer processor — HTML strip, Unicode NFC, dil/tarih (`Docs/04` §8.2)."""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from langdetect import DetectorFactory, LangDetectException, detect

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.normalizer")

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
MIN_WORD_COUNT = 10
_WHITESPACE_RE = re.compile(r"\s+")
_UNDEFINED_LANGUAGE = "und"
_MAX_UNESCAPE_PASSES = 3

DetectorFactory.seed = 0


def unescape_entities(text: str) -> str:
    """Çift kodlanmış HTML entity'leri çözer (`&amp;#039;` → `'`, `&amp;quot;` → `\"`).

    Kaynak feed'ler bazen tek kodlanmış entity'yi (`&#039;`) tekrar escape eder
    (`&amp;#039;`). Stabil hale gelene kadar (en fazla birkaç tur) tekrarlı çözer.
    """
    if not text:
        return text
    for _ in range(_MAX_UNESCAPE_PASSES):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def strip_html(text: str) -> str:
    """HTML etiketlerini kaldırır; malformed HTML graceful strip."""
    if not text or "<" not in text:
        return text
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ")


def normalize_unicode(text: str) -> str:
    """Unicode NFC normalizasyonu — Türkçe karakter koruması."""
    return unicodedata.normalize("NFC", text)


def collapse_whitespace(text: str) -> str:
    """Çoklu boşluk ve satır sonlarını tek boşluğa indirger."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_text(text: str) -> str:
    """HTML strip → entity decode → NFC → whitespace düzenleme."""
    return collapse_whitespace(
        normalize_unicode(unescape_entities(strip_html(text)))
    )


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def detect_language(text: str) -> str:
    """ISO 639-1 dil kodu; algılanamazsa `und`."""
    try:
        return str(detect(text))
    except LangDetectException:
        return _UNDEFINED_LANGUAGE


def normalize_published_at(value: datetime | None) -> datetime | None:
    """Tarihi Europe/Istanbul timezone-aware datetime'a çevirir."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ISTANBUL_TZ)


class NormalizerProcessor(BaseProcessor):
    """Metin temizleme, dil algılama ve min length filtresi."""

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        data = ctx.data

        normalized_title = normalize_text(data.title)
        normalized_content = normalize_text(data.content)
        words = word_count(normalized_content)

        if words < MIN_WORD_COUNT:
            logger.info(
                "processor_normalize_short_content",
                extra={
                    "source_id": str(data.source_id),
                    "word_count": words,
                    "min_words": MIN_WORD_COUNT,
                },
            )
            return None

        language = detect_language(normalized_content)
        published_at = normalize_published_at(data.published_at)

        data.title = normalized_title
        data.content = normalized_content
        data.published_at = published_at
        data.extras["clean_content"] = normalized_content
        data.extras["language"] = language

        logger.debug(
            "processor_normalize_success",
            extra={
                "source_id": str(data.source_id),
                "language": language,
                "word_count": words,
            },
        )
        return data

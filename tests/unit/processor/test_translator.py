"""TranslationProcessor unit testleri — gate koşulu, çeviri, hata=passthrough (`Docs/04` §8.45)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from packages.shared.enums import LlmRequestType
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput
from services.processor.translator import TranslationProcessor, parse_translation_response

_TR_JSON = '{"title": "Türkçe Başlık", "content": "Türkçe çevrilmiş metin gövdesi."}'


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeLLMClient:
    """`complete` çağrılarını kaydeden sahte LLM client."""

    def __init__(self, *, text: str | None = None, error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        operation_type: object = None,
    ) -> _FakeResponse:
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "operation_type": operation_type,
            }
        )
        if self._error is not None:
            raise self._error
        assert self._text is not None
        return _FakeResponse(self._text)


def _context(
    *,
    language: str,
    score: float,
    title: str = "Original Title",
    content: str = "Original English body.",
    clean_content: str | None = "Original English body.",
) -> ProcessorContext:
    item = ProcessorInput(
        source_id=uuid.uuid4(),
        source_type="rss",
        title=title,
        content=content,
        content_hash="sha256:translatortest",
        published_at=datetime.now(UTC),
        raw_metadata={},
    )
    data = ProcessorOutput.from_input(item)
    data.extras["language"] = language
    data.extras["relevance_score"] = score
    if clean_content is not None:
        data.extras["clean_content"] = clean_content
    return ProcessorContext(input=item, data=data)


@pytest.mark.asyncio
async def test_translates_english_above_threshold() -> None:
    client = _FakeLLMClient(text=_TR_JSON)
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="en", score=0.80)

    result = await processor.process(ctx)

    assert result is not None
    assert result.title == "Türkçe Başlık"
    assert result.content == "Türkçe çevrilmiş metin gövdesi."
    assert result.extras["clean_content"] == "Türkçe çevrilmiş metin gövdesi."
    assert result.extras["language"] == "tr"
    assert result.extras["original_translation"] == {
        "language": "en",
        "title": "Original Title",
        "content": "Original English body.",
    }
    assert len(client.calls) == 1
    assert client.calls[0]["operation_type"] is LlmRequestType.ARTICLE_TRANSLATION


@pytest.mark.asyncio
async def test_english_below_threshold_is_noop() -> None:
    client = _FakeLLMClient(text=_TR_JSON)
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="en", score=0.50)

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["language"] == "en"
    assert "original_translation" not in result.extras
    assert client.calls == []


@pytest.mark.asyncio
async def test_non_english_is_noop() -> None:
    client = _FakeLLMClient(text=_TR_JSON)
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="tr", score=0.95, title="Türkçe", content="Türkçe metin.")

    result = await processor.process(ctx)

    assert result is not None
    assert result.title == "Türkçe"
    assert result.extras["language"] == "tr"
    assert "original_translation" not in result.extras
    assert client.calls == []


@pytest.mark.asyncio
async def test_llm_error_passthrough_keeps_english() -> None:
    client = _FakeLLMClient(error=RuntimeError("provider down"))
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="en", score=0.90)

    result = await processor.process(ctx)

    assert result is not None
    assert result.title == "Original Title"
    assert result.content == "Original English body."
    assert result.extras["language"] == "en"
    assert "original_translation" not in result.extras


@pytest.mark.asyncio
async def test_unparseable_output_passthrough() -> None:
    client = _FakeLLMClient(text="Bu geçerli bir JSON değil.")
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="en", score=0.90)

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["language"] == "en"
    assert "original_translation" not in result.extras


@pytest.mark.asyncio
async def test_no_client_is_noop() -> None:
    processor = TranslationProcessor(llm_client=None, min_relevance_score=75)
    ctx = _context(language="en", score=0.90)

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["language"] == "en"
    assert "original_translation" not in result.extras


@pytest.mark.asyncio
async def test_safe_process_never_raises_on_translation_error() -> None:
    """Çeviri hatası `ProcessorStepError`'a yükseltilmez — haber DLQ'ya düşmez."""
    client = _FakeLLMClient(error=RuntimeError("boom"))
    processor = TranslationProcessor(llm_client=client, min_relevance_score=75)
    ctx = _context(language="en", score=0.90)

    result = await processor.safe_process(ctx)

    assert result is not None
    assert result.extras["language"] == "en"


def test_parse_translation_response_variants() -> None:
    assert parse_translation_response(_TR_JSON) == (
        "Türkçe Başlık",
        "Türkçe çevrilmiş metin gövdesi.",
    )
    # Markdown kod bloğu içinde JSON
    fenced = f"```json\n{_TR_JSON}\n```"
    assert parse_translation_response(fenced) == (
        "Türkçe Başlık",
        "Türkçe çevrilmiş metin gövdesi.",
    )
    # Eksik/boş alanlar → None
    assert parse_translation_response('{"title": "X"}') is None
    assert parse_translation_response('{"title": "", "content": "y"}') is None
    assert parse_translation_response('{"title": "x", "content": "  "}') is None
    assert parse_translation_response("tamamen serbest metin") is None
    assert parse_translation_response("") is None

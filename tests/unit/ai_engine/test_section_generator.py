"""SectionGenerator unit testleri — bölüm özeti + Yıldız etki + kaynak referansları."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

import pytest
from packages.shared.enums import ApiProvider
from services.ai_engine.digest_models import DigestArticle
from services.ai_engine.exceptions import DigestParseError
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.section_generator import (
    SectionGenerator,
    build_section_prompt,
    build_source_references,
    parse_section_response,
)

from tests.unit.ai_engine.test_llm_client import MockProvider


@dataclass
class _FakeSection:
    id: uuid.UUID
    name: str = "Piyasa Genel Görünümü"
    sort_order: int = 0
    section_system_prompt: str = "Sen {section_name} bölümünü yazan bir analistsin."
    section_user_prompt: str = (
        "Bülten: {newsletter_name}\nDönem: {date_range}\nHaberler:\n{articles}"
    )
    impact_prompt: str = "{section_name} bölümünün Yıldız etkisini değerlendir."


def _article(item_id: uuid.UUID | None = None, *, title: str = "Haber") -> DigestArticle:
    return DigestArticle(
        processed_item_id=item_id or uuid.uuid4(),
        source_id=uuid.uuid4(),
        title=title,
        clean_content="Örnek makale gövdesi { süslü } parantez içerir.",
        relevance_score=0.8,
        published_at=None,
        url="https://example.com/1",
        topics=["fmcg"],
    )


def _llm_client(text: str) -> LLMClient:
    provider = MockProvider(
        provider=ApiProvider.GROQ,
        returns=LLMResponse(
            text=text,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/test",
            latency_ms=10,
        ),
    )
    return LLMClient(providers=[provider])


@pytest.mark.asyncio
async def test_generate_section_builds_summary_impact_and_references() -> None:
    art1, art2 = _article(title="Haber A"), _article(title="Haber B")
    response = json.dumps(
        {
            "ai_summary": "FMCG piyasasında bu hafta hareketlilik arttı.",
            "impact_note": "Yıldız Holding için olumlu sinyaller.",
        }
    )
    generator = SectionGenerator(llm_client=_llm_client(response))

    result = await generator.generate_section(
        section=_FakeSection(id=uuid.uuid4()),
        newsletter_name="FMCG Haftalık",
        articles=[art1, art2],
        date_range="2026-06-09 — 2026-06-15",
    )

    assert result.ai_summary == "FMCG piyasasında bu hafta hareketlilik arttı."
    assert result.impact_note == "Yıldız Holding için olumlu sinyaller."
    assert result.section_title == "Piyasa Genel Görünümü"
    assert [ref.processed_item_id for ref in result.source_references] == [
        art1.processed_item_id,
        art2.processed_item_id,
    ]


@pytest.mark.asyncio
async def test_generate_section_sets_newsletter_section_provenance() -> None:
    section_id = uuid.uuid4()
    generator = SectionGenerator(
        llm_client=_llm_client('{"ai_summary": "özet", "impact_note": "etki"}')
    )

    result = await generator.generate_section(
        section=_FakeSection(id=section_id),
        newsletter_name="FMCG Haftalık",
        articles=[_article()],
        date_range="2026-06-09 — 2026-06-15",
    )

    assert result.newsletter_section_id == section_id


@pytest.mark.asyncio
async def test_generate_section_plain_text_becomes_summary_without_impact() -> None:
    generator = SectionGenerator(llm_client=_llm_client("Düz metin bölüm özeti."))

    result = await generator.generate_section(
        section=_FakeSection(id=uuid.uuid4()),
        newsletter_name="FMCG Haftalık",
        articles=[_article()],
        date_range="2026-06-09 — 2026-06-15",
    )

    assert result.ai_summary == "Düz metin bölüm özeti."
    assert result.impact_note is None


@pytest.mark.asyncio
async def test_generate_section_empty_response_raises_parse_error() -> None:
    generator = SectionGenerator(llm_client=_llm_client("   "))

    with pytest.raises(DigestParseError):
        await generator.generate_section(
            section=_FakeSection(id=uuid.uuid4()),
            newsletter_name="FMCG Haftalık",
            articles=[_article()],
            date_range="2026-06-09 — 2026-06-15",
        )


def test_parse_section_response_from_code_fence() -> None:
    raw = '```json\n{"ai_summary": "özet", "impact_note": "etki"}\n```'
    summary, impact = parse_section_response(raw)

    assert summary == "özet"
    assert impact == "etki"


def test_build_section_prompt_embeds_impact_instruction() -> None:
    prompt = build_section_prompt("Haberleri özetle.", "Yıldız etkisini yaz.")

    assert "Haberleri özetle." in prompt
    assert "Yıldız etkisini yaz." in prompt
    assert "ai_summary" in prompt
    assert "impact_note" in prompt


def test_build_source_references_keeps_article_order_and_urls() -> None:
    art1, art2 = _article(title="A"), _article(title="B")
    refs = build_source_references([art1, art2])

    assert len(refs) == 2
    assert refs[0].title == "A"
    assert refs[0].url == "https://example.com/1"
    assert refs[1].processed_item_id == art2.processed_item_id

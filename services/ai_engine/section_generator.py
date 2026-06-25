"""Bölüm LLM aşaması — atanan haberlerden özet + Yıldız etki notu (Faz 6.5).

ADR-0003 / `Docs/04` §9.2 Aşama 2: editörün bir bülten bölümüne atadığı
haberler alınır; `section_system_prompt` + `section_user_prompt` + `impact_prompt`
render edilip tek LLM çağrısıyla `{ai_summary, impact_note}` üretilir.
`source_references` LLM'e bırakılmaz — atanan haberlerden deterministik kurulur.

Prompt değişkenleri tek-süslü `{degisken}` biçimindedir (`Docs/03` §5); editör
aşamasıyla aynı güvenli hedefli ikame (`render_prompt`) kullanılır — makale
içeriğindeki serbest `{`/`}` karakterleri bozulmaz.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any, Protocol

from packages.shared.enums import LlmRequestType

from services.ai_engine.digest_models import (
    DigestArticle,
    ParsedDigestSection,
    SourceReference,
)
from services.ai_engine.editor_selector import (
    SectionLike,
    format_articles_for_prompt,
    render_prompt,
)
from services.ai_engine.exceptions import DigestParseError
from services.ai_engine.llm_client import LLMClient

logger = logging.getLogger("ygip.ai_engine.section_generator")

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL | re.IGNORECASE)


class GeneratableSection(SectionLike, Protocol):
    """`section_generator`'ın bölümden ihtiyaç duyduğu minimum arayüz.

    `SectionLike`'ı (name, sort_order) genişletir; element alt-tipliği sayesinde
    `Sequence[GeneratableSection]`, editör `Sequence[SectionLike]` beklediği yerde
    geçerlidir.
    """

    id: uuid.UUID
    section_system_prompt: str
    section_user_prompt: str
    impact_prompt: str


class SectionGenerator:
    """Bülten bölümü başına LLM çağrısı — özet + Yıldız etki notu."""

    def __init__(self, *, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def generate_section(
        self,
        *,
        section: GeneratableSection,
        newsletter_name: str,
        articles: Sequence[DigestArticle],
        date_range: str,
    ) -> ParsedDigestSection:
        """Atanan haberlerden bölüm özeti + Yıldız etki notu üretir."""
        context = {
            "section_name": section.name,
            "newsletter_name": newsletter_name,
            "date_range": date_range,
            "articles": format_articles_for_prompt(articles),
        }
        system_prompt = render_prompt(section.section_system_prompt, context)
        user_prompt = render_prompt(section.section_user_prompt, context)
        impact_instruction = render_prompt(section.impact_prompt, context)

        full_prompt = build_section_prompt(user_prompt, impact_instruction)
        response = await self._llm_client.complete(
            full_prompt,
            system_prompt=system_prompt,
            operation_type=LlmRequestType.DIGEST_GENERATION,
        )

        ai_summary, impact_note = parse_section_response(response.text)
        return ParsedDigestSection(
            section_title=section.name,
            ai_summary=ai_summary,
            impact_note=impact_note,
            source_references=build_source_references(articles),
            newsletter_section_id=section.id,
        )


def build_section_prompt(user_prompt: str, impact_instruction: str) -> str:
    """Bölüm özeti + Yıldız etki notunu tek JSON çağrısında isteyen prompt."""
    return (
        f"{user_prompt}\n\n"
        "---\n"
        "Ayrıca, aşağıdaki talimata göre bir Yıldız Holding etki notu üret:\n"
        f"{impact_instruction}\n\n"
        "Yanıtını yalnızca şu JSON formatında ver:\n"
        '{"ai_summary": "<bölüm özeti>", "impact_note": "<Yıldız etki notu>"}'
    )


def build_source_references(
    articles: Sequence[DigestArticle],
) -> list[SourceReference]:
    """Atanan haberlerden kaynak referansları (id + başlık + url)."""
    return [
        SourceReference(
            processed_item_id=article.processed_item_id,
            title=article.title,
            url=article.url,
        )
        for article in articles
    ]


def parse_section_response(raw_text: str) -> tuple[str, str | None]:
    """Bölüm LLM çıktısını `(ai_summary, impact_note)` olarak parse eder.

    JSON `{ai_summary, impact_note}` tercih edilir; düz metin gelirse tüm metin
    özet kabul edilir (etki notu yok). Boş yanıt parse hatasıdır.
    """
    text = raw_text.strip()
    if not text:
        raise DigestParseError("Bölüm LLM yanıtı boş.")

    payload = _extract_json_object(text)
    if payload is not None:
        ai_summary = _coerce_str(payload.get("ai_summary") or payload.get("summary"))
        impact_note = _coerce_optional_str(payload.get("impact_note") or payload.get("impact"))
        if ai_summary:
            return ai_summary, impact_note
        logger.warning("section_response_missing_summary_fallback_to_text")

    return text, None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    candidates: list[str] = []
    block = _JSON_BLOCK_RE.search(text)
    if block:
        candidates.append(block.group(1))
    candidates.append(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_str(value: Any) -> str | None:
    text = _coerce_str(value)
    return text or None

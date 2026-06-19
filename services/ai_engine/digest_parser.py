"""LLM digest çıktısı parser — JSON öncelikli, regex fallback."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from services.ai_engine.digest_models import DigestArticle, ParsedDigestSection, SourceReference
from services.ai_engine.exceptions import DigestParseError

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(
    r"^#{1,3}\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_IMPACT_RE = re.compile(
    r"(?:Etki\s*Notu|Impact\s*Note)\s*:\s*(?P<impact>.+)",
    re.IGNORECASE | re.DOTALL,
)


def parse_llm_sections(
    raw_text: str,
    *,
    section_key: str | None = None,
    articles: list[DigestArticle] | None = None,
) -> list[ParsedDigestSection]:
    """LLM yanıtını bölüm listesine parse eder."""
    text = raw_text.strip()
    if not text:
        raise DigestParseError("LLM yanıtı boş.")

    parsed = _try_parse_json(text)
    if parsed is not None:
        return _normalize_sections(parsed, section_key=section_key, articles=articles)

    fallback = _regex_fallback(text, section_key=section_key, articles=articles)
    if fallback:
        return fallback

    raise DigestParseError("LLM yanıtı tanınan formatta değil.")


def _try_parse_json(text: str) -> list[dict[str, Any]] | None:
    candidates = [text]
    block_match = _JSON_BLOCK_RE.search(text)
    if block_match:
        candidates.insert(0, block_match.group(1))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        sections = _extract_section_dicts(payload)
        if sections:
            return sections
    return None


def _extract_section_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    sections = payload.get("sections")
    if isinstance(sections, list):
        return [item for item in sections if isinstance(item, dict)]

    if any(key in payload for key in ("section_title", "ai_summary", "summary", "title")):
        return [payload]
    return []


def _normalize_sections(
    section_dicts: list[dict[str, Any]],
    *,
    section_key: str | None,
    articles: list[DigestArticle] | None,
) -> list[ParsedDigestSection]:
    normalized: list[ParsedDigestSection] = []
    for item in section_dicts:
        section = _dict_to_section(item, section_key=section_key, articles=articles)
        normalized.append(section)
    return normalized


def _dict_to_section(
    data: dict[str, Any],
    *,
    section_key: str | None,
    articles: list[DigestArticle] | None,
) -> ParsedDigestSection:
    title = _coerce_str(data.get("section_title") or data.get("title"))
    summary = _coerce_str(data.get("ai_summary") or data.get("summary") or data.get("content"))
    impact = _coerce_optional_str(data.get("impact_note") or data.get("impact"))

    if not title or not summary:
        raise DigestParseError("Bölüm başlığı veya özeti eksik.")

    refs = _parse_source_references(data.get("source_references"), articles=articles)
    resolved_key = section_key or _coerce_optional_str(data.get("section_key"))

    return ParsedDigestSection(
        section_title=title,
        ai_summary=summary,
        impact_note=impact,
        source_references=refs,
        section_key=resolved_key,
    )


def _parse_source_references(
    raw: Any,
    *,
    articles: list[DigestArticle] | None,
) -> list[SourceReference]:
    refs: list[SourceReference] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            ref = _reference_from_dict(item)
            if ref is not None:
                refs.append(ref)

    if refs:
        return refs
    return _default_references(articles)


def _reference_from_dict(data: dict[str, Any]) -> SourceReference | None:
    item_id_raw = data.get("processed_item_id") or data.get("id")
    title = _coerce_str(data.get("title"))
    if not item_id_raw or not title:
        return None
    try:
        item_id = uuid.UUID(str(item_id_raw))
    except ValueError:
        return None
    url = _coerce_optional_str(data.get("url"))
    return SourceReference(processed_item_id=item_id, title=title, url=url)


def _default_references(articles: list[DigestArticle] | None) -> list[SourceReference]:
    if not articles:
        return []
    return [
        SourceReference(
            processed_item_id=article.processed_item_id,
            title=article.title,
            url=article.url,
        )
        for article in articles[:5]
    ]


def _regex_fallback(
    text: str,
    *,
    section_key: str | None,
    articles: list[DigestArticle] | None,
) -> list[ParsedDigestSection]:
    headers = list(_SECTION_HEADER_RE.finditer(text))
    if not headers:
        if len(text) < 20:
            return []
        impact = _extract_impact(text)
        summary = _strip_impact(text)
        return [
            ParsedDigestSection(
                section_title=section_key or "Özet",
                ai_summary=summary.strip(),
                impact_note=impact,
                source_references=_default_references(articles),
                section_key=section_key,
            )
        ]

    sections: list[ParsedDigestSection] = []
    for index, match in enumerate(headers):
        title = match.group("title").strip()
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        impact = _extract_impact(body)
        summary = _strip_impact(body)
        sections.append(
            ParsedDigestSection(
                section_title=title,
                ai_summary=summary.strip(),
                impact_note=impact,
                source_references=_default_references(articles),
                section_key=section_key if len(headers) == 1 else None,
            )
        )
    return sections


def _extract_impact(text: str) -> str | None:
    match = _IMPACT_RE.search(text)
    if match is None:
        return None
    return match.group("impact").strip() or None


def _strip_impact(text: str) -> str:
    return _IMPACT_RE.sub("", text).strip()


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_str(value: Any) -> str | None:
    text = _coerce_str(value)
    return text or None

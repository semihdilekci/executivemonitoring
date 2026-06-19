"""DigestParser unit testleri."""

from __future__ import annotations

import uuid

import pytest
from services.ai_engine.digest_models import DigestArticle
from services.ai_engine.digest_parser import parse_llm_sections
from services.ai_engine.exceptions import DigestParseError

_ARTICLE = DigestArticle(
    processed_item_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    source_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    title="Test Haber",
    clean_content="İçerik metni burada.",
    relevance_score=0.9,
    published_at=None,
    url="https://example.com/haber",
    topics=["strateji"],
)


def test_parse_valid_json_object() -> None:
    raw = """
    {
      "section_title": "Yönetici Özeti",
      "ai_summary": "Bu hafta önemli gelişmeler yaşandı.",
      "impact_note": "Yıldız Holding için orta düzey etki.",
      "source_references": [
        {
          "processed_item_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          "title": "Test Haber",
          "url": "https://example.com/haber"
        }
      ]
    }
    """

    sections = parse_llm_sections(raw, section_key="executive_summary", articles=[_ARTICLE])

    assert len(sections) == 1
    assert sections[0].section_title == "Yönetici Özeti"
    assert "gelişmeler" in sections[0].ai_summary
    assert sections[0].impact_note is not None
    assert len(sections[0].source_references) == 1


def test_parse_valid_json_sections_array() -> None:
    raw = """
    {
      "sections": [
        {
          "section_title": "Trend 1",
          "ai_summary": "Özet 1"
        },
        {
          "section_title": "Trend 2",
          "ai_summary": "Özet 2",
          "impact_note": "Etki 2"
        }
      ]
    }
    """

    sections = parse_llm_sections(raw, articles=[_ARTICLE])

    assert len(sections) == 2
    assert sections[0].section_title == "Trend 1"
    assert sections[1].impact_note == "Etki 2"


def test_parse_json_code_block() -> None:
    raw = """```json
    {
      "section_title": "Kod Bloğu",
      "ai_summary": "JSON fence içinde."
    }
    ```"""

    sections = parse_llm_sections(raw, articles=[_ARTICLE])

    assert len(sections) == 1
    assert sections[0].section_title == "Kod Bloğu"


def test_parse_invalid_json_regex_fallback() -> None:
    raw = """## Haftalık Özet
Bu hafta FMCG sektöründe önemli hareketlilik gözlendi.

Etki Notu: Perakende kanalında rekabet artıyor.
"""

    sections = parse_llm_sections(raw, section_key="market_overview", articles=[_ARTICLE])

    assert len(sections) == 1
    assert sections[0].section_title == "Haftalık Özet"
    assert "hareketlilik" in sections[0].ai_summary
    assert sections[0].impact_note is not None
    assert sections[0].source_references


def test_parse_missing_section_fields_raises() -> None:
    raw = '{"section_title": "Sadece başlık"}'

    with pytest.raises(DigestParseError, match="eksik"):
        parse_llm_sections(raw)


def test_parse_empty_response_raises() -> None:
    with pytest.raises(DigestParseError, match="boş"):
        parse_llm_sections("   ")


def test_parse_defaults_source_references_from_articles() -> None:
    raw = """
    {
      "section_title": "Özet",
      "ai_summary": "Kaynak listesi yok."
    }
    """

    sections = parse_llm_sections(raw, articles=[_ARTICLE])

    assert len(sections[0].source_references) == 1
    assert sections[0].source_references[0].processed_item_id == _ARTICLE.processed_item_id

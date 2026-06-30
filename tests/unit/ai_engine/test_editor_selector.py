"""EditorSelector unit testleri — aday havuz filtresi, dağıtım, eleme, fallback."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from packages.shared.enums import ApiProvider
from services.ai_engine.digest_models import DigestArticle, DigestTypeQueryConfig
from services.ai_engine.editor_selector import (
    EditorSelector,
    count_articles_in_prompt,
    format_articles_for_prompt,
    parse_editor_response,
    render_prompt,
)
from services.ai_engine.exceptions import DigestParseError
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage

from tests.unit.ai_engine.test_llm_client import MockProvider

_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "llm" / "editor_response.json"


@dataclass
class _FakeSection:
    name: str
    sort_order: int


@dataclass
class _FakeNewsletter:
    name: str = "FMCG Haftalık"
    description: str = "FMCG sektörü haftalık bülteni."
    summary_system_prompt: str = "Sen kıdemli bir editörsün."
    summary_user_prompt: str = (
        "Bülten: {newsletter_name}\nDönem: {date_range}\n"
        "Bölümler:\n{sections}\n\nHaberler:\n{articles}"
    )
    min_content_score: int = 55
    content_categories: list[str] = field(default_factory=list)
    sections: list[_FakeSection] = field(
        default_factory=lambda: [
            _FakeSection(name="Piyasa Genel Görünümü", sort_order=0),
            _FakeSection(name="Marka Hamleleri", sort_order=1),
        ]
    )


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


def _article_with_body(item_id: uuid.UUID, *, body: str) -> DigestArticle:
    return DigestArticle(
        processed_item_id=item_id,
        source_id=uuid.uuid4(),
        title="Haber",
        clean_content=body,
        relevance_score=0.9,
        published_at=None,
        url="https://example.com/1",
        topics=["fmcg"],
    )


class _CapturingLLM:
    """`run_editor`'a verilen user_prompt'u yakalayan sahte LLM client."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.captured_user_prompt: str = ""

    async def complete(self, user_prompt: str, **_kwargs: Any) -> Any:
        self.captured_user_prompt = user_prompt
        return LLMResponse(
            text=self._text,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/test",
            latency_ms=10,
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


class _CapturingRepo:
    """`list_for_digest` çağrı argümanlarını kaydeder."""

    def __init__(self, articles: list[DigestArticle]) -> None:
        self._articles = articles
        self.last_config: DigestTypeQueryConfig | None = None
        self.last_min_score: float | None = None
        self.last_limit: int | None = None

    async def list_for_digest(
        self,
        _db: Any,
        *,
        config: DigestTypeQueryConfig,
        period_start: date,
        period_end: date,
        min_relevance_score: float,
        limit: int,
    ) -> list[DigestArticle]:
        self.last_config = config
        self.last_min_score = min_relevance_score
        self.last_limit = limit
        return self._articles


@pytest.mark.asyncio
async def test_select_candidates_uses_news_schema_and_score_threshold() -> None:
    repo = _CapturingRepo([_article()])
    selector = EditorSelector(
        llm_client=_llm_client("{}"),
        processed_items=repo,  # type: ignore[arg-type]
        candidate_limit=25,
    )

    await selector.select_candidates(
        object(),  # type: ignore[arg-type]
        newsletter=_FakeNewsletter(min_content_score=55),
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )

    assert repo.last_config is not None
    assert repo.last_config.schema == "news"
    assert repo.last_config.source_category is None
    assert repo.last_config.content_category is None
    assert repo.last_config.content_categories == ()
    assert repo.last_config.topic_keywords == ()
    # min_content_score 55 → relevance_score eşiği 0.55
    assert repo.last_min_score == pytest.approx(0.55)
    assert repo.last_limit == 25


@pytest.mark.asyncio
async def test_select_candidates_passes_content_categories_filter() -> None:
    repo = _CapturingRepo([_article()])
    selector = EditorSelector(
        llm_client=_llm_client("{}"),
        processed_items=repo,  # type: ignore[arg-type]
    )

    await selector.select_candidates(
        object(),  # type: ignore[arg-type]
        newsletter=_FakeNewsletter(content_categories=["fmcg"]),
        period_start=date(2026, 6, 18),
        period_end=date(2026, 6, 24),
    )

    assert repo.last_config is not None
    # bülten kategorisi tuple olarak aday havuz sorgusuna geçer
    assert repo.last_config.content_categories == ("fmcg",)
    # varsayılan aday tavanı en az 100 (tüm bültenler için)
    assert repo.last_limit == 100


@pytest.mark.asyncio
async def test_run_editor_distributes_articles_to_sections() -> None:
    art1, art2, art3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    response = json.dumps(
        {
            "summary": "Haftanın yönetici özeti.",
            "assignments": [
                {"section": "Piyasa Genel Görünümü", "article_ids": [str(art1), str(art2)]},
                {"section": "Marka Hamleleri", "article_ids": [str(art3)]},
            ],
            "dropped": [],
        }
    )
    selector = EditorSelector(llm_client=_llm_client(response))

    result = await selector.run_editor(
        newsletter=_FakeNewsletter(),
        articles=[_article(art1), _article(art2), _article(art3)],
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )

    assert result.summary == "Haftanın yönetici özeti."
    assert len(result.assignments) == 2
    first, second = result.assignments
    assert first.sort_order == 0
    assert first.article_ids == [art1, art2]
    assert second.sort_order == 1
    assert second.article_ids == [art3]


def test_parse_dropped_articles_are_not_assigned() -> None:
    kept, dropped = uuid.uuid4(), uuid.uuid4()
    # Editör tutarsız: dropped haberi aynı zamanda bir bölüme atamış.
    raw = json.dumps(
        {
            "summary": "özet",
            "assignments": [
                {"section": 0, "article_ids": [str(kept), str(dropped)]},
            ],
            "dropped": [str(dropped)],
        }
    )
    sections = _FakeNewsletter().sections
    articles = [_article(kept), _article(dropped)]

    result = parse_editor_response(raw, sections=sections, articles=articles)

    assert result.dropped == [dropped]
    assigned_ids = [aid for assignment in result.assignments for aid in assignment.article_ids]
    assert dropped not in assigned_ids
    assert assigned_ids == [kept]


def test_parse_ignores_hallucinated_article_ids() -> None:
    real = uuid.uuid4()
    hallucinated = uuid.uuid4()
    raw = json.dumps(
        {
            "summary": "özet",
            "assignments": [
                {"section": "Piyasa Genel Görünümü", "article_ids": [str(real), str(hallucinated)]},
            ],
            "dropped": [],
        }
    )
    sections = _FakeNewsletter().sections
    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments[0].article_ids == [real]


def test_parse_unknown_section_is_skipped() -> None:
    real = uuid.uuid4()
    raw = json.dumps(
        {
            "summary": "özet",
            "assignments": [
                {"section": "Olmayan Bölüm", "article_ids": [str(real)]},
            ],
            "dropped": [],
        }
    )
    sections = _FakeNewsletter().sections
    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments == []


def test_parse_section_by_index() -> None:
    real = uuid.uuid4()
    raw = json.dumps(
        {
            "summary": "özet",
            "assignments": [{"section": 1, "article_ids": [str(real)]}],
            "dropped": [],
        }
    )
    sections = _FakeNewsletter().sections
    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert len(result.assignments) == 1
    assert result.assignments[0].sort_order == 1


def test_parse_unparseable_json_raises_instead_of_dumping_to_first_section() -> None:
    """Regresyon: bozuk/parse edilemez editör çıktısı eskiden tüm haberleri ilk
    bölüme atıyordu ("hepsi tek bölümde" yanlış bülteni). Artık açıkça başarısız
    olmalı ki üretim "failed" işaretlensin ve admin yeniden tetiklesin.
    """
    art1, art2 = uuid.uuid4(), uuid.uuid4()
    sections = _FakeNewsletter().sections
    articles = [_article(art1), _article(art2)]

    with pytest.raises(DigestParseError):
        parse_editor_response(
            "Bu JSON değil, sadece düz metin.",
            sections=sections,
            articles=articles,
        )


def test_parse_matches_section_with_index_prefix_label() -> None:
    """Editör bölümü prompt'taki "1: Ad" etiketinin tamamıyla döndürürse de eşleşmeli."""
    real = uuid.uuid4()
    raw = json.dumps(
        {
            "summary": "özet",
            "assignments": [
                {"section": "1: Marka Hamleleri", "article_ids": [str(real)]}
            ],
            "dropped": [],
        }
    )
    sections = _FakeNewsletter().sections

    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments[0].sort_order == 1
    assert result.assignments[0].article_ids == [real]


def test_parse_tolerates_literal_newline_in_summary() -> None:
    """`summary` serbest metninde kaçışsız yeni satır parse'ı düşürmemeli (strict=False)."""
    real = uuid.uuid4()
    raw = (
        '{"summary": "Birinci cümle.\nİkinci cümle.", '
        '"assignments": [{"section": 0, "article_ids": ["' + str(real) + '"]}], '
        '"dropped": []}'
    )
    sections = _FakeNewsletter().sections

    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments[0].article_ids == [real]
    assert "İkinci cümle" in result.summary


def test_parse_ignores_trailing_prose_after_json_object() -> None:
    """Bloktan sonra gelen serbest metindeki `}` dengeli-nesne taramasıyla atlanmalı."""
    real = uuid.uuid4()
    raw = (
        "İşte sonuç:\n"
        '{"summary": "özet", '
        '"assignments": [{"section": 0, "article_ids": ["' + str(real) + '"]}], '
        '"dropped": []}\n'
        "Not: bazı haberler {atlandı}."
    )
    sections = _FakeNewsletter().sections

    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.summary == "özet"
    assert result.assignments[0].article_ids == [real]


def test_parse_tolerates_trailing_commas() -> None:
    """Uzun dizilerde LLM'in bıraktığı sondaki virgül parse'ı düşürmemeli."""
    real = uuid.uuid4()
    raw = (
        '{"summary": "özet", '
        '"assignments": [{"section": 0, "article_ids": ["' + str(real) + '",]},], '
        '"dropped": [],}'
    )
    sections = _FakeNewsletter().sections

    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments[0].article_ids == [real]


def test_parse_json_inside_code_fence() -> None:
    real = uuid.uuid4()
    raw = (
        "İşte sonuç:\n```json\n"
        + json.dumps(
            {
                "summary": "özet",
                "assignments": [{"section": 0, "article_ids": [str(real)]}],
                "dropped": [],
            }
        )
        + "\n```"
    )
    sections = _FakeNewsletter().sections
    result = parse_editor_response(raw, sections=sections, articles=[_article(real)])

    assert result.assignments[0].article_ids == [real]


def test_parse_editor_response_fixture() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    ids = {
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
    }
    articles = [_article(uuid.UUID(value)) for value in ids]
    sections = _FakeNewsletter().sections

    result = parse_editor_response(json.dumps(payload), sections=sections, articles=articles)

    assert result.summary.startswith("Bu hafta")
    assert result.assignments[0].article_ids == [
        uuid.UUID("11111111-1111-1111-1111-111111111111"),
        uuid.UUID("22222222-2222-2222-2222-222222222222"),
    ]
    assert result.assignments[1].article_ids == [
        uuid.UUID("33333333-3333-3333-3333-333333333333"),
    ]
    assert result.dropped == [uuid.UUID("44444444-4444-4444-4444-444444444444")]


def test_format_articles_long_first_article_does_not_crowd_out_others() -> None:
    """Regresyon: tek bir uzun haber bütçeyi tüketip diğer adayları dışlamamalı.

    Bug: editör 50 aday seçtiği halde ilk (en uzun, en yüksek skorlu) haber
    12000 karakter bütçesini doldurunca prompt'a yalnızca o 1 haber giriyordu;
    LLM "özetlenecek FMCG gelişmesi yok" diyordu.
    """
    ids = [uuid.uuid4() for _ in range(5)]
    articles = [_article_with_body(ids[0], body="X" * 40000)] + [
        _article_with_body(item_id, body="Kısa gövde.") for item_id in ids[1:]
    ]

    rendered = format_articles_for_prompt(
        articles, max_chars=80000, per_article_chars=900
    )

    assert count_articles_in_prompt(rendered) == 5
    for item_id in ids:
        assert str(item_id) in rendered
    # uzun haber snippet'e indirgenir (tam 40k gövde girmez)
    assert "X" * 40000 not in rendered
    assert "[…]" in rendered


@pytest.mark.asyncio
async def test_run_editor_sends_at_least_100_candidates_to_llm() -> None:
    """Regresyon: tüm bültenler için en az 100 aday editör prompt'una sığmalı."""
    ids = [uuid.uuid4() for _ in range(100)]
    # ilk haber çok uzun — eski davranışta tek başına bütçeyi tüketirdi
    articles = [_article_with_body(ids[0], body="L" * 30000)] + [
        _article_with_body(item_id, body=f"Haber gövdesi {i}.")
        for i, item_id in enumerate(ids[1:], start=1)
    ]
    capturing = _CapturingLLM("{}")
    selector = EditorSelector(llm_client=capturing)  # type: ignore[arg-type]

    await selector.run_editor(
        newsletter=_FakeNewsletter(),
        articles=articles,
        period_start=date(2026, 6, 18),
        period_end=date(2026, 6, 24),
    )

    assert count_articles_in_prompt(capturing.captured_user_prompt) == 100
    for item_id in ids:
        assert str(item_id) in capturing.captured_user_prompt


def test_render_prompt_replaces_single_brace_tokens_and_keeps_stray_braces() -> None:
    template = "Bülten: {newsletter_name}\nHaberler:\n{articles}"
    rendered = render_prompt(
        template,
        {"newsletter_name": "FMCG", "articles": "metin { süslü } parantez"},
    )

    assert "Bülten: FMCG" in rendered
    # makale içeriğindeki serbest süslü parantez korunur
    assert "{ süslü }" in rendered

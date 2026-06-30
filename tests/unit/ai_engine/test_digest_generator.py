"""DigestGenerator unit testleri — 3-aşamalı editör pipeline (Faz 6.5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
from packages.shared.enums import ApiProvider, DigestStatus
from packages.shared.models.digest import Digest
from services.ai_engine.digest_generator import DigestGenerator, build_digest_title
from services.ai_engine.digest_models import (
    DigestArticle,
    EditorResult,
    ParsedDigestSection,
    SectionAssignment,
    SourceReference,
)
from services.ai_engine.editor_selector import EditorSelector
from services.ai_engine.exceptions import DigestParseError, NoArticlesForDigestError
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.providers.base import LLMProvider
from services.ai_engine.section_generator import SectionGenerator

# --- Fixtures / fakes -------------------------------------------------------


@dataclass
class _FakeSection:
    id: uuid.UUID
    name: str
    sort_order: int
    section_system_prompt: str = "Sen bir analistsin."
    section_user_prompt: str = "Haberler:\n{articles}"
    impact_prompt: str = "Yıldız etkisini değerlendir."


@dataclass
class _FakeNewsletter:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    slug: str = "fmcg_weekly"
    name: str = "FMCG Haftalık"
    description: str = "FMCG sektörü haftalık bülteni."
    summary_system_prompt: str = "Sen kıdemli bir editörsün."
    summary_user_prompt: str = "Bölümler:\n{sections}\nHaberler:\n{articles}"
    min_content_score: int = 50
    content_categories: list[str] = field(default_factory=list)
    sections: list[_FakeSection] = field(default_factory=list)


def _article(item_id: uuid.UUID | None = None, *, title: str = "Haber") -> DigestArticle:
    return DigestArticle(
        processed_item_id=item_id or uuid.uuid4(),
        source_id=uuid.uuid4(),
        title=title,
        clean_content="Uzun içerik metni örnek makale gövdesi.",
        relevance_score=0.8,
        published_at=None,
        url="https://example.com/1",
        topics=["fmcg"],
    )


class _FakeDigestRepo:
    def __init__(self) -> None:
        self.sections: list[Any] = []
        self._digest: Digest | None = None

    async def find_for_period(self, _db: Any, **_kwargs: Any) -> Digest | None:
        return self._digest

    async def create_generating(self, _db: Any, **kwargs: Any) -> Digest:
        self._digest = Digest(
            id=uuid.uuid4(),
            newsletter_slug=kwargs["newsletter_slug"],
            newsletter_template_id=kwargs["newsletter_template_id"],
            title=kwargs["title"],
            status=DigestStatus.GENERATING,
            period_start=kwargs["period_start"],
            period_end=kwargs["period_end"],
            total_sources_used=0,
            generation_metadata={},
        )
        return self._digest

    async def reset_for_regeneration(self, _db: Any, digest: Digest, *, title: str) -> Digest:
        digest.title = title
        digest.status = DigestStatus.GENERATING
        digest.summary = None
        return digest

    async def add_sections(self, _db: Any, _digest_id: uuid.UUID, sections: list[Any]) -> list[Any]:
        self.sections = sections
        return sections

    async def mark_ready(self, _db: Any, digest: Digest, **kwargs: Any) -> Digest:
        digest.status = DigestStatus.READY
        digest.s3_archive_key = kwargs["s3_archive_key"]
        digest.total_sources_used = kwargs["total_sources_used"]
        digest.generation_metadata = kwargs["generation_metadata"]
        digest.completed_at = kwargs["completed_at"]
        return digest

    async def mark_failed(self, _db: Any, digest: Digest, **kwargs: Any) -> Digest:
        digest.status = DigestStatus.FAILED
        digest.error_message = kwargs["error_message"]
        digest.completed_at = kwargs["completed_at"]
        return digest


class _FakeArchiveService:
    async def upload_html(self, *, digest: Digest, sections: list[Any]) -> str:
        return f"{digest.newsletter_slug}/2026/06/{digest.id}.html"


class _FakeEditor:
    """Aday havuz + editör çıktısını sabitler."""

    def __init__(self, *, candidates: list[DigestArticle], result: EditorResult) -> None:
        self._candidates = candidates
        self._result = result

    async def select_candidates(self, _db: Any, **_kwargs: Any) -> list[DigestArticle]:
        return self._candidates

    async def run_editor(self, **_kwargs: Any) -> EditorResult:
        return self._result


class _FakeSectionGenerator:
    """Atanan haberlerden deterministik bölüm üretir; isteğe bağlı parse hatası."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[int] = []

    async def generate_section(
        self,
        *,
        section: _FakeSection,
        newsletter_name: str,
        articles: list[DigestArticle],
        date_range: str,
    ) -> ParsedDigestSection:
        self.calls.append(section.sort_order)
        if self._fail:
            raise DigestParseError("bölüm parse hatası")
        return ParsedDigestSection(
            section_title=section.name,
            ai_summary=f"{section.name} özeti",
            impact_note="Yıldız etkisi",
            source_references=[
                SourceReference(
                    processed_item_id=article.processed_item_id,
                    title=article.title,
                    url=article.url,
                )
                for article in articles
            ],
            newsletter_section_id=section.id,
        )


class _ScriptedProvider(LLMProvider):
    """Çağrı sırasına göre farklı yanıt döndürür (editör → bölümler)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._key_id = uuid.uuid4()
        self.call_count = 0

    @property
    def provider(self) -> ApiProvider:
        return ApiProvider.GROQ

    @property
    def key_id(self) -> uuid.UUID:
        return self._key_id

    @property
    def is_active(self) -> bool:
        return True

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        index = min(self.call_count, len(self._responses) - 1)
        text = self._responses[index]
        self.call_count += 1
        return LLMResponse(
            text=text,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/test",
            latency_ms=10,
        )


def _newsletter_with_two_sections() -> _FakeNewsletter:
    return _FakeNewsletter(
        sections=[
            _FakeSection(id=uuid.uuid4(), name="Piyasa Genel Görünümü", sort_order=0),
            _FakeSection(id=uuid.uuid4(), name="Marka Hamleleri", sort_order=1),
        ]
    )


# --- Tests ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_persists_summary_and_sections() -> None:
    art1, art2, art3 = _article(), _article(), _article()
    newsletter = _newsletter_with_two_sections()
    editor_result = EditorResult(
        summary="Haftanın yönetici özeti.",
        assignments=[
            SectionAssignment(
                section_name="Piyasa Genel Görünümü",
                sort_order=0,
                article_ids=[art1.processed_item_id, art2.processed_item_id],
            ),
            SectionAssignment(
                section_name="Marka Hamleleri",
                sort_order=1,
                article_ids=[art3.processed_item_id],
            ),
        ],
        dropped=[],
    )
    digest_repo = _FakeDigestRepo()
    audit_events: list[str] = []

    async def audit_hook(_db: Any, *, event_type: str, **_kwargs: Any) -> None:
        audit_events.append(event_type)

    generator = DigestGenerator(
        llm_client=LLMClient(providers=[]),
        editor_selector=_FakeEditor(candidates=[art1, art2, art3], result=editor_result),
        section_generator=_FakeSectionGenerator(),
        digests=digest_repo,
        archive_service=_FakeArchiveService(),
        audit_hook=audit_hook,
    )

    digest = await generator.generate(
        AsyncMock(),
        newsletter=newsletter,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
        actor_user_id=uuid.uuid4(),
    )

    assert digest.status == DigestStatus.READY
    assert digest.summary == "Haftanın yönetici özeti."
    assert digest.newsletter_slug == "fmcg_weekly"
    assert digest.s3_archive_key is not None
    assert len(digest_repo.sections) == 2
    assert digest_repo.sections[0].section_order == 1
    assert digest_repo.sections[0].newsletter_section_id == newsletter.sections[0].id
    # 3 benzersiz haber kullanıldı.
    assert digest.total_sources_used == 3
    assert audit_events == ["digest.started", "digest.completed"]


@pytest.mark.asyncio
async def test_generate_skips_sections_with_no_assignment() -> None:
    art1 = _article()
    newsletter = _newsletter_with_two_sections()
    editor_result = EditorResult(
        summary="özet",
        assignments=[
            SectionAssignment(
                section_name="Piyasa Genel Görünümü",
                sort_order=0,
                article_ids=[art1.processed_item_id],
            ),
        ],
        dropped=[],
    )
    digest_repo = _FakeDigestRepo()
    section_gen = _FakeSectionGenerator()

    generator = DigestGenerator(
        llm_client=LLMClient(providers=[]),
        editor_selector=_FakeEditor(candidates=[art1], result=editor_result),
        section_generator=section_gen,
        digests=digest_repo,
        archive_service=_FakeArchiveService(),
    )

    digest = await generator.generate(
        AsyncMock(),
        newsletter=newsletter,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )

    assert digest.status == DigestStatus.READY
    # Yalnızca atama yapılan ilk bölüm üretildi.
    assert section_gen.calls == [0]
    assert len(digest_repo.sections) == 1
    assert digest_repo.sections[0].section_title == "Piyasa Genel Görünümü"

    # Diagnostik: 2 bölüm tanımlı, 1'i üretildi; boş bölüm açıkça işaretli
    # (pipeline detayında "neden 4/5 bölüm oluştu" görünür kılar).
    metadata = digest.generation_metadata
    assert metadata["defined_section_count"] == 2
    assert metadata["section_count"] == 1
    distribution = metadata["distribution"]
    assert [(row["sort_order"], row["generated"]) for row in distribution] == [
        (0, True),
        (1, False),
    ]
    assert distribution[0]["assigned_count"] == 1
    assert distribution[1]["assigned_count"] == 0


@pytest.mark.asyncio
async def test_generate_section_parse_error_marks_failed() -> None:
    art1 = _article()
    newsletter = _newsletter_with_two_sections()
    editor_result = EditorResult(
        summary="özet",
        assignments=[
            SectionAssignment(
                section_name="Piyasa Genel Görünümü",
                sort_order=0,
                article_ids=[art1.processed_item_id],
            ),
        ],
        dropped=[],
    )
    digest_repo = _FakeDigestRepo()

    generator = DigestGenerator(
        llm_client=LLMClient(providers=[]),
        editor_selector=_FakeEditor(candidates=[art1], result=editor_result),
        section_generator=_FakeSectionGenerator(fail=True),
        digests=digest_repo,
        archive_service=_FakeArchiveService(),
    )

    with pytest.raises(DigestParseError):
        await generator.generate(
            AsyncMock(),
            newsletter=newsletter,
            period_start=date(2026, 6, 9),
            period_end=date(2026, 6, 15),
        )

    assert digest_repo._digest is not None
    assert digest_repo._digest.status == DigestStatus.FAILED
    assert digest_repo._digest.error_message is not None


@pytest.mark.asyncio
async def test_generate_no_candidates_marks_failed() -> None:
    newsletter = _newsletter_with_two_sections()
    digest_repo = _FakeDigestRepo()

    generator = DigestGenerator(
        llm_client=LLMClient(providers=[]),
        editor_selector=_FakeEditor(
            candidates=[],
            result=EditorResult(summary="", assignments=[], dropped=[]),
        ),
        section_generator=_FakeSectionGenerator(),
        digests=digest_repo,
        archive_service=_FakeArchiveService(),
    )

    with pytest.raises(NoArticlesForDigestError):
        await generator.generate(
            AsyncMock(),
            newsletter=newsletter,
            period_start=date(2026, 6, 9),
            period_end=date(2026, 6, 15),
        )

    assert digest_repo._digest is not None
    assert digest_repo._digest.status == DigestStatus.FAILED


class _FakeProcessedRepo:
    def __init__(self, articles: list[DigestArticle]) -> None:
        self._articles = articles

    async def list_for_digest(self, *_args: Any, **_kwargs: Any) -> list[DigestArticle]:
        return self._articles


@pytest.mark.asyncio
async def test_generate_end_to_end_with_real_editor_and_sections() -> None:
    """Gerçek EditorSelector + SectionGenerator; scripted LLM ile uçtan uca."""
    art1, art2 = _article(title="Haber A"), _article(title="Haber B")
    newsletter = _newsletter_with_two_sections()

    editor_json = json.dumps(
        {
            "summary": "Bu hafta FMCG'de fiyat baskısı öne çıktı.",
            "assignments": [
                {"section": "Piyasa Genel Görünümü", "article_ids": [str(art1.processed_item_id)]},
                {"section": "Marka Hamleleri", "article_ids": [str(art2.processed_item_id)]},
            ],
            "dropped": [],
        }
    )
    section_json = json.dumps({"ai_summary": "Bölüm özeti.", "impact_note": "Yıldız etkisi."})
    provider = _ScriptedProvider([editor_json, section_json, section_json])
    llm_client = LLMClient(providers=[provider])
    digest_repo = _FakeDigestRepo()

    generator = DigestGenerator(
        llm_client=llm_client,
        editor_selector=EditorSelector(
            llm_client=llm_client,
            processed_items=_FakeProcessedRepo([art1, art2]),  # type: ignore[arg-type]
        ),
        section_generator=SectionGenerator(llm_client=llm_client),
        digests=digest_repo,
        archive_service=_FakeArchiveService(),
    )

    digest = await generator.generate(
        AsyncMock(),
        newsletter=newsletter,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )

    assert digest.status == DigestStatus.READY
    assert digest.summary == "Bu hafta FMCG'de fiyat baskısı öne çıktı."
    assert len(digest_repo.sections) == 2
    # editör (1) + bölüm (2) = 3 LLM çağrısı
    assert provider.call_count == 3
    assert digest_repo.sections[0].ai_summary == "Bölüm özeti."
    assert digest_repo.sections[0].impact_note == "Yıldız etkisi."


def test_build_digest_title_uses_newsletter_name_and_turkish_month() -> None:
    title = build_digest_title("FMCG Haftalık", date(2026, 6, 9), date(2026, 6, 15))

    assert "FMCG Haftalık" in title
    assert "9-15 Haziran 2026" in title

"""DigestGenerator unit testleri — mock LLM, repo ve audit."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
from packages.shared.enums import ApiProvider, DigestStatus, DigestType
from packages.shared.models.digest import Digest
from packages.shared.models.prompt_template import PromptTemplate
from services.ai_engine.digest_generator import (
    DigestGenerator,
    build_digest_title,
    format_articles_for_prompt,
)
from services.ai_engine.digest_models import (
    DIGEST_TYPE_QUERY_CONFIG,
    DigestArticle,
    DigestTypeQueryConfig,
)
from services.ai_engine.exceptions import NoArticlesForDigestError
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage

from tests.unit.ai_engine.test_llm_client import MockProvider


def _article(*, title: str = "Haber", score: float = 0.8) -> DigestArticle:
    return DigestArticle(
        processed_item_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        title=title,
        clean_content="Uzun içerik metni örnek makale gövdesi.",
        relevance_score=score,
        published_at=None,
        url="https://example.com/1",
        topics=["strateji"],
    )


def _template(
    *,
    section_key: str,
    digest_type: DigestType = DigestType.FMCG_WEEKLY,
) -> PromptTemplate:
    return PromptTemplate(
        id=uuid.uuid4(),
        name=f"{digest_type.value}_{section_key}",
        digest_type=digest_type,
        section_key=section_key,
        system_prompt="Sen bir analistsin.",
        user_prompt_template="Makaleler:\n{{ articles }}",
        model_preference="groq",
        is_active=True,
        version=1,
    )


class _FakeProcessedRepo:
    def __init__(self, articles: list[DigestArticle]) -> None:
        self._articles = articles

    async def list_for_digest(self, *_args: Any, **_kwargs: Any) -> list[DigestArticle]:
        return self._articles


class _TrackingProcessedRepo:
    """`list_for_digest` çağrısındaki config'i kaydeder."""

    def __init__(self, articles: list[DigestArticle]) -> None:
        self._articles = articles
        self.last_config: DigestTypeQueryConfig | None = None

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
        return self._articles


class _FakeDigestRepo:
    def __init__(self) -> None:
        self.sections: list[Any] = []
        self._digest: Digest | None = None

    async def find_for_period(self, _db: Any, **_kwargs: Any) -> Digest | None:
        return self._digest

    async def create_generating(self, _db: Any, **kwargs: Any) -> Digest:
        self._digest = Digest(
            id=uuid.uuid4(),
            digest_type=kwargs["digest_type"],
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


class _FakeTemplateResolver:
    def __init__(self, templates: list[PromptTemplate]) -> None:
        self._templates = templates

    async def list_active_templates(
        self,
        _db: Any,
        *,
        digest_type: DigestType,
    ) -> list[PromptTemplate]:
        return [template for template in self._templates if template.digest_type == digest_type]


class _FakeArchiveService:
    async def upload_html(self, *, digest: Digest, sections: list[Any]) -> str:
        return f"{digest.digest_type.value}/2026/06/{digest.id}.html"


@pytest.fixture
def llm_response_json() -> str:
    return """
    {
      "section_title": "Piyasa Özeti",
      "ai_summary": "FMCG piyasasında bu hafta hareketlilik arttı.",
      "impact_note": "Yıldız Holding için olumlu sinyaller.",
      "source_references": []
    }
    """


@pytest.mark.asyncio
async def test_generate_success_creates_ready_digest(llm_response_json: str) -> None:
    provider = MockProvider(
        provider=ApiProvider.GROQ,
        returns=LLMResponse(
            text=llm_response_json,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/test",
            latency_ms=10,
        ),
    )
    llm_client = LLMClient(providers=[provider])
    digest_repo = _FakeDigestRepo()
    audit_events: list[str] = []

    async def audit_hook(
        _db: Any,
        *,
        event_type: str,
        actor_user_id: uuid.UUID | None,
        target_type: str | None,
        target_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        audit_events.append(event_type)

    generator = DigestGenerator(
        llm_client=llm_client,
        processed_items=_FakeProcessedRepo([_article()]),
        digests=digest_repo,
        template_resolver=_FakeTemplateResolver(
            [
                _template(section_key="market_overview"),
                _template(section_key="brand_moves"),
            ]
        ),
        archive_service=_FakeArchiveService(),
        audit_hook=audit_hook,
    )

    digest = await generator.generate(
        AsyncMock(),
        digest_type=DigestType.FMCG_WEEKLY,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
        actor_user_id=uuid.uuid4(),
    )

    assert digest.status == DigestStatus.READY
    assert digest.s3_archive_key is not None
    assert digest.total_sources_used == 1
    assert len(digest_repo.sections) == 2
    assert provider.call_count == 2
    assert audit_events == ["digest.started", "digest.completed"]


async def _generate_for_digest_type(
    *,
    digest_type: DigestType,
    section_keys: list[str],
    llm_response_json: str,
) -> tuple[Digest, _FakeDigestRepo, _TrackingProcessedRepo]:
    provider = MockProvider(
        provider=ApiProvider.GROQ,
        returns=LLMResponse(
            text=llm_response_json,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/test",
            latency_ms=10,
        ),
    )
    llm_client = LLMClient(providers=[provider])
    digest_repo = _FakeDigestRepo()
    processed_repo = _TrackingProcessedRepo([_article()])
    templates = [_template(section_key=key, digest_type=digest_type) for key in section_keys]

    generator = DigestGenerator(
        llm_client=llm_client,
        processed_items=processed_repo,
        digests=digest_repo,
        template_resolver=_FakeTemplateResolver(templates),
        archive_service=_FakeArchiveService(),
    )

    digest = await generator.generate(
        AsyncMock(),
        digest_type=digest_type,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
        actor_user_id=uuid.uuid4(),
    )
    return digest, digest_repo, processed_repo


@pytest.mark.asyncio
async def test_generate_turkish_media_weekly_uses_media_query_config(
    llm_response_json: str,
) -> None:
    digest, digest_repo, processed_repo = await _generate_for_digest_type(
        digest_type=DigestType.TURKISH_MEDIA_WEEKLY,
        section_keys=["headlines", "sector_highlights"],
        llm_response_json=llm_response_json,
    )

    expected = DIGEST_TYPE_QUERY_CONFIG["turkish_media_weekly"]
    assert processed_repo.last_config == expected
    assert processed_repo.last_config is not None
    assert processed_repo.last_config.schema == "news"
    assert processed_repo.last_config.source_category is None
    assert digest.status == DigestStatus.READY
    assert len(digest_repo.sections) == 2


@pytest.mark.asyncio
async def test_generate_strategy_weekly_uses_topic_keyword_config(
    llm_response_json: str,
) -> None:
    digest, digest_repo, processed_repo = await _generate_for_digest_type(
        digest_type=DigestType.STRATEGY_WEEKLY,
        section_keys=["executive_summary", "global_trends"],
        llm_response_json=llm_response_json,
    )

    expected = DIGEST_TYPE_QUERY_CONFIG["strategy_weekly"]
    assert processed_repo.last_config == expected
    assert processed_repo.last_config is not None
    assert processed_repo.last_config.schema == "news"
    assert processed_repo.last_config.topic_keywords
    assert digest.status == DigestStatus.READY
    assert len(digest_repo.sections) == 2


@pytest.mark.asyncio
async def test_generate_no_articles_marks_failed() -> None:
    digest_repo = _FakeDigestRepo()
    generator = DigestGenerator(
        llm_client=LLMClient(providers=[MockProvider(provider=ApiProvider.GROQ)]),
        processed_items=_FakeProcessedRepo([]),
        digests=digest_repo,
        template_resolver=_FakeTemplateResolver([_template(section_key="market_overview")]),
    )

    with pytest.raises(NoArticlesForDigestError):
        await generator.generate(
            AsyncMock(),
            digest_type=DigestType.FMCG_WEEKLY,
            period_start=date(2026, 6, 9),
            period_end=date(2026, 6, 15),
        )

    assert digest_repo._digest is not None
    assert digest_repo._digest.status == DigestStatus.FAILED
    assert digest_repo._digest.error_message is not None


def test_build_digest_title_turkish_month() -> None:
    title = build_digest_title(
        DigestType.FMCG_WEEKLY,
        date(2026, 6, 9),
        date(2026, 6, 15),
    )

    assert "FMCG Haftalık Bülten" in title
    assert "9-15 Haziran 2026" in title


def test_format_articles_for_prompt_includes_metadata() -> None:
    article = _article(title="Örnek Başlık")
    text = format_articles_for_prompt([article])

    assert "Örnek Başlık" in text
    assert str(article.processed_item_id) in text
    assert "https://example.com/1" in text

"""Email collector unit testleri."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.email_collector import EmailCollector
from services.collectors.handler import COLLECTOR_MAP

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "email"


def _make_email_source(**config_overrides: object) -> Source:
    config: dict[str, object] = {
        "imap_host": "imap.ygip.test",
        "imap_user": "fmcg-inbox@ygip.test",
        "mailbox": "INBOX",
        "sender_allowlist": ["newsletter@ygip.test"],
        "ingest_mode": "all",
        "default_category": "fmcg",
    }
    config.update(config_overrides)
    return Source(
        id=uuid.uuid4(),
        name="Test Email Source",
        source_type=SourceType.EMAIL,
        config=config,
        polling_interval_minutes=60,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.FMCG,
        target_phase="mvp-0",
    )


@pytest.fixture
def sample_newsletter_eml() -> bytes:
    return (FIXTURES_DIR / "sample_newsletter.eml").read_bytes()


@pytest.fixture
def plain_text_eml() -> bytes:
    return (FIXTURES_DIR / "plain_text_email.eml").read_bytes()


@pytest.mark.asyncio
async def test_email_collector_parses_html_newsletter(
    sample_newsletter_eml: bytes,
) -> None:
    collector = EmailCollector()
    source = _make_email_source()

    with patch.object(collector, "_fetch_messages", return_value=[sample_newsletter_eml]):
        articles = await collector.collect(source)

    assert len(articles) == 1
    article = articles[0]
    assert "FMCG Trendleri" in article.title
    assert article.content
    assert "<" not in article.content
    assert "%4,2" in article.content
    assert article.url == "https://example.com/fmcg-report"
    assert article.published_at is not None
    assert article.metadata.get("sender") == "newsletter@ygip.test"
    assert article.source_id == source.id


@pytest.mark.asyncio
async def test_email_collector_parses_plain_text_email(
    plain_text_eml: bytes,
) -> None:
    collector = EmailCollector()
    source = _make_email_source(
        sender_allowlist=["strategy-digest@ygip.test"],
        imap_user="strategy-inbox@ygip.test",
        default_category="strategy",
    )

    with patch.object(collector, "_fetch_messages", return_value=[plain_text_eml]):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert "Küresel Strateji" in articles[0].title
    assert "tedarik zinciri" in articles[0].content
    assert articles[0].url.startswith("email://")


@pytest.mark.asyncio
async def test_email_collector_filters_disallowed_sender(
    sample_newsletter_eml: bytes,
) -> None:
    collector = EmailCollector()
    source = _make_email_source(sender_allowlist=["other@ygip.test"])

    with patch.object(collector, "_fetch_messages", return_value=[sample_newsletter_eml]):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_email_collector_missing_imap_host_returns_empty() -> None:
    collector = EmailCollector()
    source = _make_email_source()
    source.config = {
        "imap_user": "fmcg-inbox@ygip.test",
        "mailbox": "INBOX",
        "sender_allowlist": ["newsletter@ygip.test"],
        "ingest_mode": "all",
        "default_category": "fmcg",
    }

    articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_email_collector_empty_mailbox_returns_empty() -> None:
    collector = EmailCollector()
    source = _make_email_source()

    with patch.object(collector, "_fetch_messages", return_value=[]):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_email_collector_content_hash_on_transform(
    sample_newsletter_eml: bytes,
) -> None:
    collector = EmailCollector()
    source = _make_email_source()

    with patch.object(collector, "_fetch_messages", return_value=[sample_newsletter_eml]):
        articles = await collector.collect(source)

    normalized = await collector.transform(articles[0])
    assert normalized.content_hash.startswith("sha256:")
    assert normalized.external_id is not None
    assert normalized.source_type == "email"


@pytest.mark.asyncio
async def test_email_collector_imap_failure_raises() -> None:
    collector = EmailCollector()
    source = _make_email_source()

    with (
        patch.object(collector, "_fetch_messages", side_effect=OSError("connection refused")),
        pytest.raises(RuntimeError, match="IMAP bağlantısı başarısız"),
    ):
        await collector.collect(source)


def test_collector_map_registers_email() -> None:
    assert "email" in COLLECTOR_MAP
    assert isinstance(COLLECTOR_MAP["email"], EmailCollector)

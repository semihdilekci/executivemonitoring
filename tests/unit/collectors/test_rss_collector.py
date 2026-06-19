"""RSS collector unit testleri."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.handler import COLLECTOR_MAP
from services.collectors.rss_collector import RSSCollector

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "rss"


def _make_rss_source(**config_overrides: object) -> Source:
    config: dict[str, object] = {
        "feed_url": "https://example.com/feed.xml",
        "ingest_mode": "filtered",
        "default_category": "turkish_media",
        "language": "tr",
    }
    config.update(config_overrides)
    return Source(
        id=uuid.uuid4(),
        name="Test RSS Source",
        source_type=SourceType.RSS,
        config=config,
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.TURKISH_MEDIA,
        target_phase="mvp-0",
    )


@pytest.fixture
def sample_rss_xml() -> str:
    return (FIXTURES_DIR / "sample_feed.xml").read_text(encoding="utf-8")


@pytest.fixture
def malformed_rss_xml() -> str:
    return (FIXTURES_DIR / "malformed_feed.xml").read_text(encoding="utf-8")


@pytest.fixture
def turkish_iso_feed_bytes() -> bytes:
    return (FIXTURES_DIR / "turkish_iso8859_feed.xml").read_bytes()


@pytest.mark.asyncio
async def test_rss_collector_parses_valid_feed(
    sample_rss_xml: str,
) -> None:
    collector = RSSCollector()
    source = _make_rss_source()

    with patch.object(collector, "_fetch", return_value=sample_rss_xml):
        articles = await collector.collect(source)

    assert len(articles) == 2
    assert all(article.title for article in articles)
    assert all(article.content for article in articles)
    assert all(article.url.startswith("https://") for article in articles)
    assert articles[0].source_id == source.id
    assert articles[0].published_at is not None
    assert articles[0].metadata.get("language") == "tr"


@pytest.mark.asyncio
async def test_rss_collector_extracts_html_description(
    sample_rss_xml: str,
) -> None:
    collector = RSSCollector()
    source = _make_rss_source()

    with patch.object(collector, "_fetch", return_value=sample_rss_xml):
        articles = await collector.collect(source)

    html_article = next(item for item in articles if "Enflasyon" in item.title)
    assert "<p>" not in html_article.content
    assert "yüzde 3,2" in html_article.content


@pytest.mark.asyncio
async def test_rss_collector_handles_malformed_xml(
    malformed_rss_xml: str,
) -> None:
    collector = RSSCollector()
    source = _make_rss_source()

    with patch.object(collector, "_fetch", return_value=malformed_rss_xml):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_rss_collector_handles_empty_feed() -> None:
    collector = RSSCollector()
    source = _make_rss_source()
    empty_feed = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'

    with patch.object(collector, "_fetch", return_value=empty_feed):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_rss_collector_decodes_iso8859_turkish_chars(
    turkish_iso_feed_bytes: bytes,
) -> None:
    collector = RSSCollector()
    source = _make_rss_source()
    decoded = turkish_iso_feed_bytes

    with patch.object(collector, "_fetch", return_value=decoded):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert "İstanbul" in articles[0].title
    assert "şırınga" in articles[0].title
    assert "Öğrenci" in articles[0].content


@pytest.mark.asyncio
async def test_rss_collector_missing_feed_url_returns_empty() -> None:
    collector = RSSCollector()
    source = _make_rss_source()
    source.config = {"ingest_mode": "filtered", "default_category": "turkish_media"}

    articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_rss_collector_content_hash_on_transform(sample_rss_xml: str) -> None:
    collector = RSSCollector()
    source = _make_rss_source()

    with patch.object(collector, "_fetch", return_value=sample_rss_xml):
        articles = await collector.collect(source)

    normalized = await collector.transform(articles[0])
    assert normalized.content_hash.startswith("sha256:")
    assert normalized.external_id is not None


def test_collector_map_registers_rss() -> None:
    assert "rss" in COLLECTOR_MAP
    assert isinstance(COLLECTOR_MAP["rss"], RSSCollector)

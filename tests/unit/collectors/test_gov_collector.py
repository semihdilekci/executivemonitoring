"""Gov collector unit testleri."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.gov_collector import GovCollector
from services.collectors.handler import COLLECTOR_MAP

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "gov"


def _make_gov_source(**config_overrides: object) -> Source:
    config: dict[str, object] = {
        "endpoint_url": "https://www.tcmb.gov.tr/feed",
        "gov_subtype": "tcmb",
        "ingest_mode": "all",
        "default_category": "official",
    }
    config.update(config_overrides)
    return Source(
        id=uuid.uuid4(),
        name="Test Gov Source",
        source_type=SourceType.GOV,
        config=config,
        polling_interval_minutes=30,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.OFFICIAL,
        target_phase="mvp-0",
    )


@pytest.fixture
def tcmb_feed_xml() -> str:
    return (FIXTURES_DIR / "tcmb_feed.xml").read_text(encoding="utf-8")


@pytest.fixture
def kap_feed_xml() -> str:
    return (FIXTURES_DIR / "kap_feed.xml").read_text(encoding="utf-8")


@pytest.fixture
def resmi_gazete_feed_bytes() -> bytes:
    return (FIXTURES_DIR / "resmi_gazete_feed.xml").read_bytes()


@pytest.fixture
def malformed_gov_feed() -> str:
    return (FIXTURES_DIR / "malformed_feed.xml").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_gov_collector_parses_tcmb_feed(tcmb_feed_xml: str) -> None:
    collector = GovCollector()
    source = _make_gov_source(gov_subtype="tcmb")

    with patch.object(collector, "_fetch", return_value=tcmb_feed_xml):
        articles = await collector.collect(source)

    assert len(articles) == 2
    assert all(article.title for article in articles)
    assert all(article.content for article in articles)
    assert articles[0].metadata["institution"] == "TCMB"
    assert articles[0].metadata["announcement_number"] == "2026/42"
    assert articles[0].metadata["gov_subtype"] == "tcmb"
    assert articles[0].published_at is not None


@pytest.mark.asyncio
async def test_gov_collector_parses_kap_feed(kap_feed_xml: str) -> None:
    collector = GovCollector()
    source = _make_gov_source(
        endpoint_url="https://www.kap.org.tr/feed",
        gov_subtype="kap",
    )

    with patch.object(collector, "_fetch", return_value=kap_feed_xml):
        articles = await collector.collect(source)

    assert len(articles) == 2
    assert articles[0].metadata["institution"] == "KAP"
    assert articles[0].metadata["announcement_number"] == "2026/0898"
    assert "Özel Durum" in articles[0].title


@pytest.mark.asyncio
async def test_gov_collector_parses_resmi_gazete_with_turkish_chars(
    resmi_gazete_feed_bytes: bytes,
) -> None:
    collector = GovCollector()
    source = _make_gov_source(
        endpoint_url="https://www.resmigazete.gov.tr/feed",
        gov_subtype="resmi_gazete",
    )

    with patch.object(collector, "_fetch", return_value=resmi_gazete_feed_bytes):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert articles[0].metadata["institution"] == "Resmi Gazete"
    assert articles[0].metadata["issue_number"] == "32612"
    assert "İşçi" in articles[0].content
    assert "sendikaları" in articles[0].content


@pytest.mark.asyncio
async def test_gov_collector_accepts_parser_config_alias(kap_feed_xml: str) -> None:
    collector = GovCollector()
    source = _make_gov_source(
        endpoint_url="https://www.kap.org.tr/feed",
        gov_subtype=None,
        parser="kap",
    )

    with patch.object(collector, "_fetch", return_value=kap_feed_xml):
        articles = await collector.collect(source)

    assert len(articles) == 2
    assert articles[0].metadata["gov_subtype"] == "kap"


@pytest.mark.asyncio
async def test_gov_collector_handles_malformed_feed(malformed_gov_feed: str) -> None:
    collector = GovCollector()
    source = _make_gov_source()

    with patch.object(collector, "_fetch", return_value=malformed_gov_feed):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_gov_collector_missing_endpoint_url_returns_empty() -> None:
    collector = GovCollector()
    source = _make_gov_source()
    source.config = {
        "gov_subtype": "tcmb",
        "ingest_mode": "all",
        "default_category": "official",
    }

    articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_gov_collector_fetch_failure_raises() -> None:
    collector = GovCollector()
    source = _make_gov_source()

    with (
        patch.object(collector, "_fetch", side_effect=OSError("connection refused")),
        pytest.raises(RuntimeError, match="Gov feed alınamadı"),
    ):
        await collector.collect(source)


@pytest.mark.asyncio
async def test_gov_collector_content_hash_on_transform(tcmb_feed_xml: str) -> None:
    collector = GovCollector()
    source = _make_gov_source()

    with patch.object(collector, "_fetch", return_value=tcmb_feed_xml):
        articles = await collector.collect(source)

    normalized = await collector.transform(articles[0])
    assert normalized.content_hash.startswith("sha256:")
    assert normalized.source_type == "gov"
    assert normalized.raw_metadata.get("institution") == "TCMB"


def test_collector_map_registers_gov() -> None:
    assert "gov" in COLLECTOR_MAP
    assert isinstance(COLLECTOR_MAP["gov"], GovCollector)

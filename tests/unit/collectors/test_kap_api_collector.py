"""KAP API collector unit testleri."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.gov_collector import GovCollector
from services.collectors.kap_api_collector import KapApiCollector

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "gov"
_NOW = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)


def _make_kap_source(**config_overrides: object) -> Source:
    config: dict[str, object] = {
        "endpoint_url": "https://www.kap.org.tr/tr/api/memberDisclosureQuery",
        "api_url": "https://www.kap.org.tr/tr/api/memberDisclosureQuery",
        "parser": "kap",
        "parser_type": "api",
        "company_codes": ["ULKER", "YGYO", "YFAS"],
        "ingest_mode": "all",
        "default_category": "finance",
        "max_age_days": 7,
    }
    config.update(config_overrides)
    return Source(
        id=uuid.uuid4(),
        name="KAP Bildirimler",
        source_type=SourceType.GOV,
        config=config,
        polling_interval_minutes=30,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.OFFICIAL,
        target_phase="mvp-0",
    )


@pytest.fixture
def kap_disclosures_json() -> bytes:
    return (FIXTURES_DIR / "kap_disclosures.json").read_bytes()


@pytest.mark.asyncio
async def test_kap_collector_parses_disclosures(kap_disclosures_json: bytes) -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source()

    with patch.object(collector, "_post", return_value=kap_disclosures_json):
        articles = await collector.collect(source)

    # ALKSZ takip edilmeyen şirket — elenir; ULKER + YGYO/YFAS kalır.
    assert len(articles) == 2
    ulker = articles[0]
    assert "ÜLKER" in ulker.title
    assert ulker.url == "https://www.kap.org.tr/tr/Bildirim/1454321"
    assert ulker.metadata["gov_subtype"] == "kap"
    assert ulker.metadata["institution"] == "KAP"
    assert ulker.metadata["stock_codes"] == ["ULKER"]
    assert ulker.published_at == datetime(2026, 6, 20, 18, 30, 45, tzinfo=UTC)
    assert ulker.external_id == "kap-1454321"


@pytest.mark.asyncio
async def test_kap_collector_empty_summary_falls_back_to_subject(
    kap_disclosures_json: bytes,
) -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source()

    with patch.object(collector, "_post", return_value=kap_disclosures_json):
        articles = await collector.collect(source)

    ygyo = next(a for a in articles if "YGYO" in a.metadata["stock_codes"])
    # Özet boş; içerik bildirim konusuna düşmeli, bildirim elenmemeli.
    assert ygyo.content == "Finansal Tablo Bildirimi"


@pytest.mark.asyncio
async def test_kap_collector_sends_date_range_post_body() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source()

    with patch.object(collector, "_post", return_value=b"[]") as mock_post:
        await collector.collect(source)

    body = mock_post.call_args.args[1]
    assert body["fromDate"] == "2026-06-14"
    assert body["toDate"] == "2026-06-21"
    assert body["memberType"] == "IGS"


@pytest.mark.asyncio
async def test_kap_collector_no_company_filter_keeps_all() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source(company_codes=[])
    payload = json.dumps(
        [
            {
                "disclosureIndex": 1,
                "publishDate": "21.06.2026 10:00:00",
                "companyName": "HERHANGI A.Ş.",
                "title": "Genel Bildirim",
                "summary": "Içerik.",
                "stockCodes": "HRHNG",
            }
        ]
    ).encode("utf-8")

    with patch.object(collector, "_post", return_value=payload):
        articles = await collector.collect(source)

    assert len(articles) == 1


@pytest.mark.asyncio
async def test_kap_collector_filters_out_of_window() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source(company_codes=[], max_age_days=7)
    payload = json.dumps(
        [
            {
                "disclosureIndex": 2,
                "publishDate": "01.03.2026 10:00:00",
                "companyName": "ESKI A.Ş.",
                "title": "Eski Bildirim",
                "summary": "Çok eski.",
                "stockCodes": "ESKI",
            }
        ]
    ).encode("utf-8")

    with patch.object(collector, "_post", return_value=payload):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_kap_collector_wrapped_data_key() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source(company_codes=[])
    payload = json.dumps(
        {
            "data": [
                {
                    "disclosureIndex": 3,
                    "publishDate": "21.06.2026 10:00:00",
                    "companyName": "SARMAL A.Ş.",
                    "title": "Bildirim",
                    "summary": "Sarmalanmış yanıt.",
                    "stockCodes": "SRML",
                }
            ]
        }
    ).encode("utf-8")

    with patch.object(collector, "_post", return_value=payload):
        articles = await collector.collect(source)

    assert len(articles) == 1


@pytest.mark.asyncio
async def test_kap_collector_invalid_json_returns_empty() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source()

    with patch.object(collector, "_post", return_value=b"<html>not json</html>"):
        articles = await collector.collect(source)

    assert articles == []


@pytest.mark.asyncio
async def test_kap_collector_fetch_failure_raises() -> None:
    collector = KapApiCollector(now=_NOW)
    source = _make_kap_source()

    with (
        patch.object(collector, "_post", side_effect=OSError("connection refused")),
        pytest.raises(RuntimeError, match="KAP API alınamadı"),
    ):
        await collector.collect(source)


@pytest.mark.asyncio
async def test_gov_collector_delegates_api_source(kap_disclosures_json: bytes) -> None:
    """GovCollector, parser_type == 'api' kaynağı KapApiCollector'a delege etmeli."""
    collector = GovCollector(now=_NOW)
    source = _make_kap_source()

    api_collector = collector._get_api_collector(source)
    with patch.object(api_collector, "_post", return_value=kap_disclosures_json):
        articles = await collector.collect(source)

    assert len(articles) == 2
    assert articles[0].metadata["gov_subtype"] == "kap"


@pytest.mark.asyncio
async def test_gov_collector_transform_keeps_gov_source_type(
    kap_disclosures_json: bytes,
) -> None:
    collector = GovCollector(now=_NOW)
    source = _make_kap_source()

    api_collector = collector._get_api_collector(source)
    with patch.object(api_collector, "_post", return_value=kap_disclosures_json):
        articles = await collector.collect(source)

    normalized = await collector.transform(articles[0])
    assert normalized.source_type == "gov"
    assert normalized.content_hash.startswith("sha256:")

"""RSS collector unit testleri."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
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
        "default_category": "macro",
        "language": "tr",
        # Generic parse testleri tarih/ağ'dan bağımsız olsun:
        "max_age_days": 3650,
        "fetch_full_text": False,
    }
    config.update(config_overrides)
    return Source(
        id=uuid.uuid4(),
        name="Test RSS Source",
        source_type=SourceType.RSS,
        config=config,
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.MACRO,
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
    source.config = {"ingest_mode": "filtered", "default_category": "macro"}

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


# --- Tarih penceresi + tam metin fetch + url-cache testleri ---

_NOW = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)


def _feed_with_dates(*, recent_date: str, old_date: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Yeni haber</title>
    <link>https://example.com/yeni</link>
    <guid>https://example.com/yeni</guid>
    <description>Bu hafta içindeki güncel bir gelişme.</description>
    <pubDate>{recent_date}</pubDate>
  </item>
  <item>
    <title>Eski haber</title>
    <link>https://example.com/eski</link>
    <guid>https://example.com/eski</guid>
    <description>Aylar öncesine ait eski bir gelişme.</description>
    <pubDate>{old_date}</pubDate>
  </item>
</channel></rss>"""


def _feed_short_summary(url: str = "https://example.com/makale") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Kısa özetli haber</title>
    <link>{url}</link>
    <guid>{url}</guid>
    <description>Sadece kısa bir spot cümle.</description>
    <pubDate>Sat, 20 Jun 2026 09:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


@pytest.mark.asyncio
async def test_rss_window_filters_old_entries() -> None:
    collector = RSSCollector(now=_NOW)
    source = _make_rss_source(max_age_days=7, fetch_full_text=False)
    feed = _feed_with_dates(
        recent_date="Sat, 20 Jun 2026 09:00:00 GMT",
        old_date="Sun, 01 Mar 2026 09:00:00 GMT",
    )

    with patch.object(collector, "_fetch", return_value=feed):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert articles[0].title == "Yeni haber"


@pytest.mark.asyncio
async def test_rss_window_configurable_per_source() -> None:
    """max_age_days genişletilince eski haber de gelir."""
    collector = RSSCollector(now=_NOW)
    source = _make_rss_source(max_age_days=365, fetch_full_text=False)
    feed = _feed_with_dates(
        recent_date="Sat, 20 Jun 2026 09:00:00 GMT",
        old_date="Sun, 01 Mar 2026 09:00:00 GMT",
    )

    with patch.object(collector, "_fetch", return_value=feed):
        articles = await collector.collect(source)

    assert len(articles) == 2


@pytest.mark.asyncio
async def test_rss_fetches_full_text_when_summary_short() -> None:
    collector = RSSCollector(now=_NOW)
    source = _make_rss_source(fetch_full_text=True, max_age_days=3650)
    full_html = (
        "<html><body><article><p>"
        + " ".join(f"kelime{i}" for i in range(200))
        + "</p></article></body></html>"
    )

    with (
        patch.object(collector, "_fetch", return_value=_feed_short_summary()),
        patch.object(collector, "_fetch_page", return_value=full_html) as page_mock,
    ):
        articles = await collector.collect(source)

    assert len(articles) == 1
    page_mock.assert_awaited_once()
    assert len(articles[0].content.split()) >= 120
    assert "kelime150" in articles[0].content


@pytest.mark.asyncio
async def test_rss_full_text_fallback_on_fetch_error() -> None:
    collector = RSSCollector(now=_NOW)
    source = _make_rss_source(fetch_full_text=True, max_age_days=3650)

    with (
        patch.object(collector, "_fetch", return_value=_feed_short_summary()),
        patch.object(collector, "_fetch_page", side_effect=OSError("timeout")),
    ):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert "kısa bir spot" in articles[0].content.lower()


@pytest.mark.asyncio
async def test_rss_marks_url_after_collect() -> None:
    """Toplanan makalenin URL'si cache'e yazılır (bir sonraki run atlasın)."""

    class _RecordingRedis:
        def __init__(self) -> None:
            self.sets: list[str] = []

        async def exists(self, *_keys: str) -> int:
            return 0

        async def set(self, key: str, *_a: object, **_k: object) -> None:
            self.sets.append(key)

    redis = _RecordingRedis()
    collector = RSSCollector(redis, now=_NOW)  # type: ignore[arg-type]
    source = _make_rss_source(fetch_full_text=False, max_age_days=3650)

    with patch.object(collector, "_fetch", return_value=_feed_short_summary()):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert len(redis.sets) == 1
    assert redis.sets[0].startswith("collector:url:")


@pytest.mark.asyncio
async def test_rss_full_text_timeout_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sayfa fetch'i timeout'u aşarsa feed özetine düşülür (run takılmaz)."""
    import services.collectors.rss_collector as rss_mod

    monkeypatch.setattr(rss_mod, "FULL_TEXT_TIMEOUT_SECONDS", 0.05)
    collector = RSSCollector(now=_NOW)
    source = _make_rss_source(fetch_full_text=True, max_age_days=3650)

    async def _slow_page(_url: str, **_kwargs: object) -> str:
        await asyncio.sleep(0.5)
        return "<html><body><article><p>gecikmis</p></article></body></html>"

    with (
        patch.object(collector, "_fetch", return_value=_feed_short_summary()),
        patch.object(collector, "_fetch_page", side_effect=_slow_page),
    ):
        articles = await collector.collect(source)

    assert len(articles) == 1
    assert "kısa bir spot" in articles[0].content.lower()


@pytest.mark.asyncio
async def test_rss_skips_already_collected_url() -> None:
    class _FakeRedis:
        async def exists(self, *_keys: str) -> int:
            return 1

        async def set(self, *_a: object, **_k: object) -> None:
            return None

    collector = RSSCollector(_FakeRedis(), now=_NOW)  # type: ignore[arg-type]
    source = _make_rss_source(fetch_full_text=True, max_age_days=3650)

    with (
        patch.object(collector, "_fetch", return_value=_feed_short_summary()),
        patch.object(collector, "_fetch_page") as page_mock,
    ):
        articles = await collector.collect(source)

    assert articles == []
    page_mock.assert_not_awaited()

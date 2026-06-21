"""RSS/Atom feed collector — feedparser + tam metin çıkarma + tarih penceresi."""

from __future__ import annotations

import asyncio
import logging
import re
from calendar import timegm
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import feedparser
from packages.shared.enums import SourceType
from packages.shared.models.source import Source
from redis.asyncio import Redis

from services.collectors.base_collector import BaseCollector
from services.collectors.feed_utils import is_within_window, resolve_window_days
from services.collectors.models import RawArticle

logger = logging.getLogger("ygip.collectors.rss")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DEFAULT_USER_AGENT = "YGIP-RSS-Collector/0.1"
# Feed gövdesi bu kelime sayısının altındaysa yalnızca özet/snippet kabul edilir
# ve makale URL'sinden tam metin çekilmeye çalışılır.
FULL_TEXT_MIN_WORDS = 120
# Tam metin sayfa fetch'leri sınırlandırılmazsa collect aşaması saatlerce sürebilir
# (kaynak × makale sıralı ağ isteği). Eşzamanlılık + sıkı timeout + kaynak başına
# üst sınır ile wall-clock sınırlanır.
FULL_TEXT_CONCURRENCY = 8
FULL_TEXT_TIMEOUT_SECONDS = 10
MAX_FULL_TEXT_PER_SOURCE = 50


class RSSCollector(BaseCollector):
    """RSS/Atom kaynaklarından makale toplar (`Docs/04` §7)."""

    source_type = SourceType.RSS
    track_fetched_urls = True

    def __init__(self, redis_client: Redis | None = None, *, now: datetime | None = None) -> None:
        super().__init__(redis_client)
        self._now = now

    async def collect(self, source: Source) -> list[RawArticle]:
        feed_url = source.config.get("feed_url")
        if not isinstance(feed_url, str) or not feed_url.strip():
            logger.warning(
                "rss_missing_feed_url",
                extra={"source_id": str(source.id)},
            )
            return []

        try:
            raw_feed = await self._fetch(feed_url.strip())
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "rss_fetch_failed",
                extra={"source_id": str(source.id), "feed_url": feed_url},
                exc_info=True,
            )
            raise RuntimeError(f"RSS feed alınamadı: {feed_url}") from exc

        return await self._parse_feed(source, raw_feed)

    async def _fetch(self, url: str, *, timeout: int = 30) -> bytes:
        """Feed XML indirir — unit testlerde mock'lanır."""

        def _download() -> bytes:
            request = Request(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                data = response.read()
                return bytes(data)

        return await asyncio.to_thread(_download)

    async def _parse_feed(self, source: Source, raw_feed: str | bytes) -> list[RawArticle]:
        parsed = feedparser.parse(raw_feed)
        if parsed.bozo and not parsed.entries:
            logger.info(
                "rss_parse_empty_or_invalid",
                extra={"source_id": str(source.id)},
            )
            return []

        window_days = resolve_window_days(source.config)
        fetch_full_text = bool(source.config.get("fetch_full_text", True))

        # 1) Ucuz ön-eleme: tarih penceresi + daha önce toplanan URL (cache).
        candidates: list[tuple[Any, str, datetime | None]] = []
        skipped_old = 0
        for entry in parsed.entries:
            published_at = _parse_published_at(entry)
            if not is_within_window(published_at, window_days, now=self._now):
                skipped_old += 1
                continue
            url = _clean_text(getattr(entry, "link", ""))
            if url and await self.url_already_collected(url):
                continue
            candidates.append((entry, url, published_at))

        if skipped_old:
            logger.info(
                "rss_window_filtered",
                extra={
                    "source_id": str(source.id),
                    "skipped_old": skipped_old,
                    "window_days": window_days,
                },
            )

        # 2) Tam metin fetch gerektirenleri eşzamanlı + sınırlı işle.
        over_cap = max(len(candidates) - MAX_FULL_TEXT_PER_SOURCE, 0)
        if over_cap and fetch_full_text:
            logger.info(
                "rss_full_text_capped",
                extra={
                    "source_id": str(source.id),
                    "capped": over_cap,
                    "max_per_source": MAX_FULL_TEXT_PER_SOURCE,
                },
            )

        semaphore = asyncio.Semaphore(FULL_TEXT_CONCURRENCY)
        tasks = [
            self._build_article(
                source,
                entry,
                url,
                published_at,
                allow_fetch=fetch_full_text and index < MAX_FULL_TEXT_PER_SOURCE,
                semaphore=semaphore,
            )
            for index, (entry, url, published_at) in enumerate(candidates)
        ]
        built = await asyncio.gather(*tasks)
        return [article for article in built if article is not None]

    async def _build_article(
        self,
        source: Source,
        entry: Any,
        url: str,
        published_at: datetime | None,
        *,
        allow_fetch: bool,
        semaphore: asyncio.Semaphore,
    ) -> RawArticle | None:
        title = _clean_text(getattr(entry, "title", ""))
        async with semaphore:
            content = await self._resolve_content(entry, url, allow_fetch)

        if not title or not content or not url:
            return None

        # URL'yi toplandı diye işaretle (fetch maliyetini bir sonraki run'da atla).
        await self.mark_url_collected(url)

        external_id = _clean_text(getattr(entry, "id", "")) or url
        language = source.config.get("language")
        metadata: dict[str, Any] = {"collector": "rss"}
        if isinstance(language, str) and language:
            metadata["language"] = language

        return RawArticle(
            source_id=source.id,
            title=title,
            content=content,
            url=url,
            published_at=published_at,
            metadata=metadata,
            external_id=external_id,
        )

    async def _resolve_content(self, entry: Any, url: str, fetch_full_text: bool) -> str:
        """Feed gövdesini döner; kısa (özet) ise makale sayfasından tam metni dener."""
        feed_content = self._extract_content(entry)

        if not fetch_full_text or not url:
            return feed_content
        if _word_count(feed_content) >= FULL_TEXT_MIN_WORDS:
            return feed_content

        full_text = await self._fetch_full_text(url)
        if full_text and _word_count(full_text) > _word_count(feed_content):
            return full_text
        return feed_content

    def _extract_content(self, entry: Any) -> str:
        raw_content = ""
        if getattr(entry, "content", None):
            raw_content = str(entry.content[0].get("value", ""))
        elif getattr(entry, "summary", ""):
            raw_content = str(entry.summary)
        elif getattr(entry, "description", ""):
            raw_content = str(entry.description)

        if not raw_content:
            return ""

        if "<" in raw_content and ">" in raw_content:
            extracted = _extract_html_text(raw_content)
            if extracted:
                return extracted

        return _clean_text(raw_content)

    async def _fetch_full_text(self, url: str) -> str:
        """Makale sayfasını indirip ana metni çıkarır — best-effort, hata/timeout → ''."""
        try:
            html = await asyncio.wait_for(
                self._fetch_page(url), timeout=FULL_TEXT_TIMEOUT_SECONDS
            )
        except (URLError, TimeoutError, OSError):
            logger.debug("rss_full_text_fetch_failed", extra={"url": url}, exc_info=True)
            return ""
        return _extract_article_main_text(html)

    async def _fetch_page(self, url: str, *, timeout: int = FULL_TEXT_TIMEOUT_SECONDS) -> str:
        """Makale HTML sayfasını indirir — unit testlerde mock'lanır."""

        def _download() -> str:
            request = Request(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                data = response.read()
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="replace")
                return str(data)

        return await asyncio.to_thread(_download)


def _extract_html_text(html: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return _clean_text(extracted)
    except Exception:
        logger.debug("trafilatura_extract_failed", exc_info=True)

    return _clean_text(_HTML_TAG_RE.sub(" ", html))


def _extract_article_main_text(html: str) -> str:
    """Tam HTML sayfasından ana makale metnini çıkarır (trafilatura).

    Tag-strip fallback YOK — başarısızsa '' döner ki feed özetine düşülsün
    (aksi halde menü/nav metni gövdeye karışır).
    """
    if not html:
        return ""
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return _clean_text(extracted)
    except Exception:
        logger.debug("trafilatura_article_extract_failed", exc_info=True)
    return ""


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _word_count(value: str) -> int:
    return len(value.split())


def _parse_published_at(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed is not None:
            try:
                return datetime.fromtimestamp(timegm(parsed[:6]), tz=UTC)
            except (TypeError, ValueError, OverflowError):
                continue

    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if isinstance(raw, str) and raw.strip():
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=UTC)
                return dt.astimezone(UTC)
            except (TypeError, ValueError):
                continue
    return None

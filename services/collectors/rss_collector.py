"""RSS/Atom feed collector — feedparser + içerik çıkarma."""

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

from services.collectors.base_collector import BaseCollector
from services.collectors.models import RawArticle

logger = logging.getLogger("ygip.collectors.rss")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DEFAULT_USER_AGENT = "YGIP-RSS-Collector/0.1"


class RSSCollector(BaseCollector):
    """RSS/Atom kaynaklarından makale toplar (`Docs/04` §7)."""

    source_type = SourceType.RSS

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

        return self._parse_feed(source, raw_feed)

    async def _fetch(self, url: str, *, timeout: int = 30) -> bytes:
        """Feed XML indirir — unit testlerde mock'lanır."""

        def _download() -> bytes:
            request = Request(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                data = response.read()
                return bytes(data)

        return await asyncio.to_thread(_download)

    def _parse_feed(self, source: Source, raw_feed: str | bytes) -> list[RawArticle]:
        parsed = feedparser.parse(raw_feed)
        if parsed.bozo and not parsed.entries:
            logger.info(
                "rss_parse_empty_or_invalid",
                extra={"source_id": str(source.id)},
            )
            return []

        articles: list[RawArticle] = []
        for entry in parsed.entries:
            article = self._entry_to_article(source, entry)
            if article is not None:
                articles.append(article)
        return articles

    def _entry_to_article(self, source: Source, entry: Any) -> RawArticle | None:
        title = _clean_text(getattr(entry, "title", ""))
        url = _clean_text(getattr(entry, "link", ""))
        content = self._extract_content(entry)

        if not title or not content or not url:
            return None

        external_id = _clean_text(getattr(entry, "id", "")) or url
        published_at = _parse_published_at(entry)
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


def _extract_html_text(html: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return _clean_text(extracted)
    except Exception:
        logger.debug("trafilatura_extract_failed", exc_info=True)

    return _clean_text(_HTML_TAG_RE.sub(" ", html))


def _clean_text(value: str) -> str:
    return " ".join(value.split())


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

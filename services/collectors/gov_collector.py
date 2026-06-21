"""Resmi kaynak collector — TCMB, KAP, Resmi Gazete RSS/Atom parse."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
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
from services.collectors.kap_api_collector import KapApiCollector
from services.collectors.models import RawArticle

logger = logging.getLogger("ygip.collectors.gov")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DEFAULT_USER_AGENT = "YGIP-Gov-Collector/0.1"
_GOV_SUBTYPES = frozenset({"tcmb", "kap", "resmi_gazete"})
_ANNOUNCEMENT_NUMBER_RE = re.compile(r"(\d{4}/\d+)")
_ISSUE_NUMBER_RE = re.compile(r"Say[ıi]:\s*(\d+)", re.IGNORECASE)
_INSTITUTION_BY_SUBTYPE = {
    "tcmb": "TCMB",
    "kap": "KAP",
    "resmi_gazete": "Resmi Gazete",
}
# TCMB Atom feed'i tarihleri Türkçe ay kısaltmasıyla verir ("18 Haz 2026 14:00:00");
# feedparser/parsedate_to_datetime bunu çözemediği için elle parse ediyoruz.
_TR_MONTHS = {
    "oca": 1, "şub": 2, "sub": 2, "mar": 3, "nis": 4, "may": 5, "haz": 6,
    "tem": 7, "ağu": 8, "agu": 8, "eyl": 9, "eki": 10, "kas": 11, "ara": 12,
}
_TR_DATE_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)


class GovCollector(BaseCollector):
    """TCMB, KAP ve Resmi Gazete kaynaklarından duyuru toplar (`Docs/04` §7)."""

    source_type = SourceType.GOV

    def __init__(self, redis_client: Redis | None = None, *, now: datetime | None = None) -> None:
        super().__init__(redis_client)
        self._now = now
        # KAP gibi JSON API kaynakları (parser_type == "api") RSS parse edilemez;
        # bu kaynaklar için ayrı API collector'a delege edilir. Altyapı KAP'ı
        # "gov" schedule'ı ile tetiklediğinden source_type "gov" kalır.
        self._api_collector: KapApiCollector | None = None

    async def collect(self, source: Source) -> list[RawArticle]:
        if _is_api_source(source.config):
            return await self._get_api_collector(source).collect(source)

        endpoint_url = source.config.get("endpoint_url")
        if not isinstance(endpoint_url, str) or not endpoint_url.strip():
            logger.warning(
                "gov_missing_endpoint_url",
                extra={"source_id": str(source.id)},
            )
            return []

        try:
            raw_feed = await self._fetch(endpoint_url.strip())
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "gov_fetch_failed",
                extra={"source_id": str(source.id), "endpoint_url": endpoint_url},
                exc_info=True,
            )
            raise RuntimeError(f"Gov feed alınamadı: {endpoint_url}") from exc

        return self._parse_feed(source, raw_feed)

    def _get_api_collector(self, source: Source) -> KapApiCollector:
        if self._api_collector is None:
            self._api_collector = KapApiCollector(self._redis, now=self._now)
        return self._api_collector

    async def _fetch(self, url: str, *, timeout: int = 30) -> bytes:
        """Feed içeriğini indirir — unit testlerde mock'lanır."""

        def _download() -> bytes:
            request = Request(url, headers={"User-Agent": _DEFAULT_USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                return bytes(response.read())

        return await asyncio.to_thread(_download)

    def _parse_feed(self, source: Source, raw_feed: str | bytes) -> list[RawArticle]:
        decoded = _decode_feed_bytes(raw_feed)
        parsed = feedparser.parse(decoded)
        if parsed.bozo and not parsed.entries:
            logger.info(
                "gov_parse_empty_or_invalid",
                extra={"source_id": str(source.id)},
            )
            return []

        gov_subtype = _resolve_gov_subtype(source.config)
        window_days = resolve_window_days(source.config)

        articles: list[RawArticle] = []
        skipped_old = 0
        for entry in parsed.entries:
            published_at = _parse_published_at(entry)
            if not is_within_window(published_at, window_days, now=self._now):
                skipped_old += 1
                continue
            article = self._entry_to_article(source, entry, gov_subtype, published_at)
            if article is not None:
                articles.append(article)

        if skipped_old:
            logger.info(
                "gov_window_filtered",
                extra={
                    "source_id": str(source.id),
                    "skipped_old": skipped_old,
                    "window_days": window_days,
                },
            )
        return articles

    def _entry_to_article(
        self,
        source: Source,
        entry: Any,
        gov_subtype: str | None,
        published_at: datetime | None,
    ) -> RawArticle | None:
        title = _normalize_text(_clean_text(getattr(entry, "title", "")))
        url = _clean_text(getattr(entry, "link", ""))
        content = self._extract_content(entry)

        # Resmi duyuru feed'lerinde (ör. TCMB Basın Duyuruları) özet alanı çoğu
        # zaman boştur; başlık tek anlamlı içeriktir. İçerik yoksa başlığa düş ki
        # geçerli duyurular validasyonda elenmesin.
        if not content and title:
            content = title

        if not title or not content or not url:
            return None

        external_id = _clean_text(getattr(entry, "id", "")) or url
        metadata = _build_gov_metadata(entry, title, gov_subtype)

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
                return _normalize_text(extracted)

        return _normalize_text(_clean_text(raw_content))


def _is_api_source(config: dict[str, Any]) -> bool:
    """Kaynak RSS yerine JSON API mi? (`parser_type == "api"`)."""
    return str(config.get("parser_type", "")).strip().lower() == "api"


def _resolve_gov_subtype(config: dict[str, Any]) -> str | None:
    for key in ("gov_subtype", "parser"):
        value = config.get(key)
        if isinstance(value, str) and value in _GOV_SUBTYPES:
            return value
    return None


def _build_gov_metadata(entry: Any, title: str, gov_subtype: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"collector": "gov"}
    if gov_subtype:
        metadata["gov_subtype"] = gov_subtype
        metadata["institution"] = _INSTITUTION_BY_SUBTYPE.get(gov_subtype, gov_subtype)

    announcement_number = _extract_announcement_number(title, gov_subtype)
    if announcement_number:
        metadata["announcement_number"] = announcement_number

    issue_number = _extract_issue_number(title, gov_subtype)
    if issue_number:
        metadata["issue_number"] = issue_number

    tags = getattr(entry, "tags", None)
    if tags:
        categories = [
            str(tag.get("term", "")).strip()
            for tag in tags
            if isinstance(tag, dict) and str(tag.get("term", "")).strip()
        ]
        if categories:
            metadata["categories"] = categories

    return metadata


def _extract_announcement_number(title: str, gov_subtype: str | None) -> str | None:
    if gov_subtype not in {"tcmb", "kap", None}:
        return None
    match = _ANNOUNCEMENT_NUMBER_RE.search(title)
    return match.group(1) if match else None


def _extract_issue_number(title: str, gov_subtype: str | None) -> str | None:
    if gov_subtype not in {"resmi_gazete", None}:
        return None
    match = _ISSUE_NUMBER_RE.search(title)
    return match.group(1) if match else None


def _decode_feed_bytes(raw_feed: str | bytes) -> str:
    if isinstance(raw_feed, str):
        return raw_feed

    for encoding in ("utf-8", "iso-8859-9", "windows-1254", "latin-1"):
        try:
            return raw_feed.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_feed.decode("utf-8", errors="replace")


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


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
                pass
            tr_dt = _parse_turkish_date(raw)
            if tr_dt is not None:
                return tr_dt
    return None


def _parse_turkish_date(raw: str) -> datetime | None:
    """`18 Haz 2026 14:00:00` gibi Türkçe ay kısaltmalı tarihleri UTC olarak çözer."""
    match = _TR_DATE_RE.search(raw)
    if not match:
        return None
    day, month_name, year, hour, minute, second = match.groups()
    month = _TR_MONTHS.get(month_name[:3].lower())
    if month is None:
        return None
    try:
        return datetime(
            int(year),
            month,
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            tzinfo=UTC,
        )
    except (TypeError, ValueError):
        return None

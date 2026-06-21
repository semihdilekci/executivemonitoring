"""KAP `memberDisclosureQuery` JSON API collector.

KAP (Kamuyu Aydınlatma Platformu) artık bildirimler için RSS sunmuyor; veriler
`https://www.kap.org.tr/tr/api/memberDisclosureQuery` uç noktasına **POST + JSON
body** ile sorgulanıyor ve JSON dizi olarak dönüyor. `GovCollector` yalnızca
RSS/Atom parse ettiği için bu collector ayrı tutulur ve `parser_type == "api"`
olan gov kaynakları için `GovCollector` tarafından delege edilir.

NOT: KAP yanıt alanlarının adları sürüme göre değişebildiğinden (ör. `title` /
`kapTitle` şirket adı ile bildirim konusu arasında yer değiştirebilir) parse
mantığı bilinçli olarak alan-adı varyantlarına toleranslıdır. Canlı bir yanıtla
(Türkiye içi/izinli IP'den) alan adları doğrulanmalıdır.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from packages.shared.enums import SourceType
from packages.shared.models.source import Source
from redis.asyncio import Redis

from services.collectors.base_collector import BaseCollector
from services.collectors.feed_utils import is_within_window, resolve_window_days
from services.collectors.models import RawArticle

logger = logging.getLogger("ygip.collectors.kap")

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
_KAP_DISCLOSURE_URL = "https://www.kap.org.tr/tr/Bildirim/{index}"
_KAP_DATE_FORMATS = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y")
# KAP yanıtında alan adları sürüme göre değişebiliyor; öncelik sırasıyla denenir.
_COMPANY_KEYS = ("companyName", "kapTitle", "title", "memberName")
_SUBJECT_KEYS = ("title", "kapTitle", "subject", "disclosureType")
_SUMMARY_KEYS = ("summary", "disclosureText", "description")
_STOCK_KEYS = ("stockCodes", "relatedStocks", "stockCode", "ticker")
_INDEX_KEYS = ("disclosureIndex", "index", "id")
_DATE_KEYS = ("publishDate", "date", "kapPublishDate", "publishedDate")


class KapApiCollector(BaseCollector):
    """KAP disclosure JSON API'sinden bildirim toplar (`Docs/04` §7)."""

    source_type = SourceType.GOV

    def __init__(self, redis_client: Redis | None = None, *, now: datetime | None = None) -> None:
        super().__init__(redis_client)
        self._now = now

    async def collect(self, source: Source) -> list[RawArticle]:
        config = source.config or {}
        endpoint_url = config.get("endpoint_url") or config.get("api_url")
        if not isinstance(endpoint_url, str) or not endpoint_url.strip():
            logger.warning("kap_missing_endpoint_url", extra={"source_id": str(source.id)})
            return []

        window_days = resolve_window_days(config)
        body = self._build_request_body(config, window_days)

        try:
            raw_response = await self._post(endpoint_url.strip(), body)
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "kap_fetch_failed",
                extra={"source_id": str(source.id), "endpoint_url": endpoint_url},
                exc_info=True,
            )
            raise RuntimeError(f"KAP API alınamadı: {endpoint_url}") from exc

        return self._parse_response(source, raw_response, window_days)

    async def _post(self, url: str, body: dict[str, Any], *, timeout: int = 30) -> bytes:
        """KAP API'ye POST eder — unit testlerde mock'lanır."""
        payload = json.dumps(body).encode("utf-8")

        def _send() -> bytes:
            request = Request(
                url,
                data=payload,
                method="POST",
                headers={
                    "User-Agent": _DEFAULT_USER_AGENT,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                return bytes(response.read())

        return await asyncio.to_thread(_send)

    def _build_request_body(self, config: dict[str, Any], window_days: int) -> dict[str, Any]:
        """`memberDisclosureQuery` için tarih aralıklı POST gövdesi üretir."""
        reference = self._reference_now()
        from_date = (reference - timedelta(days=window_days)).strftime("%Y-%m-%d")
        to_date = reference.strftime("%Y-%m-%d")
        member_type = config.get("member_type", "IGS")
        return {
            "fromDate": from_date,
            "toDate": to_date,
            "year": "",
            "prd": "",
            "term": "",
            "ruleType": "",
            "bdkReview": "",
            "disclosureClass": "",
            "index": "",
            "market": "",
            "isLate": "",
            "subjectList": [],
            "mkkMemberOidList": [],
            "inactiveMkkMemberOidList": [],
            "bdkMemberOidList": [],
            "mainSector": "",
            "sector": "",
            "subSector": "",
            "memberType": member_type,
            "fromSrc": "true",
            "srcCategory": "",
            "discControlForm": "",
        }

    def _parse_response(
        self, source: Source, raw_response: str | bytes, window_days: int
    ) -> list[RawArticle]:
        disclosures = _decode_disclosures(raw_response)
        if not disclosures:
            logger.info("kap_parse_empty_or_invalid", extra={"source_id": str(source.id)})
            return []

        company_codes = _normalize_company_codes(source.config.get("company_codes"))

        articles: list[RawArticle] = []
        skipped_old = 0
        skipped_company = 0
        for item in disclosures:
            if not isinstance(item, dict):
                continue

            stock_codes = _extract_stock_codes(item)
            if company_codes and not (company_codes & stock_codes):
                skipped_company += 1
                continue

            published_at = _parse_kap_date(item)
            if not is_within_window(published_at, window_days, now=self._now):
                skipped_old += 1
                continue

            article = self._item_to_article(source, item, stock_codes, published_at)
            if article is not None:
                articles.append(article)

        if skipped_old or skipped_company:
            logger.info(
                "kap_filtered",
                extra={
                    "source_id": str(source.id),
                    "skipped_old": skipped_old,
                    "skipped_company": skipped_company,
                    "window_days": window_days,
                },
            )
        return articles

    def _item_to_article(
        self,
        source: Source,
        item: dict[str, Any],
        stock_codes: set[str],
        published_at: datetime | None,
    ) -> RawArticle | None:
        company = _first_str(item, _COMPANY_KEYS)
        subject = _first_str(item, _SUBJECT_KEYS)
        summary = _first_str(item, _SUMMARY_KEYS)
        index = _first_str(item, _INDEX_KEYS)

        title_parts = [part for part in (company, subject) if part]
        title = " - ".join(dict.fromkeys(title_parts))
        # İçerik önceliği: özet > konu > başlık. Resmi bildirimlerde özet çoğu
        # zaman boştur, bu yüzden konuya/başlığa düşülür ki bildirim elenmesin.
        content = summary or subject or title

        url = ""
        if index:
            url = _KAP_DISCLOSURE_URL.format(index=index)

        if not title or not content or not url:
            return None

        metadata: dict[str, Any] = {
            "collector": "gov",
            "gov_subtype": "kap",
            "institution": "KAP",
        }
        if stock_codes:
            metadata["stock_codes"] = sorted(stock_codes)
        if company:
            metadata["company"] = company

        return RawArticle(
            source_id=source.id,
            title=title,
            content=content,
            url=url,
            published_at=published_at,
            metadata=metadata,
            external_id=f"kap-{index}" if index else url,
        )

    def _reference_now(self) -> datetime:
        reference = self._now or datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference


def _decode_disclosures(raw_response: str | bytes) -> list[Any]:
    """KAP yanıtını JSON listesine çözer — gövde dict ise olası liste alanını arar."""
    if isinstance(raw_response, bytes):
        text = raw_response.decode("utf-8", errors="replace")
    else:
        text = raw_response

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("data", "disclosures", "result", "content", "items"):
            value = parsed.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalize_company_codes(raw: Any) -> set[str]:
    if not isinstance(raw, (list, tuple, set)):
        return set()
    return {str(code).strip().upper() for code in raw if str(code).strip()}


def _extract_stock_codes(item: dict[str, Any]) -> set[str]:
    raw = ""
    for key in _STOCK_KEYS:
        value = item.get(key)
        if value:
            raw = str(value)
            break
    if not raw:
        return set()
    # KAP ticker'ları "ULKER, YGYO" ya da "ULKER,YGYO" biçiminde gelebilir.
    parts = raw.replace(";", ",").split(",")
    return {part.strip().upper() for part in parts if part.strip()}


def _parse_kap_date(item: dict[str, Any]) -> datetime | None:
    raw = _first_str(item, _DATE_KEYS)
    if not raw:
        return None
    for fmt in _KAP_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _first_str(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
        if isinstance(value, (int, float)):
            return str(value)
    return ""

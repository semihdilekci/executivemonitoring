"""BaseCollector abstract class — tüm collector'ların temel sözleşmesi."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from packages.shared.enums import SourceType
from packages.shared.models.source import Source
from packages.shared.utils.hashing import compute_content_hash
from redis.asyncio import Redis

from services.collectors.models import NormalizedArticle, RawArticle
from services.collectors.sqs_publisher import SQSPublisherProtocol

logger = logging.getLogger("ygip.collectors.base")

DEDUP_REDIS_KEY = "dedup:hashes"
# Daha önce toplanan URL'ler — tam metin sayfa fetch'ini her döngüde tekrar
# tetiklememek için. TTL ile self-clean olur ve içerik güncellenirse zamanla
# yeniden toplanır.
FETCHED_URL_KEY_PREFIX = "collector:url:"
FETCHED_URL_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 gün


class BaseCollector(ABC):
    """Dış kaynaktan veri çeken collector temel sınıfı (`Docs/04` §7)."""

    source_type: SourceType
    dedup_key: str = DEDUP_REDIS_KEY
    # URL-bazlı fetch cache yalnızca pahalı tam-metin fetch yapan collector'larda
    # (RSS) açılır; email/gov için kapalı kalır.
    track_fetched_urls: bool = False

    def __init__(self, redis_client: Redis | None = None) -> None:
        self._redis = redis_client

    def bind_redis(self, redis_client: Redis | None) -> None:
        """Paylaşılan collector singleton'ına runtime'da redis client bağlar.

        Local runtime COLLECTOR_MAP'teki redis'siz singleton'ları kullandığından,
        URL-cache'in çalışması için batch öncesi redis bağlanır.
        """
        self._redis = redis_client

    @staticmethod
    def _fetched_url_key(url: str) -> str:
        return f"{FETCHED_URL_KEY_PREFIX}{compute_content_hash(url)}"

    async def url_already_collected(self, url: str) -> bool:
        """URL daha önce toplanmış mı? (tam metin fetch'ini atlamak için)."""
        if self._redis is None or not self.track_fetched_urls or not url:
            return False
        return bool(await self._redis.exists(self._fetched_url_key(url)))

    async def mark_url_collected(self, url: str) -> None:
        """URL'yi TTL'li olarak toplandı diye işaretler."""
        if self._redis is None or not self.track_fetched_urls or not url:
            return
        await self._redis.set(
            self._fetched_url_key(url), "1", ex=FETCHED_URL_TTL_SECONDS
        )

    @abstractmethod
    async def collect(self, source: Source) -> list[RawArticle]:
        """Kaynaktan ham veriyi çeker ve RawArticle listesi döner."""

    async def validate(self, raw: RawArticle) -> bool:
        """Zorunlu alanları (title, content, url) kontrol eder."""
        return bool(raw.title.strip() and raw.content.strip() and raw.url.strip())

    async def transform(self, raw: RawArticle) -> NormalizedArticle:
        """RawArticle → NormalizedArticle; hash üretimi ve temel temizleme."""
        content_hash = f"sha256:{compute_content_hash(raw.content)}"
        return NormalizedArticle(
            source_id=raw.source_id,
            source_type=self.source_type.value,
            title=raw.title.strip(),
            content=raw.content.strip(),
            url=raw.url.strip(),
            content_hash=content_hash,
            published_at=raw.published_at,
            collected_at=datetime.now(UTC),
            raw_metadata=dict(raw.metadata),
            external_id=raw.external_id,
        )

    async def dedup_check(self, content_hash: str) -> bool:
        """Redis SET'te hash var mı kontrol eder. Varsa True (duplicate)."""
        if self._redis is None:
            return False
        is_member = await self._redis.sismember(self.dedup_key, content_hash)
        return bool(is_member)

    async def process_articles(
        self,
        source: Source,
        articles: list[RawArticle],
        publisher: SQSPublisherProtocol,
    ) -> int:
        """Validate → dedup → transform → SQS; yayınlanan makale sayısını döner."""
        published = 0
        for raw in articles:
            if not await self.validate(raw):
                logger.debug(
                    "collector_article_skipped_validation",
                    extra={"source_id": str(source.id)},
                )
                continue

            normalized = await self.transform(raw)
            if await self.dedup_check(normalized.content_hash):
                logger.debug(
                    "collector_article_skipped_duplicate",
                    extra={
                        "source_id": str(source.id),
                        "content_hash": normalized.content_hash,
                    },
                )
                continue

            await publisher.publish(normalized)
            published += 1
        return published

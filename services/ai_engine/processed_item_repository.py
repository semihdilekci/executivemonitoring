"""Digest üretimi için processed_items sorguları."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from packages.shared.enums import SourceCategory
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS, ProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.digest_models import DigestArticle, DigestTypeQueryConfig

_ISTANBUL = ZoneInfo("Europe/Istanbul")


class ProcessedItemRepository:
    """Schema-qualified processed_items sorguları."""

    async def list_for_digest(
        self,
        db: AsyncSession,
        *,
        config: DigestTypeQueryConfig,
        period_start: date,
        period_end: date,
        min_relevance_score: float = 0.0,
        limit: int = 50,
    ) -> list[DigestArticle]:
        model = PROCESSED_ITEM_MODELS[config.schema]
        period_start_dt = datetime.combine(period_start, time.min, tzinfo=_ISTANBUL)
        period_end_dt = datetime.combine(period_end, time.max, tzinfo=_ISTANBUL)

        query: Select[tuple[Any, ...]] = (
            select(
                model,
                RawItem.raw_metadata,
                Source.category,
            )
            .join(RawItem, model.raw_item_id == RawItem.id)
            .join(Source, model.source_id == Source.id)
            .where(
                model.relevance_score >= min_relevance_score,
                or_(
                    and_(
                        model.published_at.is_not(None),
                        model.published_at >= period_start_dt,
                        model.published_at <= period_end_dt,
                    ),
                    and_(
                        model.published_at.is_(None),
                        model.processed_at >= period_start_dt,
                        model.processed_at <= period_end_dt,
                    ),
                ),
            )
            .order_by(model.relevance_score.desc(), model.processed_at.desc())
            .limit(limit)
        )

        # Faz 6.4: kaynak ve içerik kategorisi filtreleri OR semantiğiyle uygulanır
        # (örn. fmcg_weekly: source.category=fmcg VEYA content_category=fmcg).
        category_predicates = []
        if config.source_category is not None:
            category_predicates.append(
                Source.category == SourceCategory(config.source_category)
            )
        if config.content_category is not None:
            category_predicates.append(model.content_category == config.content_category)
        if category_predicates:
            query = query.where(or_(*category_predicates))

        result = await db.execute(query)
        rows = result.all()

        articles: list[DigestArticle] = []
        for item, raw_metadata, _category in rows:
            if not isinstance(item, ProcessedItem):
                continue
            if config.topic_keywords and not _topics_match(item.topics, config.topic_keywords):
                continue
            articles.append(_to_digest_article(item, raw_metadata))
        return articles


def _topics_match(topics: list[Any], keywords: tuple[str, ...]) -> bool:
    normalized_topics = {str(topic).casefold() for topic in topics}
    normalized_keywords = {keyword.casefold() for keyword in keywords}
    return bool(normalized_topics & normalized_keywords)


def _to_digest_article(item: ProcessedItem, raw_metadata: dict[str, Any] | None) -> DigestArticle:
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    url_raw = metadata.get("url")
    url = str(url_raw).strip() if isinstance(url_raw, str) and url_raw.strip() else None
    topics = [str(topic) for topic in item.topics] if isinstance(item.topics, list) else []
    return DigestArticle(
        processed_item_id=item.id,
        source_id=item.source_id,
        title=item.title,
        clean_content=item.clean_content,
        relevance_score=item.relevance_score,
        published_at=item.published_at,
        url=url,
        topics=topics,
    )


processed_item_repository = ProcessedItemRepository()

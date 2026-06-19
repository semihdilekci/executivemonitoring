"""API usage log tablosu veri erişimi."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from packages.shared.enums import ApiProvider
from packages.shared.models.api_key import ApiKey
from packages.shared.models.api_usage_log import ApiUsageLog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

UsagePeriod = Literal["daily", "weekly", "monthly"]

_PERIOD_TRUNC: dict[UsagePeriod, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
}


@dataclass(frozen=True, slots=True)
class UsageAggregateRow:
    """Tek bucket + key için özet metrikler."""

    bucket_date: date
    provider: str
    api_key_id: uuid.UUID
    api_key_alias: str
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_latency_ms: float | None
    error_count: int


@dataclass(frozen=True, slots=True)
class UsageRequestTypeRow:
    """İşlem tipi kırılımı."""

    bucket_date: date
    provider: str
    api_key_id: uuid.UUID
    request_type: str
    requests: int
    tokens: int


class ApiUsageRepository:
    """LLM kullanım log CRUD ve aggregation."""

    async def create(
        self,
        db: AsyncSession,
        *,
        api_key_id: uuid.UUID,
        provider: ApiProvider,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_type: str,
        http_status: int = 200,
        latency_ms: int | None = None,
    ) -> ApiUsageLog:
        total_tokens = prompt_tokens + completion_tokens
        log = ApiUsageLog(
            api_key_id=api_key_id,
            provider=provider.value,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            request_type=request_type,
            http_status=http_status,
            latency_ms=latency_ms,
        )
        db.add(log)
        await db.flush()
        return log

    async def aggregate_usage(
        self,
        db: AsyncSession,
        *,
        period: UsagePeriod,
        start_date: date,
        end_date: date,
        provider: ApiProvider | None = None,
        api_key_id: uuid.UUID | None = None,
    ) -> tuple[list[UsageAggregateRow], list[UsageRequestTypeRow]]:
        trunc_unit = _PERIOD_TRUNC[period]
        bucket_expr = func.date_trunc(trunc_unit, ApiUsageLog.created_at).label("bucket")
        start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
        end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)

        filters = [
            ApiUsageLog.created_at >= start_dt,
            ApiUsageLog.created_at < end_exclusive,
        ]
        if provider is not None:
            filters.append(ApiUsageLog.provider == provider.value)
        if api_key_id is not None:
            filters.append(ApiUsageLog.api_key_id == api_key_id)

        summary_query = (
            select(
                bucket_expr,
                ApiUsageLog.provider,
                ApiUsageLog.api_key_id,
                ApiKey.key_alias,
                func.count().label("total_requests"),
                func.coalesce(func.sum(ApiUsageLog.prompt_tokens), 0).label("total_prompt_tokens"),
                func.coalesce(func.sum(ApiUsageLog.completion_tokens), 0).label(
                    "total_completion_tokens"
                ),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
                func.avg(ApiUsageLog.latency_ms).label("avg_latency_ms"),
                func.coalesce(
                    func.sum(case((ApiUsageLog.http_status != 200, 1), else_=0)),
                    0,
                ).label("error_count"),
            )
            .join(ApiKey, ApiKey.id == ApiUsageLog.api_key_id)
            .where(*filters)
            .group_by(
                bucket_expr,
                ApiUsageLog.provider,
                ApiUsageLog.api_key_id,
                ApiKey.key_alias,
            )
            .order_by(bucket_expr.desc(), ApiUsageLog.provider.asc(), ApiKey.key_alias.asc())
        )
        summary_result = await db.execute(summary_query)
        summary_rows = [
            UsageAggregateRow(
                bucket_date=row.bucket.date(),
                provider=row.provider,
                api_key_id=row.api_key_id,
                api_key_alias=row.key_alias,
                total_requests=int(row.total_requests),
                total_prompt_tokens=int(row.total_prompt_tokens),
                total_completion_tokens=int(row.total_completion_tokens),
                total_tokens=int(row.total_tokens),
                avg_latency_ms=(
                    float(row.avg_latency_ms) if row.avg_latency_ms is not None else None
                ),
                error_count=int(row.error_count),
            )
            for row in summary_result.all()
        ]

        breakdown_query = (
            select(
                bucket_expr,
                ApiUsageLog.provider,
                ApiUsageLog.api_key_id,
                ApiUsageLog.request_type,
                func.count().label("requests"),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
            )
            .where(*filters)
            .group_by(
                bucket_expr,
                ApiUsageLog.provider,
                ApiUsageLog.api_key_id,
                ApiUsageLog.request_type,
            )
        )
        breakdown_result = await db.execute(breakdown_query)
        breakdown_rows = [
            UsageRequestTypeRow(
                bucket_date=row.bucket.date(),
                provider=row.provider,
                api_key_id=row.api_key_id,
                request_type=row.request_type,
                requests=int(row.requests),
                tokens=int(row.tokens),
            )
            for row in breakdown_result.all()
        ]
        return summary_rows, breakdown_rows


api_usage_repository = ApiUsageRepository()

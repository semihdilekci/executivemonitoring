"""LLM API kullanım izleme iş mantığı."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from packages.shared.enums import ApiProvider, LlmRequestType
from packages.shared.models.api_usage_log import ApiUsageLog
from services.ai_engine.models import LLMResponse
from services.ai_engine.providers.base import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.repositories.api_usage_repository import (
    ApiUsageRepository,
    UsagePeriod,
    UsageRequestTypeRow,
    api_usage_repository,
)
from apps.api.schemas.api_key import (
    ApiUsageStatsResponse,
    RequestTypeStats,
    UsageStatsRow,
)

_DEFAULT_STATS_LOOKBACK_DAYS = 30


class ApiUsageService:
    """Usage log persist ve admin istatistik aggregation."""

    def __init__(self, usage_repo: ApiUsageRepository | None = None) -> None:
        self._usage_repo = usage_repo or api_usage_repository

    async def log_usage(
        self,
        db: AsyncSession,
        *,
        api_key_id: uuid.UUID,
        provider: ApiProvider,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        operation_type: LlmRequestType | str,
        http_status: int = 200,
        latency_ms: int | None = None,
    ) -> ApiUsageLog:
        request_type = (
            operation_type.value
            if isinstance(operation_type, LlmRequestType)
            else operation_type
        )
        return await self._usage_repo.create(
            db,
            api_key_id=api_key_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            request_type=request_type,
            http_status=http_status,
            latency_ms=latency_ms,
        )

    async def log_from_llm_response(
        self,
        db: AsyncSession,
        provider: LLMProvider,
        response: LLMResponse,
        operation_type: LlmRequestType | str,
    ) -> ApiUsageLog:
        key_id = response.api_key_id or provider.key_id
        return await self.log_usage(
            db,
            api_key_id=key_id,
            provider=provider.provider,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            operation_type=operation_type,
            http_status=200,
            latency_ms=response.latency_ms,
        )

    async def get_usage_stats(
        self,
        db: AsyncSession,
        *,
        period: UsagePeriod = "daily",
        provider: ApiProvider | None = None,
        api_key_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ApiUsageStatsResponse:
        today = datetime.now(tz=UTC).date()
        resolved_end = end_date or today
        resolved_start = start_date or (resolved_end - timedelta(days=_DEFAULT_STATS_LOOKBACK_DAYS))

        summary_rows, breakdown_rows = await self._usage_repo.aggregate_usage(
            db,
            period=period,
            start_date=resolved_start,
            end_date=resolved_end,
            provider=provider,
            api_key_id=api_key_id,
        )
        by_request_type = _group_request_type_breakdown(breakdown_rows)
        data = [
            UsageStatsRow(
                date=row.bucket_date,
                provider=ApiProvider(row.provider),
                api_key_alias=row.api_key_alias,
                total_requests=row.total_requests,
                total_prompt_tokens=row.total_prompt_tokens,
                total_completion_tokens=row.total_completion_tokens,
                total_tokens=row.total_tokens,
                avg_latency_ms=(
                    int(round(row.avg_latency_ms)) if row.avg_latency_ms is not None else None
                ),
                error_count=row.error_count,
                by_request_type=by_request_type.get(
                    (row.bucket_date, row.provider, row.api_key_id),
                    {},
                ),
            )
            for row in summary_rows
        ]
        return ApiUsageStatsResponse(period=period, data=data)


def _group_request_type_breakdown(
    rows: list[UsageRequestTypeRow],
) -> dict[tuple[date, str, uuid.UUID], dict[str, RequestTypeStats]]:
    grouped: dict[tuple[date, str, uuid.UUID], dict[str, RequestTypeStats]] = {}
    for row in rows:
        key = (row.bucket_date, row.provider, row.api_key_id)
        bucket = grouped.setdefault(key, {})
        bucket[row.request_type] = RequestTypeStats(requests=row.requests, tokens=row.tokens)
    return grouped


api_usage_service = ApiUsageService()

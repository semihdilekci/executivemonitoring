"""Pipeline monitoring API şemaları (Faz 6.1) — `Docs/03` §11.5."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from packages.shared.enums import (
    DigestType,
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.schemas.common import PaginatedResponse


class TriggerPipelineRequest(BaseModel):
    """Pipeline tetikleme isteği — `collect_pipeline` | `digest_update` (`Docs/03` §11.5).

    `source_types` yalnızca `collect_pipeline` için; `digest_type`/`period_*`/
    `send_notification` yalnızca `digest_update` için (kurallar `Docs/03` §7 ile aynı).
    Kaynak tipi **değer** doğrulaması (rss/email/gov/all) servis katmanında yapılır —
    geçersiz değer `INVALID_SOURCE_TYPE` (422) döner.
    """

    run_type: PipelineRunType
    source_types: list[str] | None = None
    digest_type: DigestType | None = None
    period_start: date | None = None
    period_end: date | None = None
    send_notification: bool = True

    @model_validator(mode="after")
    def _validate_by_run_type(self) -> TriggerPipelineRequest:
        if self.run_type == PipelineRunType.COLLECT_PIPELINE:
            if not self.source_types:
                raise ValueError("collect_pipeline için source_types zorunludur.")
        else:  # digest_update
            missing = [
                name
                for name in ("digest_type", "period_start", "period_end")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    "digest_update için zorunlu alan(lar): " + ", ".join(missing)
                )
            if (
                self.period_start is not None
                and self.period_end is not None
                and self.period_end < self.period_start
            ):
                raise ValueError("period_end, period_start tarihinden önce olamaz.")
        return self


class TriggerPipelineResponse(BaseModel):
    """Asenkron tetikleme yanıtı (202)."""

    id: UUID
    run_type: PipelineRunType
    status: PipelineRunStatus
    message: str = "Pipeline çalıştırması başlatıldı."


class PipelineStepResponse(BaseModel):
    """Bir aşamanın adım detayı (`sequence` sırasında)."""

    stage: PipelineStage
    status: PipelineStepStatus
    sequence: int
    items_in: int
    items_out: int
    items_failed: int
    detail: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PipelineRunSummary(BaseModel):
    """Run liste öğesi — `current_stage` yalnızca `running` durumda dolu."""

    id: UUID
    run_type: PipelineRunType
    status: PipelineRunStatus
    source_types: list[Any] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    triggered_by_name: str | None = None
    current_stage: PipelineStage | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class PipelineRunListResponse(PaginatedResponse[PipelineRunSummary]):
    """Sayfalanmış run geçmişi."""


class PipelineRunDetail(PipelineRunSummary):
    """Run detayı — aşama adımları dahil (polling endpoint'i)."""

    params: dict[str, Any] = Field(default_factory=dict)
    error_summary: str | None = None
    steps: list[PipelineStepResponse] = Field(default_factory=list)


class CancelPipelineResponse(BaseModel):
    """İptal yanıtı (200)."""

    id: UUID
    status: PipelineRunStatus

"""Pipeline run step ORM modeli — `pipeline_run_steps` tablosu (Faz 6.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import PipelineStage, PipelineStepStatus
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.pipeline_run import PipelineRun

pipeline_stage_enum = Enum(
    PipelineStage,
    name="pipeline_stage_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

pipeline_step_status_enum = Enum(
    PipelineStepStatus,
    name="pipeline_step_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class PipelineRunStep(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Bir run'ın aşama bazlı adım kaydı (collect/ingest/process/digest)."""

    __tablename__ = "pipeline_run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "stage", name="uq_pipeline_run_steps_run_id_stage"),
        Index("idx_pipeline_run_steps_run_id", "run_id"),
        Index("idx_pipeline_run_steps_status", "status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[PipelineStage] = mapped_column(pipeline_stage_enum, nullable=False)
    status: Mapped[PipelineStepStatus] = mapped_column(
        pipeline_step_status_enum,
        nullable=False,
        server_default=PipelineStepStatus.PENDING.value,
    )
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    items_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[PipelineRun] = relationship("PipelineRun", back_populates="steps")

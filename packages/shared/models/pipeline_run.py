"""Pipeline run ORM modeli — `pipeline_runs` tablosu (Faz 6.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import PipelineRunStatus, PipelineRunType
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.pipeline_run_step import PipelineRunStep
    from packages.shared.models.user import User

pipeline_run_type_enum = Enum(
    PipelineRunType,
    name="pipeline_run_type_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

pipeline_run_status_enum = Enum(
    PipelineRunStatus,
    name="pipeline_run_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class PipelineRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Admin'in manuel tetiklediği pipeline çalıştırmasının tarihsel kaydı."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("idx_pipeline_runs_status", "status"),
        Index("idx_pipeline_runs_run_type", "run_type"),
        Index("idx_pipeline_runs_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_pipeline_runs_triggered_by", "triggered_by"),
    )

    run_type: Mapped[PipelineRunType] = mapped_column(pipeline_run_type_enum, nullable=False)
    status: Mapped[PipelineRunStatus] = mapped_column(
        pipeline_run_status_enum,
        nullable=False,
        server_default=PipelineRunStatus.PENDING.value,
    )
    source_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    triggered_by_user: Mapped[User | None] = relationship("User")
    steps: Mapped[list[PipelineRunStep]] = relationship(
        "PipelineRunStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="PipelineRunStep.sequence",
    )

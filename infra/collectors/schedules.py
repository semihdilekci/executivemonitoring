"""Collector EventBridge zamanlama ve Lambda kaynak profilleri."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CollectorScheduleConfig:
    """Tek collector tipi için schedule + Lambda boyutları."""

    source_type: str
    rate_minutes: int
    memory_mb: int
    timeout_seconds: int


COLLECTOR_SCHEDULES: tuple[CollectorScheduleConfig, ...] = (
    CollectorScheduleConfig(source_type="rss", rate_minutes=15, memory_mb=256, timeout_seconds=60),
    CollectorScheduleConfig(
        source_type="email", rate_minutes=60, memory_mb=512, timeout_seconds=120
    ),
    CollectorScheduleConfig(source_type="gov", rate_minutes=30, memory_mb=256, timeout_seconds=60),
)

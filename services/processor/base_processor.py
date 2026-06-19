"""BaseProcessor chain pattern — pipeline adımlarının temel sözleşmesi."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from services.processor.models import (
    ProcessedResult,
    ProcessorContext,
    ProcessorInput,
    ProcessorOutput,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger("ygip.processor.chain")


class ProcessorStepError(Exception):
    """Pipeline adımı işlenirken beklenmeyen hata."""

    def __init__(self, processor_name: str, cause: Exception) -> None:
        self.processor_name = processor_name
        self.cause = cause
        super().__init__(f"{processor_name} failed: {cause}")


class BaseProcessor(ABC):
    """Tek pipeline adımı — `None` dönerse zincir durur (skip/discard)."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        """Context'i işler; `None` = duplicate/discard, exception = DLQ path."""

    async def safe_process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        """Adım hatasını ProcessorStepError olarak sarar."""
        try:
            return await self.process(ctx)
        except Exception as exc:
            raise ProcessorStepError(self.name, exc) from exc


class ProcessorChain:
    """Sıralı processor zinciri — dedup → normalize → gate → … (`Docs/04` §8)."""

    def __init__(self, processors: list[BaseProcessor] | None = None) -> None:
        self._processors = list(processors or [])

    @property
    def processors(self) -> list[BaseProcessor]:
        return list(self._processors)

    async def run(self, item: ProcessorInput) -> ProcessedResult:
        """Girdiyi zincirden geçirir; skip veya başarı döner."""
        ctx = ProcessorContext(input=item, data=ProcessorOutput.from_input(item))

        for processor in self._processors:
            logger.debug(
                "processor_step_start",
                extra={
                    "processor": processor.name,
                    "source_id": str(item.source_id),
                    "content_hash": item.content_hash,
                },
            )
            result = await processor.safe_process(ctx)
            if result is None:
                logger.info(
                    "processor_pipeline_skipped",
                    extra={
                        "processor": processor.name,
                        "source_id": str(item.source_id),
                        "content_hash": item.content_hash,
                    },
                )
                return ProcessedResult(
                    status="skipped",
                    skip_reason=f"discarded_by_{processor.name}",
                    processor_name=processor.name,
                )
            ctx.data = result

        logger.info(
            "processor_pipeline_success",
            extra={
                "source_id": str(item.source_id),
                "content_hash": item.content_hash,
            },
        )
        return ProcessedResult(status="success", output=ctx.data)


def with_dedup_first(
    redis: Redis,
    processors: list[BaseProcessor] | None = None,
) -> ProcessorChain:
    """Dedup'ı zincirin ilk adımı olarak kaydeder (`Docs/04` §8.6)."""
    from services.processor.dedup_processor import DedupProcessor

    steps: list[BaseProcessor] = [DedupProcessor(redis)]
    if processors:
        steps.extend(processors)
    return ProcessorChain(steps)

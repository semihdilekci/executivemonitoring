"""Chunker processor — token bazlı metin parçalama (`Docs/04` §8.5)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass

import tiktoken

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.chunker")

DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 64
DEFAULT_ENCODING = "cl100k_base"


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Tek metin parçası metadata."""

    chunk_index: int
    chunk_text: str
    token_count: int


def split_text_into_chunks(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    encoding_name: str = DEFAULT_ENCODING,
) -> list[TextChunk]:
    """Metni overlap'lı token chunk'larına böler."""
    stripped = text.strip()
    if not stripped:
        return []

    if max_tokens <= 0:
        return []
    if overlap_tokens >= max_tokens:
        overlap_tokens = max(0, max_tokens // 4)

    encoder = tiktoken.get_encoding(encoding_name)
    tokens = encoder.encode(stripped)
    if not tokens:
        return []

    if len(tokens) <= max_tokens:
        return [TextChunk(chunk_index=0, chunk_text=stripped, token_count=len(tokens))]

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        piece = tokens[start:end]
        chunks.append(
            TextChunk(
                chunk_index=index,
                chunk_text=encoder.decode(piece),
                token_count=len(piece),
            )
        )
        if end >= len(tokens):
            break
        start = end - overlap_tokens
        index += 1

    return chunks


class ChunkerProcessor(BaseProcessor):
    """Normalize edilmiş içeriği RAG chunk'larına böler."""

    def __init__(
        self,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> None:
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        clean_raw = ctx.data.extras.get("clean_content", ctx.data.content)
        content = clean_raw if isinstance(clean_raw, str) else ctx.data.content

        chunks = await asyncio.to_thread(
            split_text_into_chunks,
            content,
            max_tokens=self._max_tokens,
            overlap_tokens=self._overlap_tokens,
        )
        if not chunks:
            logger.info(
                "processor_chunk_empty_content",
                extra={"source_id": str(ctx.data.source_id)},
            )
            return None

        ctx.data.extras["chunks"] = [asdict(chunk) for chunk in chunks]
        logger.debug(
            "processor_chunk_success",
            extra={
                "source_id": str(ctx.data.source_id),
                "chunk_count": len(chunks),
            },
        )
        return ctx.data

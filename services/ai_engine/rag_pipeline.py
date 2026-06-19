"""RAG chatbot pipeline — embedding → pgvector → LLM."""

from __future__ import annotations

from packages.shared.enums import LlmRequestType
from packages.shared.models.system_setting import SystemSetting
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.chunk_repository import ContentChunkRepository, content_chunk_repository
from services.ai_engine.context_builder import ContextBuilder
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.rag_models import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMPTY_CONTEXT_ANSWER,
    RAG_SYSTEM_PROMPT,
    SETTINGS_KEY_SIMILARITY_THRESHOLD,
    ChunkSearchResult,
    RagResult,
    RagSource,
)
from services.processor.embedding_service import EmbeddingService


class RAGPipeline:
    """Soru → embedding → hybrid search → context → LLM yanıtı."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_client: LLMClient,
        *,
        chunk_repository: ContentChunkRepository | None = None,
        context_builder: ContextBuilder | None = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self._embedding = embedding_service
        self._llm = llm_client
        self._chunk_repo = chunk_repository or content_chunk_repository
        self._context_builder = context_builder or ContextBuilder()
        self._similarity_threshold = similarity_threshold

    async def ask(
        self,
        db: AsyncSession,
        question: str,
        *,
        similarity_threshold: float | None = None,
    ) -> RagResult:
        """RAG akışını çalıştırır; boş context'te LLM çağrılmaz."""
        threshold = similarity_threshold
        if threshold is None:
            threshold = await self._resolve_threshold(db)

        embeddings = await self._embedding.embed_batch([question])
        if not embeddings:
            return self._empty_result()

        ranked = await self._chunk_repo.similarity_search(
            db,
            embeddings[0],
            threshold=threshold,
        )
        if not ranked:
            return self._empty_result()

        selected = self._context_builder.select_chunks(ranked)
        if not selected:
            return self._empty_result()

        context = self._context_builder.build_context(selected)
        prompt = self._context_builder.build_prompt(context=context, question=question)
        response = await self._llm.complete(
            prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            operation_type=LlmRequestType.CHATBOT,
        )

        return RagResult(
            answer=response.text,
            sources=extract_sources(selected),
            model=response.model,
            tokens_used=response.usage.total_tokens,
        )

    async def _resolve_threshold(self, db: AsyncSession) -> float:
        result = await db.execute(
            select(SystemSetting.value).where(
                SystemSetting.key == SETTINGS_KEY_SIMILARITY_THRESHOLD
            )
        )
        value = result.scalar_one_or_none()
        if isinstance(value, (int, float)):
            return float(value)
        return self._similarity_threshold

    @staticmethod
    def _empty_result() -> RagResult:
        return RagResult(
            answer=EMPTY_CONTEXT_ANSWER,
            sources=[],
            model="",
            tokens_used=0,
        )


def extract_sources(chunks: list[ChunkSearchResult]) -> list[RagSource]:
    """Seçilen chunk'lardan API kaynak listesi üretir."""
    sources: list[RagSource] = []
    for item in chunks:
        sources.append(
            RagSource(
                chunk_id=item.chunk.id,
                processed_item_id=item.chunk.processed_item_id,
                title=item.title,
                url=item.url,
                score=round(item.hybrid_score, 4),
            )
        )
    return sources

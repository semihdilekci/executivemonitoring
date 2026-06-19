"""RAG context assembly — chunk seçimi ve LLM prompt formatı."""

from __future__ import annotations

from services.ai_engine.rag_models import (
    DEFAULT_MAX_CONTEXT_CHUNKS,
    DEFAULT_MAX_CONTEXT_TOKENS,
    ChunkSearchResult,
)


class ContextBuilder:
    """Hybrid skorlu chunk listesinden token-limitli context üretir."""

    def __init__(
        self,
        *,
        max_chunks: int = DEFAULT_MAX_CONTEXT_CHUNKS,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> None:
        self._max_chunks = max_chunks
        self._max_tokens = max_tokens

    def select_chunks(self, ranked: list[ChunkSearchResult]) -> list[ChunkSearchResult]:
        """En yüksek hybrid skorlu chunk'ları token limitine sığdırır."""
        selected = list(ranked[: self._max_chunks])
        while selected and self._total_tokens(selected) > self._max_tokens:
            selected.pop()
        return selected

    def build_context(self, chunks: list[ChunkSearchResult]) -> str:
        """Chunk metinlerini kaynak metadata ile birleştirir."""
        if not chunks:
            return ""

        parts: list[str] = []
        for index, item in enumerate(chunks, start=1):
            published = (
                item.published_at.isoformat()
                if item.published_at is not None
                else "bilinmiyor"
            )
            url = item.url or "yok"
            parts.append(
                f"--- Kaynak {index} ---\n"
                f"Başlık: {item.title}\n"
                f"URL: {url}\n"
                f"Tarih: {published}\n"
                f"İçerik:\n{item.chunk.chunk_text}\n"
            )
        return "\n".join(parts)

    def build_prompt(self, *, context: str, question: str) -> str:
        """LLM user prompt — context + soru."""
        return f"Context:\n{context}\n\nSoru: {question}"

    @staticmethod
    def _total_tokens(chunks: list[ChunkSearchResult]) -> int:
        return sum(item.chunk.token_count for item in chunks)

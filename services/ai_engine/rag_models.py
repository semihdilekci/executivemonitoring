"""RAG pipeline veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from packages.shared.models.content_chunk import ContentChunk

DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_MAX_CONTEXT_CHUNKS = 10
DEFAULT_MAX_CONTEXT_TOKENS = 8000
SETTINGS_KEY_SIMILARITY_THRESHOLD = "chatbot_similarity_threshold"

RAG_SYSTEM_PROMPT = (
    "Sen YıldızHolding Global Intelligence Platform'un AI asistanısın. "
    "Yalnızca sağlanan context'ten yanıt ver. "
    "Context'te bilgi yoksa 'Bu konuda elimde yeterli veri yok' de. "
    "Her yanıtın sonunda kullandığın kaynakları listele."
)

EMPTY_CONTEXT_ANSWER = "Bu konuda elimde yeterli veri yok."


@dataclass(frozen=True, slots=True)
class ChunkSearchResult:
    """Hybrid skor ile sıralanmış chunk arama sonucu."""

    chunk: ContentChunk
    cosine_similarity: float
    hybrid_score: float
    title: str
    url: str | None
    published_at: datetime | None
    relevance_score: float


@dataclass(frozen=True, slots=True)
class RagSource:
    """Chatbot yanıtı kaynak referansı — `Docs/03` §8."""

    chunk_id: UUID
    processed_item_id: UUID
    title: str
    url: str | None
    score: float


@dataclass(frozen=True, slots=True)
class RagResult:
    """RAG pipeline çıktısı — iter 8 HTTP katmanına aktarılır."""

    answer: str
    sources: list[RagSource]
    model: str
    tokens_used: int

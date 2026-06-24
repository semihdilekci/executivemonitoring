"""Content chunk ORM modeli — `content_chunks` tablosu (pgvector)."""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIMENSION = 1536


class ContentChunk(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """RAG için embedding'lenmiş metin parçası.

    Faz 6.4 (ADR-0002) haber konsolidasyonu sonrası tüm parçalar `news.processed_items`'a
    bağlanır; `processed_item_id` artık native FK ile garantilenir (`010` migration,
    `Docs/02` §4.5). Konsolidasyon öncesi çoklu schema partition nedeniyle FK yoktu.
    """

    __tablename__ = "content_chunks"
    __table_args__ = (
        UniqueConstraint(
            "processed_item_id",
            "chunk_index",
            name="uq_content_chunks_processed_item_id_chunk_index",
        ),
        Index("idx_content_chunks_processed_item_id", "processed_item_id"),
    )

    processed_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "news.processed_items.id",
            ondelete="CASCADE",
            name="fk_content_chunks_processed_item_id",
        ),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)

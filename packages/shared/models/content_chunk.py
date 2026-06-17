"""Content chunk ORM modeli — `content_chunks` tablosu (pgvector)."""

from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

EMBEDDING_DIMENSION = 1536


class ContentChunk(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """RAG için embedding'lenmiş metin parçası.

    `processed_item_id` mantıksal FK — native constraint yok (5 schema partition).
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

    processed_item_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)

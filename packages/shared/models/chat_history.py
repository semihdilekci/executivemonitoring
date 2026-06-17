"""Chat history ORM modeli — `chat_history` tablosu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.user import User


class ChatHistory(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """RAG chatbot soru/yanıt kaydı."""

    __tablename__ = "chat_history"
    __table_args__ = (
        Index("idx_chat_history_user_id", "user_id"),
        Index(
            "idx_chat_history_created_at",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="chat_history")

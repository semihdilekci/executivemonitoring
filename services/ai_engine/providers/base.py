"""LLM provider soyut tabanı."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from packages.shared.enums import ApiProvider

from services.ai_engine.models import LLMResponse


class LLMProvider(ABC):
    """Groq/Gemini gibi LLM sağlayıcıları için ortak arayüz."""

    @property
    @abstractmethod
    def provider(self) -> ApiProvider:
        """Sağlayıcı enum değeri."""

    @property
    @abstractmethod
    def key_id(self) -> UUID:
        """İlişkili `api_keys.id` — usage log için."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Provider kullanılabilir mi."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Prompt tamamlama — başarıda `LLMResponse` döner."""

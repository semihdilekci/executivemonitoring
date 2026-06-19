"""AI engine veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from packages.shared.enums import ApiProvider


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """LLM token kullanım özeti."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Başarılı LLM tamamlama yanıtı."""

    text: str
    usage: TokenUsage
    provider: ApiProvider
    model: str
    latency_ms: int
    api_key_id: UUID | None = None

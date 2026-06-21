"""LLM client factory — DB aktif key'ler + usage log hook (`apps/api` katmanı)."""

from __future__ import annotations

import os

from packages.shared.enums import ApiProvider, LlmRequestType
from services.ai_engine.llm_client import LLMClient, UsageLogHook
from services.ai_engine.models import LLMResponse
from services.ai_engine.providers.base import LLMProvider
from services.ai_engine.providers.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiProvider
from services.ai_engine.providers.groq_provider import GroqProvider
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService


def _gemini_model() -> str:
    """Aktif Gemini modeli — `GEMINI_MODEL` env override'ı, yoksa güncel GA varsayılan."""
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL


async def list_llm_providers(
    db: AsyncSession,
    api_key_service: ApiKeyService,
) -> list[LLMProvider]:
    """Aktif API key'lerden provider listesi oluşturur."""
    decrypted = await api_key_service.list_active_decrypted(db)
    providers: list[LLMProvider] = []
    for api_key, plaintext in decrypted:
        if api_key.provider == ApiProvider.GROQ:
            providers.append(GroqProvider(api_key=plaintext, key_id=api_key.id))
        elif api_key.provider == ApiProvider.GEMINI:
            providers.append(
                GeminiProvider(
                    api_key=plaintext, key_id=api_key.id, model=_gemini_model()
                )
            )
    return providers


def make_llm_usage_hook(
    db: AsyncSession,
    api_usage_service: ApiUsageService,
) -> UsageLogHook:
    """Başarılı LLM çağrısı sonrası usage log hook'u."""

    async def hook(
        provider: LLMProvider,
        response: LLMResponse,
        operation_type: LlmRequestType | str,
    ) -> None:
        await api_usage_service.log_from_llm_response(
            db,
            provider,
            response,
            operation_type=operation_type,
        )

    return hook


async def build_llm_client(
    db: AsyncSession,
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
    *,
    providers: list[LLMProvider] | None = None,
) -> LLMClient:
    """Aktif API key'lerden provider listesi + usage log hook ile LLM client."""
    resolved_providers = providers
    if resolved_providers is None:
        resolved_providers = await list_llm_providers(db, api_key_service)
    usage_hook = make_llm_usage_hook(db, api_usage_service)
    return LLMClient(providers=resolved_providers, usage_log_hook=usage_hook)

"""LLM client unit testleri — mock provider, fallback, provider HTTP mock."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from packages.shared.enums import ApiProvider
from services.ai_engine.exceptions import (
    AllProvidersFailedError,
    NoActiveLLMProviderError,
    RateLimitError,
    ServiceUnavailableError,
)
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.providers.anthropic_provider import AnthropicProvider
from services.ai_engine.providers.base import LLMProvider
from services.ai_engine.providers.gemini_provider import GeminiProvider
from services.ai_engine.providers.groq_provider import GroqProvider


def _sample_response(*, provider: ApiProvider, text: str = "Yanıt") -> LLMResponse:
    if provider == ApiProvider.GROQ:
        model = "groq/llama-3.1-70b-versatile"
    else:
        model = "gemini/gemini-2.5-flash-lite"
    return LLMResponse(
        text=text,
        usage=TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
        provider=provider,
        model=model,
        latency_ms=42,
        api_key_id=uuid.uuid4(),
    )


class MockProvider(LLMProvider):
    """Test için yapılandırılabilir sağlayıcı."""

    def __init__(
        self,
        *,
        provider: ApiProvider,
        key_id: uuid.UUID | None = None,
        is_active: bool = True,
        raises: Exception | None = None,
        returns: LLMResponse | None = None,
    ) -> None:
        self._provider = provider
        self._key_id = key_id or uuid.uuid4()
        self._is_active = is_active
        self.raises = raises
        self.returns = returns or _sample_response(provider=provider)
        self.call_count = 0

    @property
    def provider(self) -> ApiProvider:
        return self._provider

    @property
    def key_id(self) -> uuid.UUID:
        return self._key_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.call_count += 1
        if self.raises is not None:
            raise self.raises
        return self.returns


@pytest.mark.asyncio
async def test_llm_client_success() -> None:
    provider = MockProvider(provider=ApiProvider.GROQ)
    client = LLMClient(providers=[provider])

    response = await client.complete("test prompt", system_prompt="sistem")

    assert response.text == "Yanıt"
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_llm_client_falls_back_on_rate_limit() -> None:
    provider_a = MockProvider(provider=ApiProvider.GROQ, raises=RateLimitError())
    provider_b = MockProvider(
        provider=ApiProvider.GEMINI,
        returns=_sample_response(provider=ApiProvider.GEMINI, text="İkinci"),
    )
    client = LLMClient(providers=[provider_a, provider_b])

    response = await client.complete("test prompt")

    assert response.text == "İkinci"
    assert provider_a.call_count == 1
    assert provider_b.call_count == 1


@pytest.mark.asyncio
async def test_llm_client_falls_back_on_service_unavailable() -> None:
    provider_a = MockProvider(provider=ApiProvider.GROQ, raises=ServiceUnavailableError())
    provider_b = MockProvider(provider=ApiProvider.GEMINI)
    client = LLMClient(providers=[provider_a, provider_b])

    response = await client.complete("test prompt")

    assert response.text == "Yanıt"
    assert provider_b.call_count == 1


@pytest.mark.asyncio
async def test_llm_client_raises_when_all_providers_fail() -> None:
    provider_a = MockProvider(provider=ApiProvider.GROQ, raises=RateLimitError())
    provider_b = MockProvider(provider=ApiProvider.GEMINI, raises=ServiceUnavailableError())
    client = LLMClient(providers=[provider_a, provider_b])

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await client.complete("test prompt")

    assert exc_info.value.error_code == "ALL_LLM_PROVIDERS_FAILED"


@pytest.mark.asyncio
async def test_llm_client_raises_when_no_active_providers() -> None:
    inactive = MockProvider(provider=ApiProvider.GROQ, is_active=False)
    client = LLMClient(providers=[inactive])

    with pytest.raises(NoActiveLLMProviderError) as exc_info:
        await client.complete("test prompt")

    assert exc_info.value.error_code == "NO_ACTIVE_LLM_PROVIDER"


@pytest.mark.asyncio
async def test_llm_client_skips_inactive_providers() -> None:
    inactive = MockProvider(provider=ApiProvider.GROQ, is_active=False)
    active = MockProvider(
        provider=ApiProvider.GEMINI,
        returns=_sample_response(provider=ApiProvider.GEMINI, text="Aktif"),
    )
    client = LLMClient(providers=[inactive, active])

    response = await client.complete("test prompt")

    assert response.text == "Aktif"
    assert inactive.call_count == 0
    assert active.call_count == 1


@pytest.mark.asyncio
async def test_llm_client_usage_hook_called_on_success() -> None:
    provider = MockProvider(provider=ApiProvider.GROQ)
    usage_hook = AsyncMock()
    client = LLMClient(providers=[provider], usage_log_hook=usage_hook)

    await client.complete("test prompt", operation_type="chatbot")

    usage_hook.assert_awaited_once()
    hook_provider, hook_response, hook_operation = usage_hook.await_args.args
    assert hook_provider is provider
    assert hook_response.text == "Yanıt"
    assert hook_operation == "chatbot"


@pytest.mark.asyncio
async def test_groq_provider_complete_success() -> None:
    key_id = uuid.uuid4()
    provider = GroqProvider(api_key="gsk-test-key", key_id=key_id)
    response_body = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "Groq yanıtı"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10},
            "model": "llama-3.1-70b-versatile",
        },
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=response_body,
    ) as mock_post:
        response = await provider.complete("merhaba", system_prompt="sistem")

    assert response.text == "Groq yanıtı"
    assert response.provider == ApiProvider.GROQ
    assert response.api_key_id == key_id
    assert response.usage.total_tokens == 10
    mock_post.assert_awaited_once()
    assert "gsk-test-key" not in str(response)


@pytest.mark.asyncio
async def test_groq_provider_maps_429_to_rate_limit() -> None:
    provider = GroqProvider(api_key="gsk-test-key", key_id=uuid.uuid4())
    response_body = httpx.Response(
        429,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
    )

    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=response_body,
        ),
        pytest.raises(RateLimitError),
    ):
        await provider.complete("merhaba")


@pytest.mark.asyncio
async def test_gemini_provider_complete_success() -> None:
    key_id = uuid.uuid4()
    provider = GeminiProvider(api_key="gemini-test-key", key_id=key_id)
    response_body = httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": "Gemini yanıtı"}]}}],
            "usageMetadata": {
                "promptTokenCount": 4,
                "candidatesTokenCount": 6,
                "totalTokenCount": 10,
            },
            "modelVersion": "gemini-2.5-flash-lite",
        },
        request=httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
        ),
    )

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=response_body,
    ) as mock_post:
        response = await provider.complete("merhaba", system_prompt="sistem")

    assert response.text == "Gemini yanıtı"
    assert response.provider == ApiProvider.GEMINI
    assert response.api_key_id == key_id
    mock_post.assert_awaited_once()
    call_kwargs = mock_post.await_args.kwargs
    assert call_kwargs["params"]["key"] == "gemini-test-key"
    assert "gemini-test-key" not in str(response)


@pytest.mark.asyncio
async def test_gemini_provider_maps_503_to_service_unavailable() -> None:
    provider = GeminiProvider(api_key="gemini-test-key", key_id=uuid.uuid4())
    response_body = httpx.Response(
        503,
        request=httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent",
        ),
    )

    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=response_body,
        ),
        pytest.raises(ServiceUnavailableError),
    ):
        await provider.complete("merhaba")


def test_groq_provider_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="Groq API key boş"):
        GroqProvider(api_key="  ", key_id=uuid.uuid4())


def test_gemini_provider_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="Gemini API key boş"):
        GeminiProvider(api_key="", key_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_anthropic_provider_complete_success() -> None:
    key_id = uuid.uuid4()
    provider = AnthropicProvider(api_key="sk-ant-test-key", key_id=key_id)
    response_body = httpx.Response(
        200,
        json={
            "content": [{"type": "text", "text": "Claude yanıtı"}],
            "usage": {"input_tokens": 4, "output_tokens": 6},
            "model": "claude-opus-4-8",
        },
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=response_body,
    ) as mock_post:
        response = await provider.complete("merhaba", system_prompt="sistem")

    assert response.text == "Claude yanıtı"
    assert response.provider == ApiProvider.ANTHROPIC
    assert response.api_key_id == key_id
    assert response.usage.total_tokens == 10
    mock_post.assert_awaited_once()
    call_kwargs = mock_post.await_args.kwargs
    assert call_kwargs["headers"]["x-api-key"] == "sk-ant-test-key"
    assert call_kwargs["json"]["system"] == "sistem"
    assert "sk-ant-test-key" not in str(response)


@pytest.mark.asyncio
async def test_anthropic_provider_maps_429_to_rate_limit() -> None:
    provider = AnthropicProvider(api_key="sk-ant-test-key", key_id=uuid.uuid4())
    response_body = httpx.Response(
        429,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )

    with (
        patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=response_body,
        ),
        pytest.raises(RateLimitError),
    ):
        await provider.complete("merhaba")


def test_anthropic_provider_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="Anthropic API key boş"):
        AnthropicProvider(api_key="", key_id=uuid.uuid4())

"""LLM client factory operasyon-kapsamlı provider filtresi testleri (`Docs/04` §9.1)."""

from __future__ import annotations

import uuid

import pytest
from apps.api.services.llm_client_factory import (
    _key_in_operation_scope,
    list_llm_providers,
)
from packages.shared.enums import ApiProvider, LlmRequestType
from packages.shared.models.api_key import ApiKey


def _key(provider: ApiProvider, scope: list[str]) -> ApiKey:
    return ApiKey(
        id=uuid.uuid4(),
        provider=provider,
        key_alias="alias",
        encrypted_key="enc",
        model="model-x",
        priority_order=1,
        is_active=True,
        request_type_scope=scope,
    )


class _FakeApiKeyService:
    def __init__(self, keys: list[ApiKey]) -> None:
        self._keys = keys

    async def list_active_decrypted(self, db: object) -> list[tuple[ApiKey, str]]:
        return [(key, "plaintext") for key in self._keys]


def test_key_in_operation_scope_rules() -> None:
    op = LlmRequestType.ARTICLE_TRANSLATION
    # operation_type None → filtre yok
    assert _key_in_operation_scope([], None) is True
    assert _key_in_operation_scope(["chatbot"], None) is True
    # boş scope → tüm operasyonlar (geriye uyumlu)
    assert _key_in_operation_scope([], op) is True
    # operasyon scope içinde
    assert _key_in_operation_scope(["article_translation"], op) is True
    assert _key_in_operation_scope(["digest_generation", "article_translation"], op) is True
    # operasyon scope dışında
    assert _key_in_operation_scope(["digest_generation"], op) is False
    assert _key_in_operation_scope(["chatbot"], op) is False
    # string operasyon değeri de kabul edilir
    assert _key_in_operation_scope(["article_translation"], "article_translation") is True


@pytest.mark.asyncio
async def test_list_llm_providers_filters_by_operation() -> None:
    keys = [
        _key(ApiProvider.GROQ, ["article_translation"]),  # kapsam içi
        _key(ApiProvider.GEMINI, []),  # boş = tümü
        _key(ApiProvider.ANTHROPIC, ["digest_generation"]),  # kapsam dışı
    ]
    service = _FakeApiKeyService(keys)

    providers = await list_llm_providers(
        None,  # type: ignore[arg-type]
        service,  # type: ignore[arg-type]
        operation_type=LlmRequestType.ARTICLE_TRANSLATION,
    )

    assert len(providers) == 2
    selected = {provider.provider for provider in providers}
    assert selected == {ApiProvider.GROQ, ApiProvider.GEMINI}


@pytest.mark.asyncio
async def test_list_llm_providers_without_operation_returns_all() -> None:
    keys = [
        _key(ApiProvider.GROQ, ["article_translation"]),
        _key(ApiProvider.ANTHROPIC, ["digest_generation"]),
    ]
    service = _FakeApiKeyService(keys)

    providers = await list_llm_providers(None, service)  # type: ignore[arg-type]

    assert len(providers) == 2

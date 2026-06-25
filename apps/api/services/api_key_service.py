"""LLM API key yönetimi iş mantığı."""

from __future__ import annotations

import uuid

from packages.shared.enums import ApiProvider
from packages.shared.llm_models import is_valid_model, models_for
from packages.shared.models.api_key import ApiKey
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from apps.api.core.encryption import decrypt_api_key, encrypt_api_key, load_encryption_key
from apps.api.core.exceptions import NotFoundException, ValidationException
from apps.api.repositories.api_key_repository import ApiKeyRepository
from apps.api.schemas.api_key import (
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    DeleteApiKeyResponse,
    PatchApiKeyStatusRequest,
    UpdateApiKeyRequest,
)
from apps.api.services.audit_service import AuditService, audit_service

api_key_repository = ApiKeyRepository()


def _to_api_key_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse.model_validate(api_key)


class ApiKeyService:
    """Admin API key CRUD + decrypt helper (LLM client)."""

    def __init__(
        self,
        keys: ApiKeyRepository | None = None,
        audit_svc: AuditService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._keys = keys or api_key_repository
        self._audit_service = audit_svc or audit_service
        self._settings = settings or get_settings()
        self._encryption_key: bytes | None = None

    def _get_encryption_key(self) -> bytes:
        if self._encryption_key is None:
            self._encryption_key = load_encryption_key(self._settings.ENCRYPTION_KEY)
        return self._encryption_key

    async def list_api_keys(self, db: AsyncSession) -> ApiKeyListResponse:
        keys = await self._keys.list_all(db)
        return ApiKeyListResponse(data=[_to_api_key_response(key) for key in keys])

    async def create_api_key(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: CreateApiKeyRequest,
    ) -> ApiKeyResponse:
        encrypted_key = encrypt_api_key(body.api_key, encryption_key=self._get_encryption_key())
        scope = [request_type.value for request_type in body.request_type_scope]
        api_key = await self._keys.create(
            db,
            provider=body.provider,
            key_alias=body.key_alias,
            encrypted_key=encrypted_key,
            model=body.model,
            priority_order=body.priority_order,
            is_active=body.is_active,
            request_type_scope=scope,
        )
        await self._audit_service.log_event(
            db,
            event_type="api_key.created",
            actor_user_id=actor.id,
            target_type="api_key",
            target_id=api_key.id,
            payload={
                "provider": api_key.provider.value,
                "key_alias": api_key.key_alias,
                "model": api_key.model,
                "priority_order": api_key.priority_order,
                "is_active": api_key.is_active,
                "request_type_scope": scope,
            },
        )
        return _to_api_key_response(api_key)

    async def update_api_key(
        self,
        db: AsyncSession,
        *,
        actor: User,
        key_id: uuid.UUID,
        body: UpdateApiKeyRequest,
    ) -> ApiKeyResponse:
        """Operasyon kapsamı (+ opsiyonel model) günceller; audit `api_key.updated`."""
        api_key = await self._keys.get_by_id(db, key_id)
        if api_key is None:
            raise NotFoundException(message="API key bulunamadı.")

        if body.model is not None and not is_valid_model(api_key.provider, body.model):
            allowed = ", ".join(models_for(api_key.provider))
            raise ValidationException(
                message=f"{api_key.provider.value} için geçersiz model. Geçerli: {allowed}",
            )

        scope = [request_type.value for request_type in body.request_type_scope]
        updated = await self._keys.update_scope(
            db,
            api_key,
            request_type_scope=scope,
            model=body.model,
        )
        await self._audit_service.log_event(
            db,
            event_type="api_key.updated",
            actor_user_id=actor.id,
            target_type="api_key",
            target_id=updated.id,
            payload={
                "provider": updated.provider.value,
                "key_alias": updated.key_alias,
                "model": updated.model,
                "request_type_scope": scope,
            },
        )
        return _to_api_key_response(updated)

    async def delete_api_key(
        self,
        db: AsyncSession,
        *,
        actor: User,
        key_id: uuid.UUID,
    ) -> DeleteApiKeyResponse:
        api_key = await self._keys.get_by_id(db, key_id)
        if api_key is None:
            raise NotFoundException(message="API key bulunamadı.")

        payload = {
            "provider": api_key.provider.value,
            "key_alias": api_key.key_alias,
            "priority_order": api_key.priority_order,
        }
        await self._keys.delete(db, api_key)
        await self._audit_service.log_event(
            db,
            event_type="api_key.deleted",
            actor_user_id=actor.id,
            target_type="api_key",
            target_id=key_id,
            payload=payload,
        )
        return DeleteApiKeyResponse(message="API key silindi.")

    async def patch_api_key_status(
        self,
        db: AsyncSession,
        *,
        actor: User,
        key_id: uuid.UUID,
        body: PatchApiKeyStatusRequest,
    ) -> ApiKeyResponse:
        api_key = await self._keys.get_by_id(db, key_id)
        if api_key is None:
            raise NotFoundException(message="API key bulunamadı.")

        if api_key.is_active == body.is_active:
            return _to_api_key_response(api_key)

        updated = await self._keys.update_status(db, api_key, is_active=body.is_active)
        await self._audit_service.log_event(
            db,
            event_type="api_key.status_changed",
            actor_user_id=actor.id,
            target_type="api_key",
            target_id=updated.id,
            payload={
                "provider": updated.provider.value,
                "key_alias": updated.key_alias,
                "is_active": updated.is_active,
            },
        )
        return _to_api_key_response(updated)

    async def decrypt_for_llm(self, db: AsyncSession, key_id: uuid.UUID) -> tuple[ApiProvider, str]:
        """Aktif key'i LLM client için çözer — plaintext log/response dışı."""
        api_key = await self._keys.get_by_id(db, key_id)
        if api_key is None or not api_key.is_active:
            raise NotFoundException(message="API key bulunamadı.")
        encryption_key = self._get_encryption_key()
        plaintext = decrypt_api_key(api_key.encrypted_key, encryption_key=encryption_key)
        return api_key.provider, plaintext

    async def list_active_decrypted(
        self,
        db: AsyncSession,
    ) -> list[tuple[ApiKey, str]]:
        """Aktif key'leri priority sırasıyla çözülmüş döner — LLM client iter 3."""
        active_keys = await self._keys.list_active(db)
        encryption_key = self._get_encryption_key()
        decrypted: list[tuple[ApiKey, str]] = []
        for api_key in active_keys:
            plaintext = decrypt_api_key(api_key.encrypted_key, encryption_key=encryption_key)
            decrypted.append((api_key, plaintext))
        return decrypted


api_key_service = ApiKeyService()

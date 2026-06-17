"""Sistem ayarları iş mantığı."""

from __future__ import annotations

import logging
from typing import Any

from packages.shared.models.system_setting import SystemSetting
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from apps.api.core.exceptions import NotFoundException
from apps.api.repositories.settings_repository import SettingsRepository
from apps.api.schemas.settings import SettingListResponse, SettingResponse
from apps.api.services.audit_service import AuditService, audit_service

logger = logging.getLogger("ygip")

settings_repository = SettingsRepository()

EMBEDDING_MODEL_KEY = "embedding_model"
EMBEDDING_MODEL_WARNING = (
    "Embedding modeli değişti. Reindex job arka planda başlatıldı."
)

JWT_ACCESS_TOKEN_MINUTES_KEY = "jwt_access_token_minutes"
JWT_REFRESH_TOKEN_DAYS_KEY = "jwt_refresh_token_days"


def _to_setting_response(
    setting: SystemSetting,
    *,
    warning: str | None = None,
) -> SettingResponse:
    return SettingResponse(
        key=setting.key,
        value=setting.value,
        description=setting.description,
        updated_at=setting.updated_at,
        warning=warning,
    )


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


class SettingsService:
    """Sistem ayarları okuma ve güncelleme."""

    def __init__(
        self,
        settings_repo: SettingsRepository | None = None,
        audit_svc: AuditService | None = None,
        app_settings: Settings | None = None,
    ) -> None:
        self._settings_repo = settings_repo or settings_repository
        self._audit_service = audit_svc or audit_service
        self._app_settings = app_settings or get_settings()

    async def list_settings(self, db: AsyncSession) -> SettingListResponse:
        settings = await self._settings_repo.list_all(db)
        return SettingListResponse(
            data=[_to_setting_response(setting) for setting in settings],
        )

    async def update_setting(
        self,
        db: AsyncSession,
        *,
        actor: User,
        key: str,
        value: Any,
    ) -> SettingResponse:
        setting = await self._settings_repo.get_by_key(db, key)
        if setting is None:
            raise NotFoundException(message="Sistem ayarı bulunamadı.")

        old_value = setting.value
        if old_value == value:
            return _to_setting_response(setting)

        updated = await self._settings_repo.update(
            db,
            setting,
            value=value,
            updated_by=actor.id,
        )
        await self._audit_service.log_event(
            db,
            event_type="settings.updated",
            actor_user_id=actor.id,
            target_type="system_setting",
            target_id=None,
            payload={
                "key": key,
                "old_value": old_value,
                "new_value": value,
            },
        )

        warning: str | None = None
        if key == EMBEDDING_MODEL_KEY and old_value != value:
            logger.info(
                "embedding_model_changed_reindex_stub",
                extra={"old_value": old_value, "new_value": value},
            )
            warning = EMBEDDING_MODEL_WARNING

        return _to_setting_response(updated, warning=warning)

    async def get_jwt_access_token_minutes(self, db: AsyncSession) -> int:
        return await self._get_int_setting(
            db,
            JWT_ACCESS_TOKEN_MINUTES_KEY,
            default=self._app_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    async def get_jwt_refresh_token_days(self, db: AsyncSession) -> int:
        return await self._get_int_setting(
            db,
            JWT_REFRESH_TOKEN_DAYS_KEY,
            default=self._app_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        )

    async def _get_int_setting(
        self,
        db: AsyncSession,
        key: str,
        *,
        default: int,
    ) -> int:
        setting = await self._settings_repo.get_by_key(db, key)
        if setting is None:
            return default
        return _coerce_int(setting.value, default)


settings_service = SettingsService()

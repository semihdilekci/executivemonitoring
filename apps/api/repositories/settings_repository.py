"""System settings tablosu veri erişimi."""

from __future__ import annotations

import uuid
from typing import Any

from packages.shared.models.system_setting import SystemSetting
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SettingsRepository:
    """Sistem ayarları CRUD."""

    async def get_by_key(self, db: AsyncSession, key: str) -> SystemSetting | None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        return result.scalar_one_or_none()

    async def list_all(self, db: AsyncSession) -> list[SystemSetting]:
        result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        setting: SystemSetting,
        *,
        value: Any,
        updated_by: uuid.UUID,
    ) -> SystemSetting:
        setting.value = value
        setting.updated_by = updated_by
        await db.flush()
        # `updated_at` server-side `onupdate=func.now()` ile hesaplanır; flush
        # sonrası expired kalır. Async session'da attribute lazy-load yasak
        # (MissingGreenlet) olduğu için response'tan önce burada eager refresh.
        await db.refresh(setting)
        return setting

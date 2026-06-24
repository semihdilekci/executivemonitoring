"""API key tablosu veri erişimi."""

from __future__ import annotations

import uuid

from packages.shared.enums import ApiProvider
from packages.shared.models.api_key import ApiKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApiKeyRepository:
    """LLM API key CRUD."""

    async def get_by_id(self, db: AsyncSession, key_id: uuid.UUID) -> ApiKey | None:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        return result.scalar_one_or_none()

    async def list_all(self, db: AsyncSession) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey).order_by(ApiKey.priority_order.asc(), ApiKey.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_active(self, db: AsyncSession) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.is_active.is_(True))
            .order_by(ApiKey.priority_order.asc(), ApiKey.created_at.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        provider: ApiProvider,
        key_alias: str,
        encrypted_key: str,
        model: str,
        priority_order: int,
        is_active: bool = True,
    ) -> ApiKey:
        api_key = ApiKey(
            provider=provider,
            key_alias=key_alias,
            encrypted_key=encrypted_key,
            model=model,
            priority_order=priority_order,
            is_active=is_active,
        )
        db.add(api_key)
        await db.flush()
        return api_key

    async def delete(self, db: AsyncSession, api_key: ApiKey) -> None:
        await db.delete(api_key)
        await db.flush()

    async def update_status(self, db: AsyncSession, api_key: ApiKey, *, is_active: bool) -> ApiKey:
        api_key.is_active = is_active
        await db.flush()
        return api_key

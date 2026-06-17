"""User tablosu veri erişimi."""

from __future__ import annotations

import uuid

from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    """Kullanıcı CRUD ve sorgu operasyonları."""

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_last_login(self, db: AsyncSession, user: User) -> None:
        from datetime import UTC, datetime

        user.last_login_at = datetime.now(UTC)

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], str | None, bool]:
        """Cursor pagination — sıralama: created_at DESC, id DESC."""
        query: Select[tuple[User]] = select(User)

        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if cursor is not None:
            cursor_user = await self.get_by_id(db, cursor)
            if cursor_user is not None:
                query = query.where(
                    or_(
                        User.created_at < cursor_user.created_at,
                        and_(
                            User.created_at == cursor_user.created_at,
                            User.id < cursor_user.id,
                        ),
                    )
                )

        query = query.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
        result = await db.execute(query)
        users = list(result.scalars().all())

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = str(users[-1].id) if has_more and users else None
        return users, next_cursor, has_more

    async def create(
        self,
        db: AsyncSession,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        return user

    async def update(
        self,
        db: AsyncSession,
        user: User,
        *,
        full_name: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        await db.flush()
        return user

    async def update_password_hash(
        self,
        db: AsyncSession,
        user: User,
        *,
        password_hash: str,
    ) -> User:
        user.password_hash = password_hash
        await db.flush()
        return user

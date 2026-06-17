"""Password reset token tablosu veri erişimi."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from packages.shared.models.password_reset_token import PasswordResetToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.security import verify_password


class PasswordResetRepository:
    """Şifre sıfırlama token CRUD."""

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.flush()
        return reset_token

    async def invalidate_active_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Kullanıcının kullanılmamış aktif token'larını geçersiz kılar."""
        now = datetime.now(UTC)
        await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(used_at=now)
        )

    async def find_valid_by_raw_token(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> PasswordResetToken | None:
        """Ham token ile geçerli kaydı bulur (bcrypt karşılaştırma)."""
        now = datetime.now(UTC)
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.expires_at > now,
                PasswordResetToken.used_at.is_(None),
            )
        )
        for row in result.scalars():
            if verify_password(raw_token, row.token_hash):
                return row
        return None

    async def mark_used(self, db: AsyncSession, token: PasswordResetToken) -> None:
        token.used_at = datetime.now(UTC)
        await db.flush()

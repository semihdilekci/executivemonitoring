"""Dev fixture seed — idempotent (`Docs/09` §8.4)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.core.config import Settings, get_settings  # noqa: E402
from packages.shared.enums import (  # noqa: E402
    DigestType,
    SourceCategory,
    SourceStatus,
    SourceType,
    UserRole,
)
from packages.shared.models.notification_preference import NotificationPreference  # noqa: E402
from packages.shared.models.prompt_template import PromptTemplate  # noqa: E402
from packages.shared.models.source import Source  # noqa: E402
from packages.shared.models.system_setting import SystemSetting  # noqa: E402
from packages.shared.models.user import User  # noqa: E402

logger = logging.getLogger("ygip.seed")

FIXTURES_DIR = ROOT / "fixtures"

SEED_ADMIN_EMAIL = "admin@ygip.test"
SEED_DEV_PASSWORD = "DevPass1"


@dataclass(frozen=True)
class SeedStats:
    created: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"created": self.created, "skipped": self.skipped}


@dataclass(frozen=True)
class SeedResult:
    users: SeedStats
    notification_preferences: SeedStats
    system_settings: SeedStats
    prompt_templates: SeedStats
    sources: SeedStats

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {
            "users": self.users.as_dict(),
            "notification_preferences": self.notification_preferences.as_dict(),
            "system_settings": self.system_settings.as_dict(),
            "prompt_templates": self.prompt_templates.as_dict(),
            "sources": self.sources.as_dict(),
        }


def _load_fixture(name: str) -> list[dict[str, Any]]:
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        msg = f"Fixture {name} bir JSON array olmalıdır."
        raise ValueError(msg)
    return data


async def _ensure_notification_preference(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    stats: SeedStats,
) -> SeedStats:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if result.scalar_one_or_none() is not None:
        return SeedStats(created=stats.created, skipped=stats.skipped + 1)

    db.add(
        NotificationPreference(
            user_id=user_id,
            email_enabled=True,
            push_enabled=True,
        )
    )
    return SeedStats(created=stats.created + 1, skipped=stats.skipped)


async def seed_users(db: AsyncSession) -> tuple[SeedStats, SeedStats]:
    user_stats = SeedStats()
    pref_stats = SeedStats()
    for item in _load_fixture("users.json"):
        email = item["email"]
        existing = await db.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user is not None:
            user_stats = SeedStats(created=user_stats.created, skipped=user_stats.skipped + 1)
            pref_stats = await _ensure_notification_preference(
                db,
                user_id=user.id,
                stats=pref_stats,
            )
            continue

        user = User(
            id=uuid.UUID(item["id"]),
            email=email,
            password_hash=item["password_hash"],
            full_name=item["full_name"],
            role=UserRole(item["role"]),
            is_active=item["is_active"],
        )
        db.add(user)
        await db.flush()
        user_stats = SeedStats(created=user_stats.created + 1, skipped=user_stats.skipped)
        pref_stats = await _ensure_notification_preference(
            db,
            user_id=user.id,
            stats=pref_stats,
        )
    return user_stats, pref_stats


async def seed_system_settings(db: AsyncSession) -> SeedStats:
    stats = SeedStats()
    for item in _load_fixture("system_settings.json"):
        key = item["key"]
        existing = await db.get(SystemSetting, key)
        if existing is not None:
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue
        db.add(
            SystemSetting(
                key=key,
                value=item["value"],
                description=item.get("description"),
            )
        )
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def seed_prompt_templates(db: AsyncSession) -> SeedStats:
    stats = SeedStats()
    for item in _load_fixture("prompt_templates.json"):
        name = item["name"]
        existing = await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
        if existing.scalar_one_or_none() is not None:
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue
        db.add(
            PromptTemplate(
                name=name,
                digest_type=DigestType(item["digest_type"]),
                section_key=item["section_key"],
                system_prompt=item["system_prompt"],
                user_prompt_template=item["user_prompt_template"],
                model_preference=item.get("model_preference"),
                is_active=item.get("is_active", True),
                version=item.get("version", 1),
            )
        )
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def seed_sources(db: AsyncSession) -> SeedStats:
    stats = SeedStats()
    for item in _load_fixture("sources.json"):
        source_id = uuid.UUID(item["id"])
        existing = await db.get(Source, source_id)
        if existing is not None:
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue
        db.add(
            Source(
                id=source_id,
                name=item["name"],
                source_type=SourceType(item["source_type"]),
                config=item["config"],
                polling_interval_minutes=item["polling_interval_minutes"],
                status=SourceStatus(item.get("status", "active")),
                category=SourceCategory(item["category"]),
                target_phase=item["target_phase"],
            )
        )
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def run_seed(db: AsyncSession) -> SeedResult:
    """Tüm fixture'ları idempotent şekilde yükler."""
    user_stats, pref_stats = await seed_users(db)
    settings_stats = await seed_system_settings(db)
    template_stats = await seed_prompt_templates(db)
    source_stats = await seed_sources(db)
    return SeedResult(
        users=user_stats,
        notification_preferences=pref_stats,
        system_settings=settings_stats,
        prompt_templates=template_stats,
        sources=source_stats,
    )


def _assert_dev_environment(settings: Settings) -> None:
    if settings.ENVIRONMENT == "production":
        msg = "Seed script yalnızca dev/test ortamında çalıştırılabilir."
        raise RuntimeError(msg)


async def _run_cli(*, database_url: str | None = None) -> SeedResult:
    settings = get_settings()
    _assert_dev_environment(settings)
    url = database_url or settings.DATABASE_URL
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await run_seed(session)
            await session.commit()
            return result
    finally:
        await engine.dispose()


def _print_summary(result: SeedResult) -> None:
    for resource, stats in result.as_dict().items():
        created = stats["created"]
        skipped = stats["skipped"]
        print(f"{resource}: +{created} created, {skipped} skipped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YGIP dev fixture seed (idempotent)")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (varsayılan: ortam değişkeni / .env)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        result = asyncio.run(_run_cli(database_url=args.database_url))
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("seed_failed")
        return 1

    _print_summary(result)
    logger.info("seed_completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

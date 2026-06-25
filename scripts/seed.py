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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.core.config import Settings, get_settings  # noqa: E402
from packages.shared.enums import (  # noqa: E402
    KeywordCategory,
    SourceCategory,
    SourceStatus,
    SourceType,
    UserRole,
)
from packages.shared.env_loader import load_dotenv_file  # noqa: E402
from packages.shared.models.keyword import Keyword, KeywordCategoryRating  # noqa: E402
from packages.shared.models.newsletter_template import (  # noqa: E402
    NewsletterSection,
    NewsletterTemplate,
)
from packages.shared.models.notification_preference import NotificationPreference  # noqa: E402
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
    newsletter_templates: SeedStats
    sources: SeedStats
    keywords: SeedStats

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {
            "users": self.users.as_dict(),
            "notification_preferences": self.notification_preferences.as_dict(),
            "system_settings": self.system_settings.as_dict(),
            "newsletter_templates": self.newsletter_templates.as_dict(),
            "sources": self.sources.as_dict(),
            "keywords": self.keywords.as_dict(),
        }


def _resolve_source_config(item: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Email kaynaklarında IMAP host/kullanıcı `.env` değerlerinden gelir."""
    config = dict(item["config"])
    if item.get("source_type") != "email":
        return config

    imap_host = settings.IMAP_HOST.strip() if settings.IMAP_HOST else ""
    imap_user = settings.IMAP_USER.strip() if settings.IMAP_USER else ""
    if imap_host:
        config["imap_host"] = imap_host
    if imap_user:
        config["imap_user"] = imap_user
    config.setdefault("imap_host", "imap.gmail.com")
    config.setdefault("imap_user", "newsletters@ygip.test")
    return config


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


def _load_fixture_object(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        msg = f"Fixture {name} bir JSON object olmalıdır."
        raise ValueError(msg)
    return data


async def seed_newsletter_templates(db: AsyncSession) -> SeedStats:
    """Serbest bülten + bölüm seed — `slug` anahtarıyla idempotent (Faz 6.5).

    Global anlık-etki prompt'ları (`newsletter_impact_*`) `system_settings`'e idempotent
    eklenir (migration de ekler; mevcutsa atlanır). Bülten istatistiği yalnızca yeni
    oluşturulan bülten sayısını döner.
    """
    fixture = _load_fixture_object("newsletter_templates.json")
    stats = SeedStats()

    for setting in fixture.get("impact_settings", []):
        existing_setting = await db.get(SystemSetting, setting["key"])
        if existing_setting is None:
            db.add(
                SystemSetting(
                    key=setting["key"],
                    value=setting["value"],
                    description=setting.get("description"),
                )
            )

    for item in fixture.get("newsletters", []):
        slug = item["slug"]
        existing = await db.execute(
            select(NewsletterTemplate).where(NewsletterTemplate.slug == slug)
        )
        if existing.scalar_one_or_none() is not None:
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue
        db.add(
            NewsletterTemplate(
                slug=slug,
                name=item["name"],
                description=item.get("description", ""),
                date_range_days=item.get("date_range_days", 7),
                summary_system_prompt=item["summary_system_prompt"],
                summary_user_prompt=item["summary_user_prompt"],
                min_content_score=item.get("min_content_score", 50),
                content_categories=item.get("content_categories", []),
                model_preference=item.get("model_preference"),
                is_active=item.get("is_active", True),
                sections=[
                    NewsletterSection(
                        name=section["name"],
                        sort_order=section["sort_order"],
                        section_system_prompt=section["section_system_prompt"],
                        section_user_prompt=section["section_user_prompt"],
                        impact_prompt=section["impact_prompt"],
                        is_active=section.get("is_active", True),
                    )
                    for section in item.get("sections", [])
                ],
            )
        )
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def seed_sources(db: AsyncSession, *, settings: Settings | None = None) -> SeedStats:
    resolved_settings = settings or get_settings()
    stats = SeedStats()
    for item in _load_fixture("sources.json"):
        source_id = uuid.UUID(item["id"])
        config = _resolve_source_config(item, resolved_settings)
        existing = await db.get(Source, source_id)
        if existing is not None:
            if item.get("source_type") == "email":
                merged = dict(existing.config)
                merged["imap_host"] = config["imap_host"]
                merged["imap_user"] = config["imap_user"]
                existing.config = merged
                flag_modified(existing, "config")
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue
        db.add(
            Source(
                id=source_id,
                name=item["name"],
                source_type=SourceType(item["source_type"]),
                config=config,
                polling_interval_minutes=item["polling_interval_minutes"],
                status=SourceStatus(item.get("status", "active")),
                category=SourceCategory(item["category"]),
                target_phase=item["target_phase"],
            )
        )
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def seed_keywords(db: AsyncSession) -> SeedStats:
    """Production-grade keyword havuzu — `term_tr` (lower) anahtarıyla idempotent.

    Mevcut keyword'ler korunur (admin sonradan panelden düzenler); yalnızca
    eksikler oluşturulur. Rating satırları keyword ile birlikte eklenir.
    """
    stats = SeedStats()
    for item in _load_fixture("keywords.json"):
        term_tr = item["term_tr"]
        # İdempotency kontrolü `uq_keywords_term_tr_lower` (PG `lower(term_tr)`) ile
        # birebir aynı `lower()` semantiğini kullanmalı: Python `str.lower()` Türkçe
        # İ (U+0130) için PG `lower()`'dan farklı sonuç verir ("İstegelsin", "BİM"),
        # bu da re-run'da kontrolü kaçırıp unique ihlaline yol açardı. Her iki tarafta
        # da PG `func.lower()` kullanılır.
        existing = await db.execute(
            select(Keyword).where(func.lower(Keyword.term_tr) == func.lower(term_tr))
        )
        if existing.scalar_one_or_none() is not None:
            stats = SeedStats(created=stats.created, skipped=stats.skipped + 1)
            continue

        keyword = Keyword(
            term_tr=term_tr,
            term_en=item["term_en"],
            is_active=item.get("is_active", True),
            categories=[
                KeywordCategoryRating(
                    category=KeywordCategory(rating["category"]),
                    rating=rating["rating"],
                )
                for rating in item["categories"]
            ],
        )
        db.add(keyword)
        stats = SeedStats(created=stats.created + 1, skipped=stats.skipped)
    return stats


async def run_seed(db: AsyncSession, *, settings: Settings | None = None) -> SeedResult:
    """Tüm fixture'ları idempotent şekilde yükler."""
    resolved_settings = settings or get_settings()
    user_stats, pref_stats = await seed_users(db)
    settings_stats = await seed_system_settings(db)
    newsletter_stats = await seed_newsletter_templates(db)
    source_stats = await seed_sources(db, settings=resolved_settings)
    keyword_stats = await seed_keywords(db)
    return SeedResult(
        users=user_stats,
        notification_preferences=pref_stats,
        system_settings=settings_stats,
        newsletter_templates=newsletter_stats,
        sources=source_stats,
        keywords=keyword_stats,
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
            result = await run_seed(session, settings=settings)
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
    load_dotenv_file(override=False)
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

"""Shared domain enums — PostgreSQL native enum ile eşleşir."""

from enum import StrEnum


class UserRole(StrEnum):
    """Kullanıcı RBAC rolü (`user_role_enum`)."""

    ADMIN = "admin"
    VIEWER = "viewer"


class SourceType(StrEnum):
    """Veri kaynağı tipi (`source_type_enum`)."""

    RSS = "rss"
    EMAIL = "email"
    REST_API = "rest_api"
    WEBSOCKET = "websocket"
    GOV = "gov"


class SourceStatus(StrEnum):
    """Kaynak durumu (`source_status_enum`)."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SourceCategory(StrEnum):
    """Kaynak kategorisi (`source_category_enum`)."""

    TURKISH_MEDIA = "turkish_media"
    FMCG = "fmcg"
    STRATEGY = "strategy"
    OFFICIAL = "official"
    MARKET = "market"
    GEO = "geo"
    TRANSPORT = "transport"


class RawItemStatus(StrEnum):
    """Ham kayıt işleme durumu (`raw_item_status_enum`)."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ApiProvider(StrEnum):
    """LLM API sağlayıcısı (`api_provider_enum`)."""

    GROQ = "groq"
    GEMINI = "gemini"


class LlmRequestType(StrEnum):
    """LLM çağrısı işlem tipi (`api_usage_logs.request_type`)."""

    DIGEST_GENERATION = "digest_generation"
    CHATBOT = "chatbot"


PROCESSED_ITEM_SCHEMAS: tuple[str, ...] = ("news", "market", "geo", "transport", "fmcg")


class DigestType(StrEnum):
    """Bülten tipi (`digest_type_enum`)."""

    TURKISH_MEDIA_WEEKLY = "turkish_media_weekly"
    FMCG_WEEKLY = "fmcg_weekly"
    STRATEGY_WEEKLY = "strategy_weekly"


class DigestStatus(StrEnum):
    """Bülten üretim durumu (`digest_status_enum`)."""

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class NotificationChannel(StrEnum):
    """Bildirim kanalı (`notification_channel_enum`)."""

    EMAIL = "email"
    PUSH = "push"


class NotificationStatus(StrEnum):
    """Bildirim teslimat durumu (`notification_status_enum`)."""

    SENT = "sent"
    FAILED = "failed"


class NotificationType(StrEnum):
    """Bildirim tipi — `notification_logs.notification_type`."""

    DIGEST_READY = "digest_ready"

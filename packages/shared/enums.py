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
    """Kaynak kategorisi (`source_category_enum`).

    Faz 6.3+ ile içerik arşivi kategorileriyle (`KeywordCategory`) birebir
    hizalandı: kaynaklar artık ürettikleri içerik kategorisine göre sınıflanır.
    Eski değerler (`turkish_media`, `official`, `market`, `geo`, `transport`)
    008 migration ile bu 6 değere taşındı.
    """

    MACRO = "macro"
    FINANCE = "finance"
    FMCG = "fmcg"
    STRATEGY = "strategy"
    GEOPOLITICAL = "geopolitical"
    REGULATORY = "regulatory"


class KeywordCategory(StrEnum):
    """Keyword içerik kategorisi (`keyword_category_enum`).

    Değerler `processed_items.content_category` ile birebir aynıdır
    (enricher kategori anahtarları, `Docs/04` §8.4). Source-seviyesi
    `SourceCategory`'den farklıdır; ikisi karıştırılmaz.
    """

    MACRO = "macro"
    FINANCE = "finance"
    FMCG = "fmcg"
    STRATEGY = "strategy"
    GEOPOLITICAL = "geopolitical"
    REGULATORY = "regulatory"


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


class PipelineRunType(StrEnum):
    """Pipeline çalıştırma tipi (`pipeline_run_type_enum`)."""

    COLLECT_PIPELINE = "collect_pipeline"
    DIGEST_UPDATE = "digest_update"


class PipelineRunStatus(StrEnum):
    """Pipeline run durumu (`pipeline_run_status_enum`)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(StrEnum):
    """Pipeline aşaması (`pipeline_stage_enum`)."""

    COLLECT = "collect"
    INGEST = "ingest"
    PROCESS = "process"
    DIGEST = "digest"


class PipelineStepStatus(StrEnum):
    """Pipeline adım durumu (`pipeline_step_status_enum`)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

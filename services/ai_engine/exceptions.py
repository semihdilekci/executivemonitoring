"""AI engine exception sınıfları."""

from __future__ import annotations


class LLMProviderError(Exception):
    """LLM sağlayıcı hata tabanı."""


class AIEngineHTTPError(LLMProviderError):
    """HTTP katmanına map edilebilir AI engine hatası — `502` + `error_code`."""

    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "Dış servis hatası."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class RateLimitError(LLMProviderError):
    """429 — kota veya rate limit aşıldı; fallback denenebilir."""


class QuotaExhaustedError(LLMProviderError):
    """Kota tükendi — fallback denenebilir."""


class ServiceUnavailableError(LLMProviderError):
    """503 — geçici servis hatası; fallback denenebilir."""


class NoActiveLLMProviderError(AIEngineHTTPError):
    """Aktif LLM API key yok."""

    error_code = "NO_ACTIVE_LLM_PROVIDER"
    message = "Aktif LLM API key bulunamadı."


class AllProvidersFailedError(AIEngineHTTPError):
    """Tüm provider'lar başarısız."""

    error_code = "ALL_LLM_PROVIDERS_FAILED"
    message = "Tüm LLM provider'lar başarısız."


class PromptTemplateRenderError(LLMProviderError):
    """Jinja2 prompt render hatası — eksik değişken veya geçersiz şablon."""

    error_code = "PROMPT_TEMPLATE_RENDER_ERROR"
    message = "Prompt şablonu render edilemedi."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class DigestGenerationError(Exception):
    """Digest üretim hatası tabanı."""

    error_code = "DIGEST_GENERATION_FAILED"
    message = "Bülten üretimi başarısız."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class DigestParseError(DigestGenerationError):
    """LLM çıktısı parse edilemedi."""

    error_code = "DIGEST_PARSE_ERROR"
    message = "Bülten çıktısı parse edilemedi."


class NoArticlesForDigestError(DigestGenerationError):
    """Seçim kriterlerine uyan makale yok."""

    error_code = "NO_ARTICLES_FOR_DIGEST"
    message = "Seçilen dönem için uygun makale bulunamadı."


class NoPromptTemplatesError(DigestGenerationError):
    """Aktif prompt şablonu yok."""

    error_code = "NO_PROMPT_TEMPLATES"
    message = "Bu bülten tipi için aktif prompt şablonu bulunamadı."


class MailDeliveryError(Exception):
    """SMTP e-posta gönderim hatası."""

    error_code = "MAIL_DELIVERY_FAILED"
    message = "E-posta gönderimi başarısız."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class MailTemplateRenderError(Exception):
    """E-posta şablonu render hatası."""

    error_code = "MAIL_TEMPLATE_RENDER_ERROR"
    message = "E-posta şablonu render edilemedi."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class PushConfigurationError(Exception):
    """FCM yapılandırma hatası."""

    error_code = "PUSH_CONFIGURATION_ERROR"
    message = "FCM yapılandırması geçersiz."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class PushDeliveryError(Exception):
    """FCM push gönderim hatası."""

    error_code = "PUSH_DELIVERY_FAILED"
    message = "Push bildirimi gönderilemedi."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)

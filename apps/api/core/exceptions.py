"""Uygulama exception hiyerarşisi."""

from typing import Any


class AppException(Exception):
    """Tüm uygulama hatalarının base class'ı."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "Beklenmeyen bir hata oluştu."

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class UnauthorizedException(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Kimlik doğrulama gerekli."


class ForbiddenException(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Bu işlem için yetkiniz yok."


class NotFoundException(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Kayıt bulunamadı."


class ConflictException(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Kayıt zaten mevcut."


class ValidationException(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Giriş verisi geçersiz."


class PasswordPolicyViolationException(AppException):
    status_code = 400
    error_code = "PASSWORD_POLICY_VIOLATION"
    message = "Şifre politikasına uymuyor."


class RateLimitException(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "İstek limiti aşıldı. Lütfen bekleyiniz."

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after_seconds: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = {"retry_after_seconds": retry_after_seconds}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details)
        self.retry_after_seconds = retry_after_seconds


class ExternalServiceException(AppException):
    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "Dış servis hatası."

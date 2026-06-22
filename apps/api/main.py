"""FastAPI uygulama giriş noktası."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from services.ai_engine.exceptions import AIEngineHTTPError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.core.config import Settings, get_settings
from apps.api.core.exceptions import AppException, RateLimitException
from apps.api.middleware.rate_limiter import (
    RateLimiterBackend,
    RateLimiterMiddleware,
    create_rate_limiter_backend,
)
from apps.api.middleware.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from apps.api.middleware.request_logger import RequestLoggerMiddleware
from apps.api.routers import (
    api_keys,
    audit_logs,
    auth,
    chat,
    content_archive,
    digests,
    health,
    keyword,
    notifications,
    pipeline,
    prompt_templates,
    sources,
    users,
)
from apps.api.routers import settings as settings_router
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService

logger = logging.getLogger("ygip")


def _error_headers(request: Request) -> dict[str, str]:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return {REQUEST_ID_HEADER: request_id}
    return {}


def _register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        headers = _error_headers(request)
        if isinstance(exc, RateLimitException):
            headers["Retry-After"] = str(exc.retry_after_seconds)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details or {},
                }
            },
            headers=headers,
        )

    @app.exception_handler(AIEngineHTTPError)
    async def ai_engine_http_exception_handler(
        request: Request,
        exc: AIEngineHTTPError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": str(exc) or exc.message,
                    "details": {},
                }
            },
            headers=_error_headers(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        fields: list[dict[str, str]] = []
        for error in exc.errors():
            loc = error.get("loc", ())
            field_name = ".".join(str(part) for part in loc if part != "body")
            fields.append(
                {
                    "field": field_name or "body",
                    "message": error.get("msg", "Geçersiz değer"),
                    "type": str(error.get("type", "value_error")),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "İstek doğrulaması başarısız.",
                    "details": {"fields": fields},
                }
            },
            headers=_error_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unhandled_exception", extra={"request_id": request_id})
        details: dict[str, Any] = {}
        if settings.is_development:
            details["exception"] = exc.__class__.__name__
            details["message"] = str(exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Beklenmeyen bir hata oluştu.",
                    "details": details,
                }
            },
            headers=_error_headers(request),
        )


def create_app(
    settings: Settings | None = None,
    *,
    rate_limiter_backend: RateLimiterBackend | None = None,
) -> FastAPI:
    """Uygulama factory — testlerde settings/backend override edilebilir."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(
            resolved_settings.DATABASE_URL,
            pool_size=resolved_settings.DB_POOL_SIZE,
            max_overflow=resolved_settings.DB_MAX_OVERFLOW,
        )
        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.api_key_service = ApiKeyService(settings=resolved_settings)
        app.state.api_usage_service = ApiUsageService()
        yield
        await engine.dispose()

    app = FastAPI(
        title="YGIP API",
        version="0.1.0",
        lifespan=lifespan,
    )

    backend = rate_limiter_backend or create_rate_limiter_backend(resolved_settings)
    app.state.rate_limiter_backend = backend

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        max_age=600,
    )
    app.add_middleware(
        RateLimiterMiddleware,
        settings=resolved_settings,
        backend=backend,
    )
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RequestIDMiddleware)

    _register_exception_handlers(app, resolved_settings)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(audit_logs.router)
    app.include_router(settings_router.router)
    app.include_router(sources.router)
    app.include_router(api_keys.router)
    app.include_router(prompt_templates.router)
    app.include_router(digests.router)
    app.include_router(chat.router)
    app.include_router(notifications.router)
    app.include_router(pipeline.router)
    app.include_router(content_archive.router)
    app.include_router(keyword.router)

    return app


app = create_app()

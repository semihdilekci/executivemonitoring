"""Sağlık ve hazırlık kontrol endpoint'leri."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Uygulama süreci ayakta mı — DB kontrolü yapmaz."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
    """DB bağlantısı hazır mı."""
    try:
        await db.execute(select(1))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Veritabanı bağlantısı kurulamadı.",
                    "details": {},
                }
            },
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})

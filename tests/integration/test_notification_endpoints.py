"""Bildirim endpoint integration testleri — FCM token kaydı."""

from __future__ import annotations

import uuid

import pytest
from apps.api.core.config import Settings
from apps.api.core.security import create_access_token
from httpx import AsyncClient
from packages.shared.models.notification_preference import NotificationPreference
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)

FCM_TOKEN = "dGVzdC1mY20tdG9rZW4tMTIzNDU2"
UPDATED_FCM_TOKEN = "dGVzdC1mY20tdG9rZW4tYWJjZGVm"


async def _get_fcm_token(database_url: str, user_id: uuid.UUID) -> str | None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            select(NotificationPreference.fcm_token).where(
                NotificationPreference.user_id == user_id,
            ),
        )
        token = result.scalar_one_or_none()
    await engine.dispose()
    return token


@pytest.mark.asyncio
async def test_register_fcm_token_unauthenticated_returns_401(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        json={"fcm_token": FCM_TOKEN},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_register_fcm_token_viewer_persists_token(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)

    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=auth_headers(token),
        json={"fcm_token": FCM_TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "FCM token güncellendi."
    assert FCM_TOKEN not in body

    stored_token = await _get_fcm_token(database_url, viewer_test_user.id)
    assert stored_token == FCM_TOKEN


@pytest.mark.asyncio
async def test_register_fcm_token_admin_allowed(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)

    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=auth_headers(token),
        json={"fcm_token": FCM_TOKEN},
    )

    assert response.status_code == 200
    stored_token = await _get_fcm_token(database_url, admin_test_user.id)
    assert stored_token == FCM_TOKEN


@pytest.mark.asyncio
async def test_register_fcm_token_idempotent_for_same_token(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    first = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=headers,
        json={"fcm_token": FCM_TOKEN},
    )
    second = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=headers,
        json={"fcm_token": FCM_TOKEN},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "FCM token güncellendi."

    stored_token = await _get_fcm_token(database_url, viewer_test_user.id)
    assert stored_token == FCM_TOKEN


@pytest.mark.asyncio
async def test_register_fcm_token_updates_existing_token(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=headers,
        json={"fcm_token": FCM_TOKEN},
    )
    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=headers,
        json={"fcm_token": UPDATED_FCM_TOKEN},
    )

    assert response.status_code == 200
    stored_token = await _get_fcm_token(database_url, viewer_test_user.id)
    assert stored_token == UPDATED_FCM_TOKEN


@pytest.mark.asyncio
async def test_register_fcm_token_rejects_empty_token(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)

    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=auth_headers(token),
        json={"fcm_token": "   "},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_fcm_token_inactive_user_returns_403(
    api_client: AsyncClient,
    inactive_test_user: AuthTestUser,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apps.api.core.security.get_settings", lambda: test_settings)
    access_token = create_access_token(
        str(inactive_test_user.id),
        role=inactive_test_user.role.value,
        email=inactive_test_user.email,
        settings=test_settings,
    )

    response = await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=auth_headers(access_token),
        json={"fcm_token": FCM_TOKEN},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_ACCOUNT_INACTIVE"

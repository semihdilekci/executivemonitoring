"""Bildirim tercihleri endpoint integration testleri — admin GET/PUT."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.notification_preference import NotificationPreference
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)

FCM_TOKEN = "dGVzdC1wcmVmZXJlbmNlcy1mY20tdG9rZW4="


@pytest.fixture
async def seeded_notification_preferences(
    database_url: str,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
) -> AsyncIterator[None]:
    """Test kullanıcıları için bildirim tercihi kayıtları."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_ids = [admin_test_user.id, viewer_test_user.id]

    async with session_factory() as session:
        for user_id in user_ids:
            session.add(
                NotificationPreference(
                    user_id=user_id,
                    email_enabled=True,
                    push_enabled=True,
                ),
            )
        await session.commit()

    yield

    async with session_factory() as session:
        await session.execute(
            delete(NotificationPreference).where(
                NotificationPreference.user_id.in_(user_ids),
            ),
        )
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_can_list_notification_preferences(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        "/api/v1/notifications/preferences",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 2

    viewer_item = next(
        item for item in body["data"] if item["user_id"] == str(viewer_test_user.id)
    )
    assert viewer_item["user_name"] == "Viewer Test User"
    assert viewer_item["email_enabled"] is True
    assert viewer_item["push_enabled"] is True
    assert viewer_item["has_fcm_token"] is False
    assert "fcm_token" not in viewer_item


@pytest.mark.asyncio
async def test_viewer_forbidden_on_preferences_list(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get(
        "/api/v1/notifications/preferences",
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_update_notification_preferences(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        f"/api/v1/notifications/preferences/{viewer_test_user.id}",
        headers=auth_headers(token),
        json={"email_enabled": False, "push_enabled": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(viewer_test_user.id)
    assert body["user_name"] == "Viewer Test User"
    assert body["email_enabled"] is False
    assert body["push_enabled"] is True
    assert body["has_fcm_token"] is False
    assert "fcm_token" not in body


@pytest.mark.asyncio
async def test_update_preferences_reflects_fcm_token_presence(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    viewer_token = await login_and_get_token(api_client, viewer_test_user)
    await api_client.post(
        "/api/v1/notifications/fcm-token",
        headers=auth_headers(viewer_token),
        json={"fcm_token": FCM_TOKEN},
    )

    admin_token = await login_and_get_token(api_client, admin_test_user)
    list_response = await api_client.get(
        "/api/v1/notifications/preferences",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200
    viewer_item = next(
        item
        for item in list_response.json()["data"]
        if item["user_id"] == str(viewer_test_user.id)
    )
    assert viewer_item["has_fcm_token"] is True
    assert FCM_TOKEN not in list_response.text


@pytest.mark.asyncio
async def test_update_unknown_user_preferences_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        f"/api/v1/notifications/preferences/{uuid.uuid4()}",
        headers=auth_headers(token),
        json={"email_enabled": True, "push_enabled": False},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_viewer_forbidden_on_preferences_update(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    admin_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.put(
        f"/api/v1/notifications/preferences/{admin_test_user.id}",
        headers=auth_headers(token),
        json={"email_enabled": False, "push_enabled": False},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_update_preferences_writes_audit_log(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    update_response = await api_client.put(
        f"/api/v1/notifications/preferences/{viewer_test_user.id}",
        headers=auth_headers(token),
        json={"email_enabled": True, "push_enabled": False},
    )
    assert update_response.status_code == 200

    audit_response = await api_client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(token),
        params={"event_type": "notification.preferences_updated"},
    )
    assert audit_response.status_code == 200
    matched = next(
        (
            item
            for item in audit_response.json()["data"]
            if item["payload"].get("user_id") == str(viewer_test_user.id)
            and item["payload"].get("push_enabled", {}).get("to") is False
        ),
        None,
    )
    assert matched is not None
    assert matched["actor_user_id"] == str(admin_test_user.id)
    assert "fcm_token" not in matched["payload"]


@pytest.mark.asyncio
async def test_preferences_unauthenticated_returns_401(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    seeded_notification_preferences: None,
) -> None:
    list_response = await api_client.get("/api/v1/notifications/preferences")
    assert list_response.status_code == 401
    assert list_response.json()["error"]["code"] == "UNAUTHORIZED"

    update_response = await api_client.put(
        f"/api/v1/notifications/preferences/{viewer_test_user.id}",
        json={"email_enabled": True, "push_enabled": True},
    )
    assert update_response.status_code == 401
    assert update_response.json()["error"]["code"] == "UNAUTHORIZED"

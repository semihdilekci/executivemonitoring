"""Sistem ayarları endpoint integration testleri."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.system_setting import SystemSetting
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)

DEFAULT_SETTINGS: list[tuple[str, object, str]] = [
    ("jwt_access_token_minutes", 60, "Access token geçerlilik süresi (dk)"),
    ("jwt_refresh_token_days", 30, "Refresh token geçerlilik süresi (gün)"),
    ("embedding_model", "openai/text-embedding-3-small", "Aktif embedding modeli"),
]


@pytest.fixture
async def seeded_system_settings(database_url: str) -> AsyncIterator[None]:
    """Test için öntanımlı system_settings kayıtları."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for key, value, description in DEFAULT_SETTINGS:
            session.add(
                SystemSetting(
                    key=key,
                    value=value,
                    description=description,
                )
            )
        await session.commit()

    yield

    async with session_factory() as session:
        keys = [key for key, _, _ in DEFAULT_SETTINGS]
        await session.execute(delete(SystemSetting).where(SystemSetting.key.in_(keys)))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_can_list_settings(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get("/api/v1/settings", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    keys = {item["key"] for item in body["data"]}
    assert "jwt_access_token_minutes" in keys
    assert "embedding_model" in keys
    jwt_setting = next(
        item for item in body["data"] if item["key"] == "jwt_access_token_minutes"
    )
    assert jwt_setting["value"] == 60
    assert jwt_setting["description"] == "Access token geçerlilik süresi (dk)"
    assert "updated_at" in jwt_setting


@pytest.mark.asyncio
async def test_viewer_forbidden_on_settings_list(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get("/api/v1/settings", headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_update_setting(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        "/api/v1/settings/jwt_access_token_minutes",
        headers=auth_headers(token),
        json={"value": 120},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "jwt_access_token_minutes"
    assert body["value"] == 120
    assert body["description"] == "Access token geçerlilik süresi (dk)"
    assert "updated_at" in body
    assert body.get("warning") is None


@pytest.mark.asyncio
async def test_update_unknown_setting_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        "/api/v1/settings/unknown_setting_key",
        headers=auth_headers(token),
        json={"value": 1},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_embedding_model_returns_warning(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        "/api/v1/settings/embedding_model",
        headers=auth_headers(token),
        json={"value": "cohere/embed-v3"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "embedding_model"
    assert body["value"] == "cohere/embed-v3"
    assert body["warning"] == (
        "Embedding modeli değişti. Reindex job arka planda başlatıldı."
    )


@pytest.mark.asyncio
async def test_update_setting_writes_audit_log(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    update_response = await api_client.put(
        "/api/v1/settings/jwt_refresh_token_days",
        headers=auth_headers(token),
        json={"value": 45},
    )
    assert update_response.status_code == 200

    audit_response = await api_client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(token),
        params={"event_type": "settings.updated"},
    )
    assert audit_response.status_code == 200
    data = audit_response.json()["data"]
    matched = next(
        (
            item
            for item in data
            if item["payload"].get("key") == "jwt_refresh_token_days"
            and item["payload"].get("new_value") == 45
        ),
        None,
    )
    assert matched is not None
    assert matched["actor_user_id"] == str(admin_test_user.id)
    assert matched["payload"]["old_value"] == 30


@pytest.mark.asyncio
async def test_viewer_forbidden_on_settings_update(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    seeded_system_settings: None,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.put(
        "/api/v1/settings/jwt_access_token_minutes",
        headers=auth_headers(token),
        json={"value": 90},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_settings_unauthenticated_returns_401(
    api_client: AsyncClient,
    seeded_system_settings: None,
) -> None:
    list_response = await api_client.get("/api/v1/settings")
    assert list_response.status_code == 401
    assert list_response.json()["error"]["code"] == "UNAUTHORIZED"

    update_response = await api_client.put(
        "/api/v1/settings/jwt_access_token_minutes",
        json={"value": 60},
    )
    assert update_response.status_code == 401
    assert update_response.json()["error"]["code"] == "UNAUTHORIZED"

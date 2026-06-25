"""Bülten şablonu (newsletter template) API integration testleri (Faz 6.5).

Admin CRUD + audit; viewer 403; slug çakışması 409 `NEWSLETTER_SLUG_EXISTS`;
`min_content_score` 0–100 dışı 422; nested bölüm replace.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from packages.shared.models.newsletter_template import NewsletterTemplate
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)

_SLUG_PREFIX = "tst_nl_"


@pytest.fixture(autouse=True)
async def _cleanup_test_templates(database_url: str) -> AsyncIterator[None]:
    yield
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            delete(NewsletterTemplate).where(NewsletterTemplate.slug.like(f"{_SLUG_PREFIX}%"))
        )
        await session.commit()
    await engine.dispose()


def _template_payload(slug: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slug": slug,
        "name": "Test Bülteni",
        "description": "Açıklama",
        "date_range_days": 7,
        "summary_system_prompt": "Sen bir editörsün.",
        "summary_user_prompt": "Bölümler: {sections}\nHaberler: {articles}",
        "min_content_score": 50,
        "model_preference": None,
        "is_active": True,
        "sections": [
            {
                "name": "Genel",
                "sort_order": 0,
                "section_system_prompt": "Sistem",
                "section_user_prompt": "Haberler: {articles}",
                "impact_prompt": "Etki?",
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_admin_full_crud(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    slug = f"{_SLUG_PREFIX}crud"

    create = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(slug),
    )
    assert create.status_code == 201
    created = create.json()
    template_id = created["id"]
    assert created["slug"] == slug
    assert len(created["sections"]) == 1
    assert created["sections"][0]["name"] == "Genel"

    get = await api_client.get(
        f"/api/v1/newsletter-templates/{template_id}",
        headers=headers,
    )
    assert get.status_code == 200
    assert get.json()["id"] == template_id

    listed = await api_client.get("/api/v1/newsletter-templates", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == template_id for item in listed.json()["data"])

    update_payload = _template_payload(slug, name="Güncel Bülten")
    update_payload["sections"] = [
        {
            "name": "Manşetler",
            "sort_order": 0,
            "section_system_prompt": "Sistem",
            "section_user_prompt": "Haberler: {articles}",
            "impact_prompt": "Etki?",
        },
        {
            "name": "Detaylar",
            "sort_order": 1,
            "section_system_prompt": "Sistem 2",
            "section_user_prompt": "Haberler: {articles}",
            "impact_prompt": "Etki 2?",
        },
    ]
    # slug update isteğinde yer almaz (salt-okunur); name + bölümler replace edilir.
    del update_payload["slug"]
    update = await api_client.put(
        f"/api/v1/newsletter-templates/{template_id}",
        headers=headers,
        json=update_payload,
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["name"] == "Güncel Bülten"
    assert [s["name"] for s in updated["sections"]] == ["Manşetler", "Detaylar"]

    delete_response = await api_client.delete(
        f"/api/v1/newsletter-templates/{template_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    get_after = await api_client.get(
        f"/api/v1/newsletter-templates/{template_id}",
        headers=headers,
    )
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_slug_returns_409(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    slug = f"{_SLUG_PREFIX}dup"

    first = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(slug),
    )
    assert first.status_code == 201

    second = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(slug),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "NEWSLETTER_SLUG_EXISTS"


@pytest.mark.asyncio
async def test_invalid_min_content_score_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(f"{_SLUG_PREFIX}score", min_content_score=150),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_sections_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(f"{_SLUG_PREFIX}empty", sections=[]),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_viewer_cannot_create_template(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/newsletter-templates",
        headers=headers,
        json=_template_payload(f"{_SLUG_PREFIX}viewer"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_viewer_cannot_list_templates(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.get("/api/v1/newsletter-templates", headers=headers)
    assert response.status_code == 403

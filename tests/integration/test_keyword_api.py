"""Keyword Takibi API integration testleri (Faz 6.3 — İterasyon 4).

Admin-only CRUD; RBAC deny (viewer 403), duplicate (409 KEYWORD_DUPLICATE),
rating/kategori doğrulaması (422), bulunamaz (404 KEYWORD_NOT_FOUND),
`categories` replace semantiği ve her yazma işleminin audit log üretmesi
(`keyword.created/updated/deleted`) doğrulanır.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.keyword import Keyword, KeywordCategoryRating
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


def _keyword_payload(*, term_tr: str, term_en: str) -> dict[str, object]:
    return {
        "term_tr": term_tr,
        "term_en": term_en,
        "is_active": True,
        "categories": [
            {"category": "macro", "rating": 9},
            {"category": "finance", "rating": 6},
        ],
    }


@pytest.fixture
async def keyword_cleanup(database_url: str) -> AsyncIterator[list[uuid.UUID]]:
    """Test sırasında oluşan keyword id'leri teardown'da temizler."""
    created: list[uuid.UUID] = []
    yield created

    if not created:
        return
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(Keyword).where(Keyword.id.in_(created)))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_keyword_crud_and_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
    keyword_cleanup: list[uuid.UUID],
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    term_tr = f"enflasyon-{uuid.uuid4().hex[:8]}"
    term_en = f"inflation-{uuid.uuid4().hex[:8]}"

    # CREATE
    create_response = await api_client.post(
        "/api/v1/admin/keywords",
        headers=headers,
        json=_keyword_payload(term_tr=term_tr, term_en=term_en),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    keyword_id = created["id"]
    keyword_cleanup.append(uuid.UUID(keyword_id))
    assert created["term_tr"] == term_tr
    assert created["is_active"] is True
    assert {c["category"]: c["rating"] for c in created["categories"]} == {
        "macro": 9,
        "finance": 6,
    }

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "keyword.created",
                AuditLog.target_id == uuid.UUID(keyword_id),
            )
        )
        assert audit.scalar_one_or_none() is not None

    # LIST (filtre: category)
    list_response = await api_client.get(
        "/api/v1/admin/keywords",
        headers=headers,
        params={"category": "macro", "q": term_tr[:6]},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["pagination"]["page"] == 1
    assert any(item["id"] == keyword_id for item in body["data"])

    # GET
    get_response = await api_client.get(
        f"/api/v1/admin/keywords/{keyword_id}", headers=headers
    )
    assert get_response.status_code == 200

    # UPDATE — categories replace (macro düşer, fmcg eklenir)
    update_response = await api_client.put(
        f"/api/v1/admin/keywords/{keyword_id}",
        headers=headers,
        json={
            "is_active": False,
            "categories": [
                {"category": "finance", "rating": 8},
                {"category": "fmcg", "rating": 4},
            ],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["is_active"] is False
    assert {c["category"]: c["rating"] for c in updated["categories"]} == {
        "finance": 8,
        "fmcg": 4,
    }

    # Replace semantiği: eski rating satırları sızmadı (DB'de yalnızca 2 satır)
    async with session_factory() as session:
        ratings = await session.execute(
            select(KeywordCategoryRating).where(
                KeywordCategoryRating.keyword_id == uuid.UUID(keyword_id)
            )
        )
        rows = ratings.scalars().all()
        assert len(rows) == 2
        assert {r.category.value for r in rows} == {"finance", "fmcg"}

        update_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "keyword.updated",
                AuditLog.target_id == uuid.UUID(keyword_id),
            )
        )
        assert update_audit.scalar_one_or_none() is not None

    # DELETE → 204
    delete_response = await api_client.delete(
        f"/api/v1/admin/keywords/{keyword_id}", headers=headers
    )
    assert delete_response.status_code == 204

    async with session_factory() as session:
        delete_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "keyword.deleted",
                AuditLog.target_id == uuid.UUID(keyword_id),
            )
        )
        assert delete_audit.scalar_one_or_none() is not None
        # CASCADE — rating satırları da silindi
        remaining = await session.execute(
            select(KeywordCategoryRating).where(
                KeywordCategoryRating.keyword_id == uuid.UUID(keyword_id)
            )
        )
        assert remaining.scalars().first() is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_forbidden_on_keywords(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/admin/keywords", headers=headers)
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "FORBIDDEN"

    create_response = await api_client.post(
        "/api/v1/admin/keywords",
        headers=headers,
        json=_keyword_payload(term_tr="viewer-tr", term_en="viewer-en"),
    )
    assert create_response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_keyword_returns_409(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    keyword_cleanup: list[uuid.UUID],
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    term_tr = f"yaptirim-{uuid.uuid4().hex[:8]}"
    term_en = f"sanctions-{uuid.uuid4().hex[:8]}"

    first = await api_client.post(
        "/api/v1/admin/keywords",
        headers=headers,
        json=_keyword_payload(term_tr=term_tr, term_en=term_en),
    )
    assert first.status_code == 201
    keyword_cleanup.append(uuid.UUID(first.json()["id"]))

    # Aynı term_tr farklı casing → 409
    dup = await api_client.post(
        "/api/v1/admin/keywords",
        headers=headers,
        json=_keyword_payload(term_tr=term_tr.upper(), term_en="baska-en"),
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "KEYWORD_DUPLICATE"


@pytest.mark.asyncio
async def test_invalid_rating_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    for bad_rating in (0, 11):
        payload = _keyword_payload(term_tr="rt-tr", term_en="rt-en")
        payload["categories"] = [{"category": "macro", "rating": bad_rating}]
        response = await api_client.post(
            "/api/v1/admin/keywords", headers=headers, json=payload
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_duplicate_category_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _keyword_payload(term_tr="dc-tr", term_en="dc-en")
    payload["categories"] = [
        {"category": "macro", "rating": 5},
        {"category": "macro", "rating": 7},
    ]
    response = await api_client.post(
        "/api/v1/admin/keywords", headers=headers, json=payload
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_empty_categories_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _keyword_payload(term_tr="ec-tr", term_en="ec-en")
    payload["categories"] = []
    response = await api_client.post(
        "/api/v1/admin/keywords", headers=headers, json=payload
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_unknown_keyword_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/admin/keywords/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "KEYWORD_NOT_FOUND"

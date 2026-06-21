"""Pipeline monitoring API integration testleri (Faz 6.1 — İterasyon 6).

Background driver no-op'a override edilir (gerçek AWS invoke / LLM çağrısı yok); run
`pending` kalır, böylece eşzamanlılık/iptal davranışı deterministik test edilir.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from apps.api.services.pipeline_service import pipeline_service
from httpx import AsyncClient
from packages.shared.models.pipeline_run import PipelineRun
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


async def _noop_driver(**_kwargs: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _patch_pipeline_driver() -> AsyncIterator[None]:
    original = pipeline_service._run_driver
    pipeline_service._run_driver = _noop_driver
    yield
    pipeline_service._run_driver = original


@pytest.fixture
async def cleanup_runs(database_url: str) -> AsyncIterator[None]:
    """Test admin'inin tetiklediği run'ları teardown'da temizler (cascade step'ler)."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield
    async with session_factory() as session:
        # Test DB izolasyonu — bu suite'in tetiklediği run'lar (cascade ile step'ler) silinir.
        await session.execute(delete(PipelineRun))
        await session.commit()
    await engine.dispose()


async def _trigger_collect(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    source_types: list[str] | None = None,
) -> Any:
    return await client.post(
        "/api/v1/pipeline/runs",
        headers=headers,
        json={"run_type": "collect_pipeline", "source_types": source_types or ["rss", "gov"]},
    )


@pytest.mark.asyncio
async def test_admin_triggers_collect_pipeline_returns_202(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await _trigger_collect(api_client, headers)
    assert response.status_code == 202
    body = response.json()
    assert body["run_type"] == "collect_pipeline"
    assert body["status"] == "pending"
    assert uuid.UUID(body["id"])


@pytest.mark.asyncio
async def test_trigger_detail_returns_four_steps_in_sequence(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    trigger = await _trigger_collect(api_client, headers)
    run_id = trigger.json()["id"]

    detail = await api_client.get(f"/api/v1/pipeline/runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["id"] == run_id
    assert data["source_types"] == ["rss", "gov"]
    sequences = [step["sequence"] for step in data["steps"]]
    assert sequences == [1, 2, 3, 4]
    stages = [step["stage"] for step in data["steps"]]
    assert stages == ["collect", "ingest", "process", "digest"]
    # collect_pipeline: collect/ingest/process pending, digest baştan skipped
    # (bülten ayrı digest_update ile üretilir).
    statuses = {step["stage"]: step["status"] for step in data["steps"]}
    assert statuses["collect"] == "pending"
    assert statuses["ingest"] == "pending"
    assert statuses["process"] == "pending"
    assert statuses["digest"] == "skipped"


@pytest.mark.asyncio
async def test_digest_update_skips_non_digest_stages(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    trigger = await api_client.post(
        "/api/v1/pipeline/runs",
        headers=headers,
        json={
            "run_type": "digest_update",
            "digest_type": "fmcg_weekly",
            "period_start": "2026-06-09",
            "period_end": "2026-06-15",
            "send_notification": False,
        },
    )
    assert trigger.status_code == 202
    run_id = trigger.json()["id"]

    detail = await api_client.get(f"/api/v1/pipeline/runs/{run_id}", headers=headers)
    steps = {step["stage"]: step["status"] for step in detail.json()["steps"]}
    assert steps["collect"] == "skipped"
    assert steps["ingest"] == "skipped"
    assert steps["process"] == "skipped"
    assert steps["digest"] == "pending"


@pytest.mark.asyncio
async def test_viewer_cannot_trigger_pipeline(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await _trigger_collect(api_client, headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_concurrent_collect_run_returns_409(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    first = await _trigger_collect(api_client, headers)
    assert first.status_code == 202

    second = await _trigger_collect(api_client, headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "PIPELINE_ALREADY_RUNNING"


@pytest.mark.asyncio
async def test_invalid_source_type_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await _trigger_collect(api_client, headers, source_types=["rss", "bogus"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SOURCE_TYPE"


@pytest.mark.asyncio
async def test_get_unknown_run_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/pipeline/runs/{uuid.uuid4()}",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PIPELINE_RUN_NOT_FOUND"


@pytest.mark.asyncio
async def test_cancel_then_double_cancel_returns_409(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    trigger = await _trigger_collect(api_client, headers)
    run_id = trigger.json()["id"]

    cancel = await api_client.post(
        f"/api/v1/pipeline/runs/{run_id}/cancel",
        headers=headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    again = await api_client.post(
        f"/api/v1/pipeline/runs/{run_id}/cancel",
        headers=headers,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "PIPELINE_NOT_CANCELLABLE"


@pytest.mark.asyncio
async def test_list_runs_returns_triggered_run(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    cleanup_runs: None,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    trigger = await _trigger_collect(api_client, headers)
    run_id = trigger.json()["id"]

    listing = await api_client.get(
        "/api/v1/pipeline/runs",
        headers=headers,
        params={"run_type": "collect_pipeline"},
    )
    assert listing.status_code == 200
    body = listing.json()
    ids = [run["id"] for run in body["data"]]
    assert run_id in ids
    found = next(run for run in body["data"] if run["id"] == run_id)
    assert found["triggered_by_name"] == "Admin Test User"
    assert "pagination" in body

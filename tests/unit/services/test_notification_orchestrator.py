"""NotificationOrchestrator unit testleri."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest
from packages.shared.enums import (
    DigestStatus,
    DigestType,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from services.ai_engine.exceptions import MailDeliveryError, PushDeliveryError
from services.ai_engine.notification_orchestrator import (
    NotificationOrchestrator,
    build_digest_teaser,
)
from services.ai_engine.notification_recipient_repository import DigestNotificationRecipient
from services.ai_engine.push_service import PushSendResult

_USER_EMAIL_ONLY = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_USER_PUSH_ONLY = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_USER_BOTH = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_USER_INACTIVE = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
_DIGEST_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _digest(*, with_section: bool = True) -> Digest:
    digest = Digest(
        id=_DIGEST_ID,
        digest_type=DigestType.FMCG_WEEKLY,
        title="FMCG Haftalık Bülten",
        status=DigestStatus.READY,
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 15),
    )
    if with_section:
        digest.sections = [
            DigestSection(
                digest_id=_DIGEST_ID,
                section_order=1,
                section_title="Pazar Özeti",
                ai_summary="Bu hafta perakende sektöründe öne çıkan gelişmeler.",
                impact_note="Orta etki",
                source_references=[],
            )
        ]
    return digest


def _recipients() -> list[DigestNotificationRecipient]:
    return [
        DigestNotificationRecipient(
            user_id=_USER_EMAIL_ONLY,
            email="email-only@example.com",
            email_enabled=True,
            push_enabled=False,
            fcm_token=None,
        ),
        DigestNotificationRecipient(
            user_id=_USER_PUSH_ONLY,
            email="push-only@example.com",
            email_enabled=False,
            push_enabled=True,
            fcm_token="push-token",
        ),
        DigestNotificationRecipient(
            user_id=_USER_BOTH,
            email="both@example.com",
            email_enabled=True,
            push_enabled=True,
            fcm_token="both-token",
        ),
    ]


@pytest.fixture
def db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mail_service() -> AsyncMock:
    service = AsyncMock()
    service.send_digest_ready = AsyncMock()
    return service


@pytest.fixture
def push_service() -> AsyncMock:
    service = AsyncMock()
    service.send_digest_ready = AsyncMock(
        return_value=PushSendResult(sent=1, failed=0, invalid_user_ids=()),
    )
    return service


@pytest.fixture
def preferences() -> AsyncMock:
    repo = AsyncMock()
    repo.list_active_digest_recipients = AsyncMock(return_value=_recipients())
    repo.clear_fcm_token = AsyncMock()
    return repo


@pytest.fixture
def logs() -> AsyncMock:
    repo = AsyncMock()
    repo.exists_for_digest_channel = AsyncMock(return_value=False)
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def digests() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=_digest())
    return repo


@pytest.fixture
def orchestrator(
    mail_service: AsyncMock,
    push_service: AsyncMock,
    preferences: AsyncMock,
    logs: AsyncMock,
    digests: AsyncMock,
) -> NotificationOrchestrator:
    return NotificationOrchestrator(
        mail_service=mail_service,
        push_service=push_service,
        preferences=preferences,
        logs=logs,
        digests=digests,
    )


@pytest.mark.asyncio
async def test_send_digest_ready_fan_out_mixed_preferences(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    mail_service: AsyncMock,
    push_service: AsyncMock,
    logs: AsyncMock,
) -> None:
    result = await orchestrator.send_digest_ready(db, digest=_digest())

    assert result.email_sent == 2
    assert result.email_failed == 0
    assert result.email_skipped == 1
    assert result.push_sent == 2
    assert result.push_failed == 0
    assert result.push_skipped == 1
    assert mail_service.send_digest_ready.await_count == 2
    assert push_service.send_digest_ready.await_count == 2
    assert logs.create.await_count == 4


@pytest.mark.asyncio
async def test_send_digest_ready_skips_inactive_users_via_recipient_list(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    preferences: AsyncMock,
    mail_service: AsyncMock,
) -> None:
    """Pasif kullanıcılar list_active_digest_recipients tarafından filtrelenir."""
    active_only = [item for item in _recipients() if item.user_id != _USER_INACTIVE]
    preferences.list_active_digest_recipients.return_value = active_only

    await orchestrator.send_digest_ready(db, digest=_digest())

    sent_emails = {
        call.kwargs["to"][0] for call in mail_service.send_digest_ready.await_args_list
    }
    assert "inactive@example.com" not in sent_emails


@pytest.mark.asyncio
async def test_send_digest_ready_logs_partial_push_failure(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    push_service: AsyncMock,
    logs: AsyncMock,
) -> None:
    async def push_side_effect(recipients, **_kwargs):
        if recipients[0].user_id == _USER_PUSH_ONLY:
            return PushSendResult(sent=0, failed=1, invalid_user_ids=(_USER_PUSH_ONLY,))
        return PushSendResult(sent=1, failed=0, invalid_user_ids=())

    push_service.send_digest_ready.side_effect = push_side_effect

    result = await orchestrator.send_digest_ready(db, digest=_digest())

    assert result.push_sent == 1
    assert result.push_failed == 1
    assert result.email_sent == 2

    create_calls = logs.create.await_args_list
    push_logs = [
        call.kwargs
        for call in create_calls
        if call.kwargs["channel"] == NotificationChannel.PUSH
    ]
    assert len(push_logs) == 2
    assert any(item["status"] == NotificationStatus.SENT for item in push_logs)
    failed_log = next(
        item for item in push_logs if item["status"] == NotificationStatus.FAILED
    )
    assert failed_log["error_message"] is not None


@pytest.mark.asyncio
async def test_send_digest_ready_logs_email_failure_separately(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    mail_service: AsyncMock,
    logs: AsyncMock,
) -> None:
    mail_service.send_digest_ready.side_effect = MailDeliveryError("SMTP gönderimi başarısız.")

    result = await orchestrator.send_digest_ready(db, digest=_digest())

    assert result.email_sent == 0
    assert result.email_failed == 2
    email_logs = [
        call.kwargs
        for call in logs.create.await_args_list
        if call.kwargs["channel"] == NotificationChannel.EMAIL
    ]
    assert len(email_logs) == 2
    assert all(item["status"] == NotificationStatus.FAILED for item in email_logs)


@pytest.mark.asyncio
async def test_send_digest_ready_is_idempotent_on_second_call(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    mail_service: AsyncMock,
    push_service: AsyncMock,
    logs: AsyncMock,
) -> None:
    existing: set[tuple[uuid.UUID, NotificationChannel]] = set()

    async def exists_side_effect(_db, *, digest_id, user_id, channel):
        return (digest_id, user_id, channel) in existing

    async def create_side_effect(_db, *, user_id, digest_id, channel, **_kwargs):
        existing.add((digest_id, user_id, channel))

    logs.exists_for_digest_channel.side_effect = exists_side_effect
    logs.create.side_effect = create_side_effect

    first = await orchestrator.send_digest_ready(db, digest=_digest())
    second = await orchestrator.send_digest_ready(db, digest=_digest())

    assert first.email_sent == 2
    assert first.push_sent == 2
    assert second.email_sent == 0
    assert second.push_sent == 0
    assert second.email_skipped == 3
    assert second.push_skipped == 3
    assert mail_service.send_digest_ready.await_count == 2
    assert push_service.send_digest_ready.await_count == 2


@pytest.mark.asyncio
async def test_send_digest_ready_push_transport_error_logs_failed(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    push_service: AsyncMock,
    logs: AsyncMock,
) -> None:
    push_service.send_digest_ready.side_effect = PushDeliveryError(
        "FCM multicast gönderimi başarısız",
    )

    result = await orchestrator.send_digest_ready(db, digest=_digest())

    assert result.push_failed == 2
    push_logs = [
        call.kwargs
        for call in logs.create.await_args_list
        if call.kwargs["channel"] == NotificationChannel.PUSH
    ]
    assert len(push_logs) == 2
    assert all(item["status"] == NotificationStatus.FAILED for item in push_logs)


@pytest.mark.asyncio
async def test_send_digest_ready_writes_correct_log_metadata(
    orchestrator: NotificationOrchestrator,
    db: AsyncMock,
    logs: AsyncMock,
) -> None:
    await orchestrator.send_digest_ready(db, digest=_digest())

    first_log = logs.create.await_args_list[0].kwargs
    assert first_log["digest_id"] == _DIGEST_ID
    assert first_log["notification_type"] == NotificationType.DIGEST_READY.value


def test_build_digest_teaser_uses_first_section_summary() -> None:
    teaser = build_digest_teaser(_digest())
    assert teaser == "Bu hafta perakende sektöründe öne çıkan gelişmeler."


def test_build_digest_teaser_falls_back_to_title() -> None:
    digest = _digest(with_section=False)
    assert build_digest_teaser(digest) == digest.title

"""FCMPushService unit testleri."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from firebase_admin import messaging
from services.ai_engine.exceptions import PushDeliveryError
from services.ai_engine.push_service import (
    DIGEST_READY_TITLE,
    FCMPushService,
    PushRecipient,
)

_USER_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_USER_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_USER_C = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_DIGEST_ID = UUID("11111111-1111-4111-8111-111111111111")


@dataclass
class FakeSendResponse:
    success: bool
    exception: Exception | None = None


@dataclass
class FakeBatchResponse:
    responses: list[FakeSendResponse]


class UnregisteredTokenError(Exception):
    """Firebase UNREGISTERED token hatası simülasyonu."""


@pytest.fixture
def recipients() -> list[PushRecipient]:
    return [
        PushRecipient(user_id=_USER_A, fcm_token="token-a"),
        PushRecipient(user_id=_USER_B, fcm_token="token-b"),
        PushRecipient(user_id=_USER_C, fcm_token="token-c"),
    ]


@pytest.mark.asyncio
async def test_send_multicast_empty_recipients_is_noop() -> None:
    called = False

    def fake_sender(_message: messaging.MulticastMessage) -> FakeBatchResponse:
        nonlocal called
        called = True
        return FakeBatchResponse(responses=[])

    service = FCMPushService(multicast_sender=fake_sender)

    result = await service.send_multicast([], title="Başlık", body="Gövde")

    assert result.sent == 0
    assert result.failed == 0
    assert result.invalid_user_ids == ()
    assert called is False


@pytest.mark.asyncio
async def test_send_multicast_calls_firebase_with_expected_payload(
    recipients: list[PushRecipient],
) -> None:
    captured: dict[str, object] = {}

    def fake_sender(message: messaging.MulticastMessage) -> FakeBatchResponse:
        captured["message"] = message
        return FakeBatchResponse(
            responses=[FakeSendResponse(success=True) for _ in recipients],
        )

    service = FCMPushService(multicast_sender=fake_sender)

    result = await service.send_multicast(
        recipients,
        title="Test başlık",
        body="Test gövde",
        data={"digest_id": str(_DIGEST_ID), "digest_type": "fmcg_weekly"},
    )

    message = captured["message"]
    assert message.tokens == ["token-a", "token-b", "token-c"]
    assert message.notification is not None
    assert message.notification.title == "Test başlık"
    assert message.notification.body == "Test gövde"
    assert message.data == {
        "digest_id": str(_DIGEST_ID),
        "digest_type": "fmcg_weekly",
    }
    assert result.sent == 3
    assert result.failed == 0


@pytest.mark.asyncio
async def test_send_multicast_clears_invalid_tokens(recipients: list[PushRecipient]) -> None:
    cleared_user_ids: list[UUID] = []

    async def cleanup(user_id: UUID) -> None:
        cleared_user_ids.append(user_id)

    def fake_sender(_message: messaging.MulticastMessage) -> FakeBatchResponse:
        return FakeBatchResponse(
            responses=[
                FakeSendResponse(success=True),
                FakeSendResponse(
                    success=False,
                    exception=UnregisteredTokenError(
                        "Requested entity was not found. UNREGISTERED",
                    ),
                ),
                FakeSendResponse(success=True),
            ],
        )

    service = FCMPushService(multicast_sender=fake_sender, token_cleanup=cleanup)

    result = await service.send_multicast(
        recipients,
        title=DIGEST_READY_TITLE,
        body="Özet",
    )

    assert result.sent == 2
    assert result.failed == 1
    assert result.invalid_user_ids == (_USER_B,)
    assert cleared_user_ids == [_USER_B]


@pytest.mark.asyncio
async def test_send_multicast_does_not_clear_on_transient_error(
    recipients: list[PushRecipient],
) -> None:
    cleared_user_ids: list[UUID] = []

    async def cleanup(user_id: UUID) -> None:
        cleared_user_ids.append(user_id)

    def fake_sender(_message: messaging.MulticastMessage) -> FakeBatchResponse:
        return FakeBatchResponse(
            responses=[
                FakeSendResponse(
                    success=False,
                    exception=RuntimeError("503 service unavailable"),
                ),
                FakeSendResponse(success=True),
                FakeSendResponse(success=True),
            ],
        )

    service = FCMPushService(multicast_sender=fake_sender, token_cleanup=cleanup)

    result = await service.send_multicast(
        recipients,
        title=DIGEST_READY_TITLE,
        body="Özet",
    )

    assert result.sent == 2
    assert result.failed == 1
    assert result.invalid_user_ids == ()
    assert cleared_user_ids == []


@pytest.mark.asyncio
async def test_send_digest_ready_uses_turkish_title_and_truncated_teaser(
    recipients: list[PushRecipient],
) -> None:
    captured: dict[str, object] = {}
    long_teaser = "A" * 200

    def fake_sender(message: messaging.MulticastMessage) -> FakeBatchResponse:
        captured["message"] = message
        return FakeBatchResponse(
            responses=[FakeSendResponse(success=True) for _ in recipients],
        )

    service = FCMPushService(multicast_sender=fake_sender)

    await service.send_digest_ready(
        recipients,
        teaser=long_teaser,
        digest_id=_DIGEST_ID,
        digest_type="strategy_weekly",
    )

    message = captured["message"]
    assert message.notification is not None
    assert message.notification.title == DIGEST_READY_TITLE
    assert message.notification.title == "Yeni bülten hazır"
    assert len(message.notification.body) == 120
    assert message.notification.body.endswith("…")
    assert message.data == {
        "digest_id": str(_DIGEST_ID),
        "digest_type": "strategy_weekly",
    }


@pytest.mark.asyncio
async def test_send_multicast_raises_on_transport_failure(
    recipients: list[PushRecipient],
) -> None:
    def fake_sender(_message: messaging.MulticastMessage) -> FakeBatchResponse:
        raise ConnectionError("network down")

    service = FCMPushService(multicast_sender=fake_sender)

    with pytest.raises(PushDeliveryError, match="FCM multicast gönderimi başarısız"):
        await service.send_multicast(
            recipients,
            title=DIGEST_READY_TITLE,
            body="Özet",
        )


def test_truncate_teaser_keeps_short_text_unchanged() -> None:
    teaser = "Kısa özet metni."
    assert FCMPushService.truncate_teaser(teaser) == teaser


def test_truncate_teaser_shortens_long_text() -> None:
    teaser = "B" * 150
    truncated = FCMPushService.truncate_teaser(teaser)
    assert len(truncated) == 120
    assert truncated.endswith("…")

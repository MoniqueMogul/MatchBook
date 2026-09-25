from types import SimpleNamespace
from uuid import uuid4

from app.events.payload_schema import NdaCompletedPayload
from app.nda.service import NDAService
from app.notification.handlers import _handle_nda_completed


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.created_events = []

    def get_by_idempotency_key(self, _idempotency_key):
        return None

    def create_event(self, event):
        self.created_events.append(event)
        return event


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.created_notifications = []

    def create_notification(self, *, user_id, data):
        self.created_notifications.append(
            {
                "user_id": user_id,
                "data": data,
            }
        )


def build_nda():
    buyer_user_id = uuid4()
    seller_user_id = uuid4()

    nda = SimpleNamespace(
        id=uuid4(),
        match_id=uuid4(),
        match=SimpleNamespace(
            buyer=SimpleNamespace(
                user_id=buyer_user_id,
            ),
            business=SimpleNamespace(
                seller=SimpleNamespace(
                    user_id=seller_user_id,
                ),
            ),
        ),
    )

    return nda, buyer_user_id, seller_user_id


def test_completed_event_contains_both_participants() -> None:
    nda, buyer_user_id, seller_user_id = build_nda()

    repository = FakeOutboxRepository()

    service = NDAService.__new__(NDAService)
    service.outbox_repository = repository

    service._create_completed_event(nda=nda)

    assert len(repository.created_events) == 1

    event = repository.created_events[0]
    payload = NdaCompletedPayload.model_validate(
        event.payload
    )

    assert set(payload.user_ids) == {
        buyer_user_id,
        seller_user_id,
    }
    assert payload.nda_id == nda.id
    assert payload.match_id == nda.match_id


def test_completion_notifies_both_participants() -> None:
    nda, buyer_user_id, seller_user_id = build_nda()

    repository = FakeNotificationRepository()

    payload = NdaCompletedPayload(
        user_ids=[
            buyer_user_id,
            seller_user_id,
        ],
        nda_id=nda.id,
        match_id=nda.match_id,
    )

    _handle_nda_completed(
        payload=payload,
        repository=repository,
    )

    notified_user_ids = {
        item["user_id"]
        for item in repository.created_notifications
    }

    assert notified_user_ids == {
        buyer_user_id,
        seller_user_id,
    }


def test_duplicate_participant_is_not_notified_twice() -> None:
    user_id = uuid4()

    repository = FakeNotificationRepository()

    payload = NdaCompletedPayload(
        user_ids=[
            user_id,
            user_id,
        ],
        nda_id=uuid4(),
        match_id=uuid4(),
    )

    _handle_nda_completed(
        payload=payload,
        repository=repository,
    )

    assert len(repository.created_notifications) == 1
    assert (
        repository.created_notifications[0]["user_id"]
        == user_id
    )

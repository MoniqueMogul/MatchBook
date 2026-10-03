"""Seller inbox access uses authoritative NDA state and a post-NDA buyer message."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from test_business_image_visibility import flow
from app.chat.service import ChatService, ChatAccessDeniedError
from app.chat.schema import MessageCreate
from app.db.db_model import NDA, Message


def test_verified_inbound_conversation_and_reply(flow):
    _, _, session, buyer, _, seller, _, match, _ = flow
    service = ChatService(session)
    response = service.list_conversations(seller.id)
    assert len(response) == 1
    assert response[0].seller_inbox_eligible and response[0].nda_completed
    message, event = service.send_message(conversation_id=match.conversation.id, user_id=seller.id, data=MessageCreate(content="Thanks for reaching out"))
    assert message.sender_id == seller.id
    assert event.payload['recipient_user_id'] == str(buyer.id)


@pytest.mark.parametrize('case', ['missing_nda', 'pending', 'buyer_signed', 'expired', 'no_buyer_signature', 'no_seller_signature', 'unverified', 'no_message', 'seller_only', 'before_nda'])
def test_ineligible_conversations_are_hidden_and_direct_access_denied(flow, case):
    _, _, session, buyer, _, seller, _, match, _ = flow
    nda = session.scalar(select(NDA))
    message = session.scalar(select(Message))
    if case == 'missing_nda': session.delete(nda)
    elif case in ('pending', 'buyer_signed', 'expired'): nda.status = case
    elif case == 'no_buyer_signature': nda.buyer_signed_at = None
    elif case == 'no_seller_signature': nda.seller_signed_at = None
    elif case == 'no_message': session.delete(message)
    elif case == 'seller_only': message.sender_id = seller.id
    elif case == 'before_nda': message.created_at = nda.completed_at - timedelta(seconds=1)
    session.commit()
    with patch('app.chat.service.NDAEligibilityService') as eligibility:
        eligibility.return_value.get_nda_eligibility.return_value.eligible = case != 'unverified'
        service = ChatService(session)
        assert service.list_conversations(seller.id) == []
        with pytest.raises(ChatAccessDeniedError):
            service.get_messages(conversation_id=match.conversation.id, user_id=seller.id)
        with pytest.raises(ChatAccessDeniedError):
            service.send_message(conversation_id=match.conversation.id, user_id=seller.id, data=MessageCreate(content="Unsolicited"))


def test_seller_cannot_start_conversation_even_with_completed_nda(flow):
    _, _, session, _, _, seller, _, match, _ = flow
    with pytest.raises(ChatAccessDeniedError):
        ChatService(session).create_conversation(match_id=match.id, user_id=seller.id)


def test_buyer_cannot_send_before_completed_nda(flow):
    _, _, session, buyer, _, _, _, match, _ = flow
    session.scalar(select(NDA)).status = 'pending'
    session.commit()
    with pytest.raises(ChatAccessDeniedError):
        ChatService(session).send_message(conversation_id=match.conversation.id, user_id=buyer.id, data=MessageCreate(content="Too early"))


def test_other_user_cannot_read_or_reply(flow):
    _, _, session, _, other, _, _, match, _ = flow
    service = ChatService(session)
    assert service.list_conversations(other.id) == []
    with pytest.raises(ChatAccessDeniedError):
        service.get_messages(conversation_id=match.conversation.id, user_id=other.id)


def test_structured_location_round_trips_for_buyer_and_seller(flow):
    from app.db.db_model import BuyerPreferences
    from app.intake.repository import IntakeRepository
    from app.intake.schemas.buyer_preferences import BuyerPreferencesUpsert
    from app.intake.schemas.business import BusinessUpdate
    _, _, session, buyer, _, seller, business, _, _ = flow
    BuyerPreferences.__table__.create(session.bind)
    fields = dict(city="Austin", state="Texas", county="Travis County", zip_code="78701")
    repository = IntakeRepository(session)
    repository.upsert_buyer_preferences(buyer.id, BuyerPreferencesUpsert(target_locations=[fields]))
    repository.update_business(seller.id, business.id, BusinessUpdate(**fields))
    session.commit()
    session.expire_all()
    preferences = repository.get_buyer_preferences_by_user_id(buyer.id)
    saved = repository.get_business_for_seller(seller.id, business.id)
    for key, value in fields.items():
        assert preferences.target_locations[0][key] == getattr(saved, key) == value

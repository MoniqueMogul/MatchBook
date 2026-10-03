"""Photo visibility through real match/chat queries; no external services."""
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

auth_stub = ModuleType('app.auth.auth')
auth_stub.supabase = MagicMock()
sys.modules.setdefault('app.auth.auth', auth_stub)

from app.auth.dependencies import get_current_user_id
from app.db.database import get_db
from app.db.db_model import User, SellerProfile, Business, BuyerProfile, Match, Conversation, Message, NDA, OutboxEvent
from app.db.db_enum import BusinessType, Industry, SubIndustry, BusinessModel, BusinessStatus
from app.matching import routes
from app.chat.service import ChatService
from app.verification import business_images
from app.verification.exceptions import ProviderError, ProviderConfigurationError


@compiles(JSONB, 'sqlite')
def sqlite_jsonb(element, compiler, **kwargs):
    return 'JSON'


@pytest.fixture
def flow():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    for model in (User, SellerProfile, Business, BuyerProfile, Match, Conversation, Message, NDA, OutboxEvent):
        model.__table__.create(engine)
    with Session(engine) as session:
        owner, buyer_user, other_user = [User(id=uuid4(), first_name='Private', last_name='Person') for _ in range(3)]
        seller = SellerProfile(id=uuid4(), user=owner)
        buyer = BuyerProfile(id=uuid4(), user=buyer_user)
        other = BuyerProfile(id=uuid4(), user=other_user)
        business = Business(id=uuid4(), seller=seller, city='Austin', state='Texas',
                            legal_name='Business', idempotency_key=str(uuid4()), status=BusinessStatus.ACTIVE,
                            business_type=next(iter(BusinessType)), industry=next(iter(Industry)),
                            sub_industry=next(iter(SubIndustry)), business_model=next(iter(BusinessModel)))
        business.profile_image_key = f'profile-images/businesses/{business.id}/photo.webp'
        match = Match(id=uuid4(), buyer=buyer, business=business, score=Decimal('0.9'), matching_version='test')
        conversation = Conversation(id=uuid4(), match=match)
        session.add_all([owner, buyer_user, other_user, seller, buyer, other, business, match, conversation])
        completed = datetime.now(timezone.utc) - timedelta(minutes=5)
        session.add(NDA(match=match, status="completed", version="test", buyer_signed_at=completed, seller_signed_at=completed, completed_at=completed))
        session.add(Message(conversation=conversation, sender_id=buyer_user.id, content="Hello", created_at=completed + timedelta(minutes=1)))
        session.commit()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_current_user_id] = lambda: buyer_user.id
        app.dependency_overrides[get_db] = lambda: session
        with patch.object(business_images, 'R2DocumentStorage') as factory, patch('app.chat.service.NDAEligibilityService') as eligibility:
            eligibility.return_value.get_nda_eligibility.return_value.eligible = True
            factory.return_value.presign_download.return_value = ('https://images.example/business?signature=test', 900)
            with TestClient(app) as client:
                yield app, client, session, buyer_user, other_user, owner, business, match, factory
    engine.dispose()


def test_matched_buyer_sees_business_photo_without_private_fields(flow):
    _, client, _, _, _, _, business, match, factory = flow
    for url in ('/api/matches', f'/api/matches/{match.id}'):
        response = client.get(url)
        assert response.status_code == 200, response.text
        data = response.json()
        public_business = (data['matches'][0] if 'matches' in data else data)['business']
        assert public_business['profile_image_url'] == 'https://images.example/business?signature=test'
        assert not {'profile_image_key', 'seller_id', 'user_id', 'email', 'phone', 'first_name', 'last_name'} & public_business.keys()
    factory.return_value.presign_download.assert_called_with(business.profile_image_key)


def test_unmatched_buyer_cannot_obtain_photo(flow):
    app, client, _, _, other, _, _, match, factory = flow
    app.dependency_overrides[get_current_user_id] = lambda: other.id
    assert client.get('/api/matches').json()['matches'] == []
    assert client.get(f'/api/matches/{match.id}').status_code == 404
    factory.assert_not_called()


def test_unauthenticated_request_cannot_obtain_photo(flow):
    app, client, _, _, _, _, _, match, factory = flow
    del app.dependency_overrides[get_current_user_id]
    assert client.get('/api/matches').status_code == 401
    assert client.get(f'/api/matches/{match.id}').status_code == 401
    factory.assert_not_called()


def test_conversation_photo_only_for_participants(flow):
    _, _, session, buyer, other, owner, _, _, factory = flow
    service = ChatService(session)
    assert service.list_conversations(other.id) == []
    factory.assert_not_called()
    for user in (buyer, owner):
        result = service.list_conversations(user.id)
        assert len(result) == 1
        data = result[0].business.model_dump()
        assert data['profile_image_url'] == 'https://images.example/business?signature=test'
        assert not {'profile_image_key', 'seller_id', 'user_id', 'email', 'phone', 'first_name', 'last_name'} & data.keys()


@pytest.mark.parametrize('key', [None, '', 'profile-images/users/private/photo.webp', 'profile-images/businesses/another/photo.webp'])
def test_missing_or_unrelated_image_is_not_signed(flow, key):
    _, client, session, _, _, _, business, match, factory = flow
    business.profile_image_key = key
    session.commit()
    assert client.get(f'/api/matches/{match.id}').json()['business']['profile_image_url'] is None
    factory.assert_not_called()


@pytest.mark.parametrize('error', [ProviderError('unavailable'), ProviderConfigurationError('missing config')])
def test_storage_failure_preserves_matches_and_conversations(flow, error):
    _, client, session, buyer, _, _, _, match, factory = flow
    factory.return_value.presign_download.side_effect = error
    assert client.get('/api/matches').json()['matches'][0]['business']['profile_image_url'] is None
    assert client.get(f'/api/matches/{match.id}').json()['business']['profile_image_url'] is None
    assert ChatService(session).list_conversations(buyer.id)[0].business.profile_image_url is None

"""Focused tests: real routes/repository, isolated SQLite, mocked R2/Auth."""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

auth_stub = ModuleType('app.auth.auth')
auth_stub.supabase = MagicMock()
sys.modules.setdefault('app.auth.auth', auth_stub)

from app.auth.dependencies import get_current_user_id
from app.db.db_model import User, Business, SellerProfile
from app.db.db_enum import BusinessType, Industry, SubIndustry, BusinessModel
from app.intake.dependencies import get_intake_repository
from app.intake.repository import IntakeRepository
from app.intake import routes
from app.verification.config import VerificationSettings
from app.verification.integrations.storage import R2DocumentStorage
from app.verification.exceptions import ProviderError, ProviderConfigurationError


@pytest.fixture
def flow():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    for model in (User, SellerProfile, Business):
        model.__table__.create(engine)
    with Session(engine) as session:
        owner, other, seller, business = uuid4(), uuid4(), uuid4(), uuid4()
        session.add_all([User(id=owner, first_name='A', last_name='B'), User(id=other, first_name='C', last_name='D')])
        session.flush()
        session.add(SellerProfile(id=seller, user_id=owner))
        session.flush()
        session.add(Business(id=business, seller_id=seller, city='Austin', state='Texas', idempotency_key=str(uuid4()), business_type=next(iter(BusinessType)), industry=next(iter(Industry)), sub_industry=next(iter(SubIndustry)), business_model=next(iter(BusinessModel))))
        session.commit()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_intake_repository] = lambda: IntakeRepository(session)
        app.dependency_overrides[get_current_user_id] = lambda: owner
        with patch.object(routes, '_get_profile_storage') as factory:
            storage = factory.return_value
            storage.object_exists.return_value = True
            storage.presign_upload.return_value = ('https://example.test/upload', 900)
            with TestClient(app) as client:
                yield app, client, session, owner, other, business, storage, factory
    engine.dispose()


def target(flow, kind):
    _, _, _, owner, _, business, _, _ = flow
    if kind == 'business':
        return f'/intake/sellers/businesses/{business}/profile-image', f'profile-images/businesses/{business}/test.webp', Business, business
    return '/intake/user/profile-image', f'profile-images/users/{owner}/test.webp', User, owner


@pytest.mark.parametrize('kind', ['user', 'business'])
def test_confirmation_persists_and_serializes(flow, kind):
    _, client, session, _, _, _, storage, _ = flow
    url, key, model, entity_id = target(flow, kind)
    for suffix in ('', '.replacement'):
        response = client.put(url, json={'object_key': key + suffix})
        assert response.status_code == 200, response.text
        assert response.json()['profile_image_key'] == key + suffix
        with Session(session.bind) as independent:
            assert independent.get(model, entity_id).profile_image_key == key + suffix
    storage.object_exists.assert_called_with(key + '.replacement')


@pytest.mark.parametrize('kind', ['user', 'business'])
@pytest.mark.parametrize('bad', ['', 'unrelated/file.webp', 'profile-images/users/other/test.webp'])
def test_invalid_prefix(flow, kind, bad):
    _, client, session, _, _, _, storage, factory = flow
    url, _, model, entity_id = target(flow, kind)
    assert client.put(url, json={'object_key': bad}).status_code == 400
    factory.assert_not_called()
    assert session.get(model, entity_id).profile_image_key is None


@pytest.mark.parametrize('kind', ['user', 'business'])
def test_missing_object(flow, kind):
    _, client, session, _, _, _, storage, _ = flow
    url, key, model, entity_id = target(flow, kind)
    storage.object_exists.return_value = False
    response = client.put(url, json={'object_key': key})
    assert response.status_code == 400
    assert 'has not been uploaded' in response.json()['detail']
    assert session.get(model, entity_id).profile_image_key is None


@pytest.mark.parametrize('kind', ['user', 'business'])
@pytest.mark.parametrize('payload', [{}, {'object_key': None}, {'object_key': 12}])
def test_invalid_schema(flow, kind, payload):
    url, *_ = target(flow, kind)
    assert flow[1].put(url, json=payload).status_code == 422
    flow[7].assert_not_called()


@pytest.mark.parametrize('kind', ['user', 'business'])
@pytest.mark.parametrize('method', ['put', 'post'])
@pytest.mark.parametrize('invalid_token', [False, True])
def test_authentication(flow, kind, method, invalid_token):
    app, client, _, _, _, _, _, factory = flow
    del app.dependency_overrides[get_current_user_id]
    url, key, *_ = target(flow, kind)
    headers = {'Authorization': 'Bearer invalid'} if invalid_token else {}
    with patch('app.auth.dependencies.supabase') as supabase:
        supabase.auth.get_user.side_effect = RuntimeError('invalid token')
        response = getattr(client, method)(url + ('/upload-url' if method == 'post' else ''), json={'object_key': key, 'content_type': 'image/webp'}, headers=headers)
    assert response.status_code == 401
    factory.assert_not_called()


@pytest.mark.parametrize('scenario', ['not_owned', 'nonexistent'])
@pytest.mark.parametrize('method', ['put', 'post'])
def test_business_ownership(flow, scenario, method):
    app, client, session, _, other, business, _, _ = flow
    if scenario == 'not_owned':
        app.dependency_overrides[get_current_user_id] = lambda: other
    requested = uuid4() if scenario == 'nonexistent' else business
    url = f'/intake/sellers/businesses/{requested}/profile-image'
    response = getattr(client, method)(url + ('/upload-url' if method == 'post' else ''), json={'object_key': f'profile-images/businesses/{requested}/x.webp', 'content_type': 'image/webp'})
    assert response.status_code == 404, response.text
    assert session.get(Business, business).profile_image_key is None


def test_missing_user(flow):
    app, client, *_ = flow
    missing = uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: missing
    assert client.put('/intake/user/profile-image', json={'object_key': f'profile-images/users/{missing}/x.webp'}).status_code == 404


@pytest.mark.parametrize('kind', ['user', 'business'])
@pytest.mark.parametrize('mime,extension', [('image/jpeg', 'jpg'), ('image/png', 'png'), ('image/webp', 'webp')])
def test_upload(flow, kind, mime, extension):
    url, key, *_ = target(flow, kind)
    response = flow[1].post(url + '/upload-url', json={'content_type': mime})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['object_key'].startswith(key.rsplit('/', 1)[0] + '/')
    assert data['object_key'].endswith('.' + extension)
    assert data['required_headers'] == {'Content-Type': mime}
    assert data['expires_in_seconds'] == 900
    flow[6].presign_upload.assert_called_once_with(data['object_key'], mime)


@pytest.mark.parametrize('kind', ['user', 'business'])
def test_unsupported_type(flow, kind):
    url, *_ = target(flow, kind)
    assert flow[1].post(url + '/upload-url', json={'content_type': 'text/html'}).status_code == 400
    flow[7].assert_not_called()


@pytest.mark.parametrize('code', ['404', 'NoSuchKey', 'NotFound', '403', '500'])
def test_r2_head_errors(code):
    storage = R2DocumentStorage(VerificationSettings(r2_bucket_name='test-bucket'))
    storage._client = MagicMock()
    error = RuntimeError('fake provider failure')
    error.response = {'Error': {'Code': code}}
    storage._client.head_object.side_effect = error
    if code in {'404', 'NoSuchKey', 'NotFound'}:
        assert storage.object_exists('key') is False
    else:
        with pytest.raises(ProviderError):
            storage.object_exists('key')
    storage._client.head_object.assert_called_once_with(Bucket='test-bucket', Key='key')


def test_r2_head_success_and_configuration():
    storage = R2DocumentStorage(VerificationSettings())
    with pytest.raises(ProviderConfigurationError):
        storage.object_exists('key')
    storage._client = MagicMock()
    assert storage.object_exists('key') is True


def test_storage_wiring():
    settings = VerificationSettings(r2_bucket_name='test-bucket')
    with patch.object(routes.VerificationSettings, 'from_env', return_value=settings):
        storage = routes._get_profile_storage()
    assert isinstance(storage, R2DocumentStorage)
    assert storage.settings is settings
    assert storage.bucket_name == 'test-bucket'


@pytest.mark.parametrize('kind', ['user', 'business'])
@pytest.mark.parametrize('method', ['put', 'post'])
@pytest.mark.parametrize('error,expected', [(ProviderConfigurationError, 503), (ProviderError, 502)])
def test_provider_failure_response(flow, kind, method, error, expected):
    url, key, model, entity_id = target(flow, kind)
    operation = flow[6].object_exists if method == 'put' else flow[6].presign_upload
    operation.side_effect = error('Simulated R2 failure')
    with TestClient(flow[0], raise_server_exceptions=False) as client:
        response = getattr(client, method)(url + ('/upload-url' if method == 'post' else ''), json={'object_key': key, 'content_type': 'image/webp'})
    assert response.status_code == expected, response.text
    assert flow[2].get(model, entity_id).profile_image_key is None


def test_migration_upgrade_downgrade():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    path = Path(routes.__file__).resolve().parents[2] / 'alembic/versions/f37c9021ab41_add_profile_image_keys.py'
    spec = importlib.util.spec_from_file_location('image_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        for table in ('users', 'businesses'):
            connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
            connection.exec_driver_sql(f'INSERT INTO {table} (id) VALUES (1)')
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            for table in ('users', 'businesses'):
                columns = {c['name']: c for c in inspect(connection).get_columns(table)}
                assert columns['profile_image_key']['nullable']
                assert columns['profile_image_key']['type'].length == 500
                assert connection.exec_driver_sql(f'SELECT profile_image_key FROM {table}').scalar() is None
            migration.downgrade()
            for table in ('users', 'businesses'):
                assert [c['name'] for c in inspect(connection).get_columns(table)] == ['id']
    engine.dispose()


def test_r2_client_and_presign_wiring():
    settings = VerificationSettings(r2_account_id='fake-account', r2_access_key_id='fake-key', r2_secret_access_key='fake-secret', r2_bucket_name='test-bucket')
    storage = R2DocumentStorage(settings)
    with patch('boto3.client') as factory:
        factory.return_value.generate_presigned_url.return_value = 'https://example.test/upload'
        assert storage.presign_upload('image.webp', 'image/webp') == ('https://example.test/upload', 900)
        assert storage.object_exists('image.webp') is True
        factory.assert_called_once()
        assert factory.call_args.kwargs['endpoint_url'] == 'https://fake-account.r2.cloudflarestorage.com'
        assert factory.call_args.kwargs['config'].signature_version == 's3v4'
        factory.return_value.generate_presigned_url.assert_called_once_with('put_object', Params={'Bucket': 'test-bucket', 'Key': 'image.webp', 'ContentType': 'image/webp'}, ExpiresIn=900)

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from Api import routes
from Api.deletion_ledger import read_receipt
from Api.org_access import AdminScope
from Api.schemas import AdminAccountPurgeRequest


class Connection:
    def __init__(self, *, memberships=(), last_admin=False, account=None, verified_aliases=()):
        self.memberships = list(memberships)
        self.last_admin = last_admin
        self.account = account or {'id': 12, 'email': 'person@example.test'}
        self.verified_aliases = set(verified_aliases)
        self.committed = False
        self.rolled_back = False
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        query = str(query)
        self.statements.append((query, params))
        if 'SELECT pg_advisory_xact_lock' in query:
            return SimpleNamespace()
        if 'SELECT id,email FROM users' in query:
            return SimpleNamespace(fetchone=lambda: self.account)
        if 'SELECT 1 FROM user_identities' in query:
            return SimpleNamespace(fetchone=lambda: {'protected': 1}
                if self.verified_aliases.intersection(params[1]) else None)
        if 'SELECT organization_id,role,is_participant' in query:
            return SimpleNamespace(fetchall=lambda: self.memberships)
        if "role='admin' ORDER BY organization_id FOR SHARE" in query:
            return SimpleNamespace(fetchall=lambda: [])
        if 'SELECT id FROM organizations' in query:
            return SimpleNamespace(fetchall=lambda: [])
        if "HAVING COUNT(*)<=1" in query:
            return SimpleNamespace(fetchone=lambda: {'organization_id': 3} if self.last_admin else None)
        raise AssertionError(query)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def membership(*, organization_id=3, role='member', participant=True):
    return {'organization_id': organization_id, 'role': role, 'is_participant': participant}


def prepare(monkeypatch, connection, *, superadmin=False):
    scope = AdminScope(is_superadmin=superadmin, organization_ids=(3,), actor_user_id=99)
    actor = SimpleNamespace(id=99)
    monkeypatch.setattr(routes, '_physical_organization_purge_available', lambda: True)
    monkeypatch.setattr(routes, '_get_admin_scope_or_403', lambda *_args, **_kwargs: scope)
    monkeypatch.setattr(routes, 'get_connection', lambda: connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', lambda _token: actor)
    monkeypatch.setattr(routes, 'configured_superadmin_emails', lambda: set())
    monkeypatch.setattr(routes, 'configured_org_admin_emails', lambda: {})
    monkeypatch.setattr(routes, 'read_receipt', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, 'record_receipt', lambda *_args: None)
    monkeypatch.setattr(routes, 'require_account_plan_organization_scope', lambda *_args, **_kwargs: None)
    return SimpleNamespace(cookies={}), scope, actor


def payload():
    return AdminAccountPurgeRequest(confirmation_email='person@example.test',
        preview_fingerprint='a' * 64, operation_id='delete-person-1', acknowledge_irreversible=True)


@pytest.mark.parametrize(('memberships', 'detail'), [
    ([membership(organization_id=4)], 'ACCOUNT_PURGE_SCOPE_FORBIDDEN'),
    ([membership(participant=False)], 'ACCOUNT_PURGE_SCOPE_FORBIDDEN'),
    ([], 'ACCOUNT_PURGE_SCOPE_FORBIDDEN'),
])
def test_org_admin_cannot_purge_foreign_inactive_or_detached_account(monkeypatch, memberships, detail):
    connection = Connection(memberships=memberships)
    request, _, _ = prepare(monkeypatch, connection)
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_account(12, payload(), request)
    assert (failure.value.status_code, failure.value.detail) == (403, detail)
    assert not connection.committed


@pytest.mark.parametrize('source', ['superadmin', 'organization_admin'])
def test_configured_account_is_protected_from_direct_purge(monkeypatch, source):
    connection = Connection(memberships=[membership()])
    request, _, _ = prepare(monkeypatch, connection, superadmin=True)
    monkeypatch.setattr(routes, 'configured_superadmin_emails',
        lambda: {'person@example.test'} if source == 'superadmin' else set())
    monkeypatch.setattr(routes, 'configured_org_admin_emails',
        lambda: {'elsewhere': ['person@example.test']} if source == 'organization_admin' else {})
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_account(12, payload(), request)
    assert failure.value.detail == 'CANNOT_PURGE_CONFIGURED_ACCOUNT'
    assert not connection.committed
    assert not any('suppressions' in query for query, _ in connection.statements)


@pytest.mark.parametrize('source', ['superadmin', 'organization_admin'])
def test_verified_configured_alias_protects_direct_account_with_different_primary(monkeypatch, source):
    connection = Connection(memberships=[membership()], verified_aliases=['configured@example.test'])
    request, _, _ = prepare(monkeypatch, connection, superadmin=True)
    monkeypatch.setattr(routes, 'configured_superadmin_emails',
        lambda: {'configured@example.test'} if source == 'superadmin' else set())
    monkeypatch.setattr(routes, 'configured_org_admin_emails',
        lambda: {'elsewhere': ['configured@example.test']} if source == 'organization_admin' else {})
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_account(12, payload(), request)
    assert failure.value.detail == 'CANNOT_PURGE_CONFIGURED_ACCOUNT'
    assert not connection.committed


def test_self_and_last_organization_admin_are_protected(monkeypatch):
    connection = Connection(memberships=[membership(role='admin')], last_admin=True)
    _, scope, actor = prepare(monkeypatch, connection, superadmin=True)
    for account, detail in [(dict(id=99, email='self@example.test'), 'CANNOT_PURGE_CURRENT_ACCOUNT'),
                            (connection.account, 'CANNOT_PURGE_LAST_ORGANIZATION_ADMIN')]:
        with pytest.raises(HTTPException) as failure:
            routes._require_account_purge_target(connection, scope=scope, actor=actor, account=account)
        assert failure.value.detail == detail


def test_org_admin_plan_is_checked_before_receipt_and_deletion(monkeypatch):
    connection = Connection(memberships=[membership()])
    request, _, _ = prepare(monkeypatch, connection)
    def forbidden(*_args, **_kwargs):
        raise ValueError('ACCOUNT_PURGE_SCOPE_FORBIDDEN')
    monkeypatch.setattr(routes, 'require_account_plan_organization_scope', forbidden)
    def purge(_connection, *, validate_scope, **_kwargs):
        validate_scope({}, [])
        pytest.fail('destructive execution must not be reached')
    monkeypatch.setattr(routes, 'purge_account', purge)
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_account(12, payload(), request)
    assert failure.value.status_code == 403
    assert connection.rolled_back and not connection.committed


def test_org_admin_purge_of_participating_admin_commits_and_cache_failure_keeps_success(monkeypatch):
    connection = Connection(memberships=[membership(role='admin')])
    request, _, _ = prepare(monkeypatch, connection)
    records = []
    monkeypatch.setattr(routes, 'record_receipt', lambda _connection, record: records.append(record))
    def purge(_connection, *, validate_scope, **_kwargs):
        validate_scope({}, [])
        return {'public.users': 1, 'public.organization_memberships': 1}
    monkeypatch.setattr(routes, 'purge_account', purge)
    def cache_failure(_user_id):
        raise RuntimeError('synthetic cache failure')
    monkeypatch.setattr(routes.interviewer_agent, 'invalidate_user', cache_failure)
    result = routes.purge_admin_account(12, payload(), request)
    assert result['ok'] is True
    assert connection.committed and not connection.rolled_back
    assert records[0]['actor_user_id'] == 99


@pytest.mark.parametrize(('saved_actor', 'actor', 'legacy', 'accepted'), [
    (99, 99, False, True), (99, 98, True, False),
    (None, 99, False, False), (None, 99, True, True),
])
def test_receipt_replay_binds_actor_and_limits_legacy_receipts(saved_actor, actor, legacy, accepted):
    row = {'operation_id': 'delete-person-1', 'target_type': 'account', 'target_id': 12,
        'preview_fingerprint': 'a' * 64, 'applied_at': None, 'actor_user_id': saved_actor}
    connection = SimpleNamespace(execute=lambda *_args: SimpleNamespace(fetchone=lambda: row))
    arguments = dict(operation_id=row['operation_id'], target_type='account', target_id=12,
        fingerprint='a' * 64, actor_user_id=actor, allow_legacy_actor=legacy)
    if accepted:
        assert read_receipt(connection, **arguments)['operation_id'] == row['operation_id']
    else:
        with pytest.raises(ValueError, match='DELETION_RECEIPT_ACTOR_MISMATCH'):
            read_receipt(connection, **arguments)


def test_replayed_receipt_does_not_look_up_deleted_target(monkeypatch):
    connection = Connection()
    request, _, _ = prepare(monkeypatch, connection)
    captured = {}
    def receipt(_connection, **kwargs):
        captured.update(kwargs)
        return {'operation_id': kwargs['operation_id']}
    monkeypatch.setattr(routes, 'read_receipt', receipt)
    result = routes.purge_admin_account(12, payload(), request)
    assert result['ok'] and result['idempotent']
    assert captured['actor_user_id'] == 99 and captured['allow_legacy_actor'] is False
    assert not any('FROM users' in query for query, _ in connection.statements)


def test_removed_member_exclusion_endpoint_is_explicit_and_does_not_write(monkeypatch):
    connection = Connection()
    request, scope, _ = prepare(monkeypatch, connection)
    monkeypatch.setattr(routes, '_require_organization_admin', lambda *_args, **_kwargs: scope)
    with pytest.raises(HTTPException) as failure:
        routes.delete_admin_organization_member(3, 'person@example.test', request)
    assert failure.value.status_code == 410
    assert not connection.statements and not connection.committed


def test_actor_authority_is_rechecked_after_waiting_for_purge_lock(monkeypatch):
    connection = Connection(memberships=[membership()])
    request, scope, _ = prepare(monkeypatch, connection)
    calls = []
    def changed_scope(_connection, _actor, *, commit_scope=True):
        calls.append(commit_scope)
        if commit_scope:
            return scope
        assert any('pg_advisory_xact_lock' in query for query, _ in connection.statements)
        raise HTTPException(403, detail='Admin access required')
    monkeypatch.setattr(routes, '_get_admin_scope_or_403', changed_scope)
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_account(12, payload(), request)
    assert failure.value.status_code == 403 and calls == [True, False]
    assert not any('FROM users' in query for query, _ in connection.statements)


def test_account_preview_maps_changed_physical_rows_to_explicit_stale_refusal(monkeypatch):
    connection = Connection(memberships=[membership()])
    request, _, _ = prepare(monkeypatch, connection)
    def stale(*_args):
        raise ValueError('PURGE_PREVIEW_STALE')
    monkeypatch.setattr(routes, 'build_account_purge_plan', stale)
    with pytest.raises(HTTPException) as failure:
        routes.preview_admin_user_purge(12, request)
    assert (failure.value.status_code, failure.value.detail) == (409, 'PURGE_PREVIEW_STALE')

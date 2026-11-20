"""Immutable command receipts; current assignment state is a separate projection."""
from __future__ import annotations

import hashlib
import json


def command_request(*, assignment_ref, user_ids, role_profile_version_id=None,
                    assessment_configuration_id=None) -> dict:
    return {'assignment_ref': str(assignment_ref).strip(),
            'user_ids': sorted(set(int(value) for value in user_ids)),
            'role_profile_version_id': role_profile_version_id,
            'assessment_configuration_id': assessment_configuration_id}


def fingerprint(request: dict, *, legacy=False) -> str:
    value = {key: val for key, val in request.items()
             if not legacy or key != 'assessment_configuration_id'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ensure_schema(connection) -> None:
    connection.execute('''CREATE TABLE IF NOT EXISTS organization_assessment_assignment_operation_results (
        organization_id BIGINT NOT NULL,
        actor_user_id BIGINT NOT NULL,
        operation_id TEXT NOT NULL,
        request_json JSONB NOT NULL,
        request_fingerprint TEXT NOT NULL,
        result_json JSONB NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY(organization_id,actor_user_id,operation_id),
        FOREIGN KEY(organization_id,actor_user_id,operation_id)
          REFERENCES organization_assessment_assignment_operations(organization_id,actor_user_id,operation_id)
          ON DELETE RESTRICT
    )''')
    connection.execute('DROP TRIGGER IF EXISTS assignment_operation_result_immutable ON organization_assessment_assignment_operation_results')
    connection.execute('''CREATE TRIGGER assignment_operation_result_immutable
        BEFORE UPDATE OR DELETE ON organization_assessment_assignment_operation_results
        FOR EACH ROW EXECUTE FUNCTION prevent_assignment_source_binding_change()''')


def claim(connection, *, organization_id, actor_user_id, operation_id, request) -> bool:
    """Unique INSERT waits for a concurrent transaction; its effects commit together."""
    scope = (organization_id, actor_user_id, operation_id)
    # Keep the existing header hash readable by the previous application. The
    # immutable result stores the full request/hash, including the config selector.
    created = connection.execute('''INSERT INTO organization_assessment_assignment_operations
        (organization_id,actor_user_id,operation_id,request_fingerprint) VALUES(%s,%s,%s,%s)
        ON CONFLICT(organization_id,actor_user_id,operation_id) DO NOTHING RETURNING operation_id''',
        (*scope, fingerprint(request, legacy=True))).fetchone()
    check_scope(connection, scope=scope, request=request)
    return created is not None


def check_scope(connection, *, scope, request) -> dict | None:
    receipt = connection.execute('''SELECT request_fingerprint FROM organization_assessment_assignment_operations
        WHERE organization_id=%s AND actor_user_id=%s AND operation_id=%s''', scope).fetchone()
    if receipt is not None and str(receipt['request_fingerprint']) not in {
            fingerprint(request), fingerprint(request, legacy=True)}:
        raise ValueError('ASSIGNMENT_OPERATION_SCOPE_MISMATCH')
    return dict(receipt) if receipt else None


def read(connection, *, organization_id, actor_user_id, operation_id, request) -> dict | None:
    scope = (organization_id, actor_user_id, operation_id)
    receipt = check_scope(connection, scope=scope, request=request)
    if receipt is None:
        return None
    available = connection.execute("SELECT to_regclass(current_schema()||'.organization_assessment_assignment_operation_results') AS relation").fetchone()
    if available and available.get('relation'):
        saved = connection.execute('''SELECT request_json,result_json,request_fingerprint
            FROM organization_assessment_assignment_operation_results
            WHERE organization_id=%s AND actor_user_id=%s AND operation_id=%s''', scope).fetchone()
        if saved:
            if saved['request_json'] != request or saved['request_fingerprint'] != fingerprint(request):
                raise ValueError('ASSIGNMENT_OPERATION_SCOPE_MISMATCH')
            return dict(saved['result_json'])
    # Old receipts proved only the intent. Only assignments CREATED by this exact
    # operation prove a per-recipient success. Never infer failures or existing
    # assignments from today's memberships/active generation.
    rows = connection.execute('''SELECT recipient_user_id,id FROM organization_assessment_assignments
        WHERE organization_id=%s AND created_by_user_id=%s AND operation_id=%s
          AND request_fingerprint=ANY(%s) AND assignment_ref=%s AND recipient_user_id=ANY(%s)''',
        (*scope, [fingerprint(request), fingerprint(request, legacy=True)],
         request['assignment_ref'], request['user_ids'])).fetchall()
    proven = {int(row['recipient_user_id']): int(row['id']) for row in rows}
    # Legacy fingerprints never included an explicit configuration selector.
    if request.get('assessment_configuration_id') is not None:
        proven = {}
    return {'items': [dict(user_id=user_id, status='assigned', assignment_id=proven[user_id], error=None)
        if user_id in proven else dict(user_id=user_id, status='uncertain', assignment_id=None,
            reason_code='ASSIGNMENT_OPERATION_RESULT_UNKNOWN', error='Сохранённый исход операции не установлен.')
        for user_id in request['user_ids']]}


def save(connection, *, organization_id, actor_user_id, operation_id, request, result) -> None:
    connection.execute('''INSERT INTO organization_assessment_assignment_operation_results
        (organization_id,actor_user_id,operation_id,request_json,result_json,request_fingerprint)
        VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s)''',
        (organization_id, actor_user_id, operation_id, json.dumps(request),
         json.dumps(result, ensure_ascii=False), fingerprint(request)))

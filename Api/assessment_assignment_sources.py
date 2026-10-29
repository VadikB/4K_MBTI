"""Explicit tenant-authorized source refs; no global/default configuration selection."""
from __future__ import annotations

from Api.assessment_role_profiles import load_published_role_profile


def ensure_schema(connection) -> None:
    connection.execute('''CREATE TABLE IF NOT EXISTS organization_assessment_assignment_operations (
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        actor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        operation_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY(organization_id,actor_user_id,operation_id)
    )''')
    connection.execute("""CREATE TABLE IF NOT EXISTS organization_assessment_source_bindings (
        id BIGSERIAL PRIMARY KEY,
        assignment_id BIGINT NOT NULL REFERENCES organization_assessment_assignments(id) ON DELETE RESTRICT,
        questionnaire_revision_id BIGINT NOT NULL REFERENCES questionnaire_response_revisions(id) ON DELETE RESTRICT,
        assessment_configuration_id BIGINT NOT NULL REFERENCES assessment_configurations(id) ON DELETE RESTRICT,
        role_profile_version_id BIGINT NOT NULL REFERENCES assessment_role_profile_versions(id) ON DELETE RESTRICT,
        assigned_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        operation_id TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(assignment_id,operation_id)
    )""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_assignment_source_binding_change()
        RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'Assessment source binding revisions are immutable';
        END $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS assignment_source_binding_immutable ON organization_assessment_source_bindings")
    connection.execute("""CREATE TRIGGER assignment_source_binding_immutable
        BEFORE UPDATE OR DELETE ON organization_assessment_source_bindings
        FOR EACH ROW EXECUTE FUNCTION prevent_assignment_source_binding_change()""")
    connection.execute('DROP TRIGGER IF EXISTS assignment_operation_immutable ON organization_assessment_assignment_operations')
    connection.execute('''CREATE TRIGGER assignment_operation_immutable
        BEFORE UPDATE OR DELETE ON organization_assessment_assignment_operations
        FOR EACH ROW EXECUTE FUNCTION prevent_assignment_source_binding_change()''')


def record_operation(connection, *, organization_id: int, actor_user_id: int,
                     operation_id: str, fingerprint: str) -> None:
    """INSERT serializes concurrent same-key commands; rollback includes the batch."""
    connection.execute('''INSERT INTO organization_assessment_assignment_operations
        (organization_id,actor_user_id,operation_id,request_fingerprint) VALUES(%s,%s,%s,%s)
        ON CONFLICT(organization_id,actor_user_id,operation_id) DO NOTHING''',
        (organization_id, actor_user_id, operation_id, fingerprint))
    previous = connection.execute('''SELECT request_fingerprint FROM organization_assessment_assignment_operations
        WHERE organization_id=%s AND actor_user_id=%s AND operation_id=%s''',
        (organization_id, actor_user_id, operation_id)).fetchone()
    if previous['request_fingerprint'] != fingerprint:
        raise ValueError('ASSIGNMENT_OPERATION_IDEMPOTENCY_CONFLICT')


def schema_available(connection) -> bool:
    row = connection.execute("SELECT to_regclass(current_schema()||'.organization_assessment_source_bindings') AS relation").fetchone()
    return bool(row and row.get('relation'))


def has_managed_assignment(connection, *, user_id: int) -> bool:
    if not schema_available(connection):
        return False
    return bool(connection.execute('''SELECT 1 FROM questionnaire_response_revisions q
        WHERE q.status='confirmed' AND EXISTS (
          SELECT 1 FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
          WHERE m.user_id=%s AND m.organization_id=q.organization_id AND o.is_active=TRUE)
        AND (EXISTS (SELECT 1 FROM organization_assessment_assignments a
                     WHERE a.recipient_user_id=%s AND a.organization_id=q.organization_id
                       AND a.assignment_ref=q.assignment_ref AND a.status='active' AND a.revoked_at IS NULL)
          OR EXISTS (SELECT 1 FROM organization_invitations i JOIN users u ON LOWER(u.email)=LOWER(i.recipient_email)
                     WHERE u.id=%s AND i.organization_id=q.organization_id AND i.assignment_ref=q.assignment_ref
                       AND i.purpose='personal_registration' AND i.revoked_at IS NULL
                       AND i.created_by_user_id IS DISTINCT FROM u.id)) LIMIT 1''',
        (user_id, user_id, user_id)).fetchone())


def options(connection, *, organization_id: int) -> dict:
    configurations = connection.execute("""SELECT c.id,c.name,c.catalog_version_id
        FROM assessment_configurations c
        JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        JOIN m5_catalogs catalog ON catalog.id=c.catalog_version_id
        WHERE c.status='published' AND m.status='published'
          AND m.definition_json->>'methodology_version'='1.1'
          AND catalog.status='published' AND catalog.usage_scope='assessment'
          AND (catalog.organization_id IS NULL OR catalog.organization_id=%s)
        ORDER BY c.id""", (organization_id,)).fetchall()
    rows = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
        JOIN assessment_role_profiles r ON r.id=v.role_profile_id
        LEFT JOIN assessment_role_profile_versions base_v ON base_v.id=v.base_role_version_id
        LEFT JOIN assessment_role_profiles base_r ON base_r.id=base_v.role_profile_id
        WHERE v.status='published' AND v.methodology_version='1.1'
          AND (r.scope='base' OR (r.scope='organization' AND r.organization_id=%s))
          AND COALESCE(base_r.code,r.code)<>'student' ORDER BY r.code,v.version DESC""", (organization_id,)).fetchall()
    roles = [load_published_role_profile(connection, int(row['id'])) for row in rows]
    return {'configurations': [dict(row) for row in configurations],
            'roles': [{'version_id': row['id'], 'name': row['definition']['description']['name'],
                       'version': row['version']} for row in roles]}


def current_binding(connection, *, user_id: int, organization_id: int,
                    assignment_ref: str, questionnaire_revision_id: int | None) -> dict | None:
    if questionnaire_revision_id is None or not schema_available(connection):
        return None
    row = connection.execute("""SELECT b.* FROM organization_assessment_source_bindings b
        JOIN organization_assessment_assignments a ON a.id=b.assignment_id
        WHERE a.recipient_user_id=%s AND a.organization_id=%s AND a.assignment_ref=%s
          AND a.status='active' AND a.revoked_at IS NULL AND b.questionnaire_revision_id=%s
        ORDER BY b.id DESC LIMIT 1""",
        (user_id, organization_id, assignment_ref, questionnaire_revision_id)).fetchone()
    return dict(row) if row else None


def bind(connection, *, assignment_id: int, organization_id: int, configuration_id: int,
         role_version_id: int, questionnaire_revision_id: int, actor_user_id: int,
         operation_id: str) -> dict:
    """Caller enforces tenant-admin permission; lock serializes changes and M4 binding."""
    assignment = connection.execute("""SELECT * FROM organization_assessment_assignments
        WHERE id=%s AND organization_id=%s AND status='active' AND revoked_at IS NULL
        FOR UPDATE""", (assignment_id, organization_id)).fetchone()
    if not assignment:
        raise ValueError('ASSIGNMENT_NOT_AVAILABLE')
    prior = connection.execute("""SELECT * FROM organization_assessment_source_bindings
        WHERE assignment_id=%s AND operation_id=%s""", (assignment_id, operation_id)).fetchone()
    if prior:
        if (prior['assessment_configuration_id'], prior['role_profile_version_id'], prior['questionnaire_revision_id']) != (
                configuration_id, role_version_id, questionnaire_revision_id):
            raise ValueError('ASSIGNMENT_SOURCE_IDEMPOTENCY_CONFLICT')
        return dict(prior)
    latest = current_binding(connection, user_id=assignment['recipient_user_id'],
        organization_id=organization_id, assignment_ref=assignment['assignment_ref'],
        questionnaire_revision_id=questionnaire_revision_id)
    if latest and (latest['assessment_configuration_id'], latest['role_profile_version_id']) == (configuration_id, role_version_id):
        return latest
    if connection.execute("""SELECT 1 FROM participant_acquaintance_confirmations
        WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s
          AND personalized_profile_id IS NOT NULL LIMIT 1""",
        (assignment['recipient_user_id'], organization_id, assignment['assignment_ref'])).fetchone():
        raise ValueError('ASSIGNMENT_SOURCES_FROZEN: Создайте новое назначение; подтверждённый профиль неизменяем.')
    available = options(connection, organization_id=organization_id)
    if configuration_id not in {row['id'] for row in available['configurations']}:
        raise ValueError('ASSIGNMENT_CONFIGURATION_NOT_AVAILABLE')
    if role_version_id not in {row['version_id'] for row in available['roles']}:
        raise ValueError('ASSIGNMENT_ROLE_NOT_AVAILABLE')
    revision = connection.execute("""SELECT id FROM questionnaire_response_revisions
        WHERE id=%s AND organization_id=%s AND assignment_ref=%s AND status='confirmed'""",
        (questionnaire_revision_id, organization_id, assignment['assignment_ref'])).fetchone()
    if not revision:
        raise ValueError('ASSIGNMENT_QUESTIONNAIRE_SCOPE_MISMATCH')
    return dict(connection.execute("""INSERT INTO organization_assessment_source_bindings
        (assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,
         assigned_by_user_id,operation_id) VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",
        (assignment_id, questionnaire_revision_id, configuration_id, role_version_id, actor_user_id, operation_id)).fetchone())


def profile_has_binding(connection, profile: dict) -> bool:
    if not schema_available(connection):
        return False
    return bool(connection.execute("""SELECT 1 FROM participant_acquaintance_confirmations c
        JOIN organization_assessment_assignments a ON a.recipient_user_id=c.user_id
          AND a.organization_id=c.organization_id AND a.assignment_ref=c.assignment_ref
        JOIN organization_assessment_source_bindings b ON b.assignment_id=a.id
          AND b.questionnaire_revision_id=c.questionnaire_revision_id
        WHERE c.personalized_profile_id=%s AND c.user_id=%s AND c.organization_id=%s
          AND b.assessment_configuration_id=%s AND b.role_profile_version_id=%s LIMIT 1""",
        (profile['id'], profile['user_id'], profile['organization_id'],
         profile['assessment_configuration_id'], profile['role_profile_version_id'])).fetchone())

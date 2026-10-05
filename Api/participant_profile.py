"""Participant confirmation adapter for existing, versioned M4 sources."""
from Api import assessment_contexts as contexts
from Api.assessment_role_profiles import list_available_role_profiles, get_selected_role_profile


def options(connection, *, user_id):
    organization_id = contexts.load_single_active_organization_id(connection, user_id=user_id)
    organizations = connection.execute("""SELECT v.id AS version_id,v.version,c.code,v.definition_json
        FROM assessment_organization_context_versions v
        JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
        WHERE c.organization_id=%s AND v.status='published'
        ORDER BY c.code,v.version DESC""", (organization_id,)).fetchall()
    configurations = connection.execute("""SELECT c.id,c.code,c.name FROM assessment_configurations c
        JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        WHERE c.status='published' AND m.status='published'
          AND m.definition_json->>'methodology_version'='1.1' ORDER BY c.id""").fetchall()
    roles = list_available_role_profiles(connection, user_id=user_id)
    selected = get_selected_role_profile(connection, user_id=user_id)
    current = connection.execute('SELECT id,status FROM assessment_personalized_profiles WHERE user_id=%s ORDER BY frozen_at DESC,id DESC LIMIT 1', (user_id,)).fetchone()
    return {
        'current_profile': dict(current) if current else None,
        'organization_contexts': [{'version_id': row['version_id'], 'version': row['version'], 'name': row['definition_json']['name']} for row in organizations],
        'configurations': [dict(row) for row in configurations],
        'roles': [{'version_id': r['id'], 'name': r['definition'].get('description', {}).get('name', r['code']),
                   'version': r['version']} for r in roles],
        'selected_role_version_id': selected['id'] if selected else None,
    }


def confirm(connection, *, user_id, selection, full_name, position, duties):
    # Serialize confirmations; an existing Cycle keeps its original M4 snapshot.
    connection.execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (user_id,))
    available = options(connection, user_id=user_id)
    if selection.role_profile_version_id not in {r['version_id'] for r in available['roles']}:
        raise ValueError('Выбранная опубликованная роль недоступна.')
    if selection.organization_context_version_id not in {r['version_id'] for r in available['organization_contexts']}:
        raise ValueError('Нужен подтверждённый контекст вашей организации.')
    if selection.assessment_configuration_id not in {r['id'] for r in available['configurations']}:
        raise ValueError('Нужна опубликованная конфигурация оценки M4/M5.')
    previous = connection.execute("""SELECT * FROM assessment_personalized_profiles
        WHERE user_id=%s ORDER BY frozen_at DESC,id DESC LIMIT 1""", (user_id,)).fetchone()
    conflicts = previous['conflicts_json'] if previous else []
    if any(c.get('type') in contexts.BLOCKING_CONFLICTS and not c.get('resolved') for c in conflicts):
        raise ValueError('Сначала требуется разрешить существенные противоречия профиля с ответственным специалистом.')
    professional = {'position_or_status': position, 'regular_tasks': duties}
    # Reconfirmation with unchanged inputs reuses the immutable snapshot.
    if previous and previous['status'] == 'ready' and all(previous[k] == getattr(selection, k) for k in
            ('role_profile_version_id', 'organization_context_version_id', 'assessment_configuration_id')):
        source = connection.execute('SELECT checksum FROM assessment_user_context_versions WHERE id=%s', (previous['user_context_version_id'],)).fetchone()
        expected = contexts.context_checksum({'identity': {'full_name': full_name}, 'professional': professional})
        if previous['content_json'].get('user_context') == professional and source and source['checksum'] == expected:
            if available['selected_role_version_id'] != selection.role_profile_version_id:
                contexts.assign_role_profile(connection, user_id=user_id, role_profile_version_id=selection.role_profile_version_id,
                                             determined_by='user', determined_by_user_id=user_id)
            return {'id': previous['id'], 'status': previous['status']}
    contexts.assign_role_profile(connection, user_id=user_id, role_profile_version_id=selection.role_profile_version_id,
                                 determined_by='user', determined_by_user_id=user_id)
    version = contexts.create_user_context_draft(connection, user_id=user_id,
        identity={'full_name': full_name}, professional=professional)
    contexts.confirm_user_context(connection, version_id=version, user_id=user_id)
    return contexts.create_personalized_profile(connection, user_id=user_id,
        assessment_configuration_id=selection.assessment_configuration_id,
        organization_context_version_id=selection.organization_context_version_id,
        role_profile_version_id=selection.role_profile_version_id, user_context_version_id=version,
        conflicts=conflicts)

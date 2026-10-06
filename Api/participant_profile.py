"""Participant confirmation and current-scope selection of canonical M4 snapshots."""
from Api import assessment_contexts as contexts
from Api.assessment_role_profiles import list_available_role_profiles, get_selected_role_profile


def active_organization(connection, user_id):
    try:
        return contexts.load_single_active_organization_id(connection, user_id=user_id)
    except ValueError as exc:
        raise ValueError('M4_ORGANIZATION_REQUIRED: Ответственный специалист должен определить одну активную организацию участника.') from exc


def profile_for_start(connection, *, user_id, profile_id=None):
    organization_id = active_organization(connection, user_id)
    role = get_selected_role_profile(connection, user_id=user_id)
    if role is None:
        raise ValueError('M4_PROFILE_NOT_READY: Подтвердите роль и контекст оценки в профиле.')
    rows = connection.execute('''SELECT DISTINCT ON (assessment_configuration_id) *
        FROM assessment_personalized_profiles WHERE user_id=%s AND organization_id=%s
        ORDER BY assessment_configuration_id,frozen_at DESC,id DESC''', (user_id, organization_id)).fetchall()
    if profile_id is not None:
        selected = next((r for r in rows if r['id'] == profile_id), None)
        if selected is None:
            raise ValueError('M4_PROFILE_SCOPE_MISMATCH: Подтвердите актуальный профиль для выбранной организации и конфигурации.')
    elif len(rows) == 1:
        selected = rows[0]
    elif len(rows) > 1:
        raise ValueError('M4_PROFILE_SELECTION_REQUIRED: Выберите конфигурацию оценки и подтвердите профиль.')
    else:
        raise ValueError('M4_PROFILE_NOT_READY: Завершите подтверждение контекста оценки.')
    if selected['role_profile_version_id'] != role['id']:
        raise ValueError('M4_PROFILE_NOT_READY: Подтвердите контекст для выбранной роли.')
    if selected['status'] != 'ready':
        raise ValueError('M4_PROFILE_NOT_READY: Ответственный специалист должен разрешить противоречия контекста.')
    validate_snapshot(connection, selected)
    return dict(selected)


def validate_snapshot(connection, row):
    try:
        snapshot = contexts.build_from_confirmed_sources(connection, user_id=row['user_id'],
            assessment_configuration_id=row['assessment_configuration_id'],
            organization_context_version_id=row['organization_context_version_id'],
            role_profile_version_id=row['role_profile_version_id'], user_context_version_id=row['user_context_version_id'],
            conflicts=row['conflicts_json'])
    except ValueError as exc:
        raise ValueError('M4_SOURCE_UNAVAILABLE: Ответственный специалист должен проверить опубликованные источники и подтверждённый контекст профиля.') from exc
    if any(snapshot[k] != row[column] for k, column in
           [('checksum', 'checksum'), ('content', 'content_json'), ('provenance', 'provenance_json'), ('status', 'status')]):
        raise ValueError('M4_CHECKSUM_MISMATCH: Ответственный специалист должен проверить источники профиля.')
    return snapshot


def readiness(connection, *, user_id, profile_id=None):
    try:
        row = profile_for_start(connection, user_id=user_id, profile_id=profile_id)
        return {'status': 'ready', 'id': row['id'], 'assessment_configuration_id': row['assessment_configuration_id'],
                'organization_id': row['organization_id'], 'message': ''}
    except ValueError as exc:
        return {'status': 'not_ready', 'id': None, 'message': str(exc)}


def options(connection, *, user_id):
    organization_id = active_organization(connection, user_id)
    organizations = connection.execute('''SELECT v.id AS version_id,v.version,c.code,v.definition_json
        FROM assessment_organization_context_versions v
        JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
        WHERE c.organization_id=%s AND v.status='published'
        ORDER BY c.code,v.version DESC''', (organization_id,)).fetchall()
    configurations = connection.execute('''SELECT c.id,c.code,c.name FROM assessment_configurations c
        JOIN assessment_methodology_versions m ON m.id=c.methodology_version_id
        WHERE c.status='published' AND m.status='published'
          AND m.definition_json->>'methodology_version'='1.1' ORDER BY c.id''').fetchall()
    roles = list_available_role_profiles(connection, user_id=user_id)
    selected = get_selected_role_profile(connection, user_id=user_id)
    current = readiness(connection, user_id=user_id)
    user_context = connection.execute('''SELECT v.professional_context_json FROM assessment_user_context_versions v
        JOIN assessment_user_contexts u ON u.id=v.user_context_id
        WHERE u.user_id=%s AND u.organization_id=%s AND v.status='confirmed'
        ORDER BY v.version DESC,v.id DESC LIMIT 1''', (user_id, organization_id)).fetchone()
    return {
        'organization_id': organization_id,
        'current_profile': current if current['id'] else None,
        'readiness': current,
        'user_context': user_context['professional_context_json'] if user_context else None,
        'organization_contexts': [{'version_id': row['version_id'], 'version': row['version'], 'name': row['definition_json']['name']} for row in organizations],
        'configurations': [dict(row) for row in configurations],
        'roles': [{'version_id': r['id'], 'name': r['definition'].get('description', {}).get('name', r['code']),
                   'version': r['version']} for r in roles],
        'selected_role_version_id': selected['id'] if selected else None,
    }


def confirm(connection, *, user_id, selection, full_name, position, duties):
    connection.execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (user_id,))
    organization_id = active_organization(connection, user_id)
    available = options(connection, user_id=user_id)
    if selection.role_profile_version_id not in {r['version_id'] for r in available['roles']}:
        raise ValueError('Выбранная опубликованная роль недоступна.')
    if selection.organization_context_version_id not in {r['version_id'] for r in available['organization_contexts']}:
        raise ValueError('Нужен подтверждённый контекст вашей организации.')
    if selection.assessment_configuration_id not in {r['id'] for r in available['configurations']}:
        raise ValueError('Нужна опубликованная конфигурация оценки M4/M5.')
    previous = connection.execute('''SELECT * FROM assessment_personalized_profiles
        WHERE user_id=%s AND organization_id=%s AND assessment_configuration_id=%s
        ORDER BY frozen_at DESC,id DESC LIMIT 1''', (user_id, organization_id, selection.assessment_configuration_id)).fetchone()
    conflicts = previous['conflicts_json'] if previous else []
    if any(c.get('type') in contexts.BLOCKING_CONFLICTS and not c.get('resolved') for c in conflicts):
        raise ValueError('Сначала требуется разрешить существенные противоречия профиля с ответственным специалистом.')
    professional = {'position_or_status': position, 'regular_tasks': duties}
    if previous and previous['status'] == 'ready' and all(previous[k] == getattr(selection, k) for k in
            ('role_profile_version_id', 'organization_context_version_id', 'assessment_configuration_id')):
        source = connection.execute('SELECT checksum FROM assessment_user_context_versions WHERE id=%s', (previous['user_context_version_id'],)).fetchone()
        expected = contexts.context_checksum({'identity': {'full_name': full_name}, 'professional': professional})
        if previous['content_json'].get('user_context') == professional and source and source['checksum'] == expected:
            snapshot = validate_snapshot(connection, previous)
            if available['selected_role_version_id'] != selection.role_profile_version_id:
                contexts.assign_role_profile(connection, user_id=user_id, role_profile_version_id=selection.role_profile_version_id,
                                             determined_by='user', determined_by_user_id=user_id)
            return {'id': previous['id'], **snapshot}
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

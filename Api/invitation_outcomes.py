"""Safe invitation facts. Legacy delivery_error remains readable; no raw text leaves this boundary."""
from __future__ import annotations

import json
import hashlib

REASONS = {
    'not_attempted': ('operation', 'none'),
    'invalid_email': ('recipient', 'review_member'),
    'questionnaire_unconfirmed': ('readiness', 'review_organization'),
    'questionnaire_incomplete': ('readiness', 'review_organization'),
    'organization_unsupported': ('readiness', 'none'),
    'access_changed': ('access', 'review_member'),
    'permission_changed': ('access', 'refresh_context'),
    'organization_changed': ('readiness', 'review_organization'),
    'member_unavailable': ('access', 'review_member'),
    'permission_denied': ('access', 'refresh_context'),
    'mail_not_configured': ('configuration', 'operator'),
    'provider_rejected': ('transport', 'retry'),
    'provider_recipient': ('transport', 'review_member'),
    'provider_sender': ('transport', 'operator'),
    'provider_access': ('transport', 'operator'),
    'provider_limit': ('transport', 'retry_later'),
    'provider_temporary': ('transport', 'retry_later'),
    'context_changed': ('finalization', 'check'),
    'operation_mismatch': ('operation', 'refresh_context'),
    'link_used': ('operation', 'refresh_context'),
    'link_revoked': ('operation', 'refresh_context'),
    'link_expired': ('operation', 'retry'),
    'failed_unclassified': ('unknown', 'retry'),
    'delivery_unknown': ('transport', 'check'),
    'sending': ('transport', 'check'),
    'queued': ('operation', 'check'),
    'accepted': ('complete', 'none'),
}


MESSAGES = {
    'invalid_email': 'Некорректный email участника.',
    'questionnaire_unconfirmed': 'Чтобы пригласить участников, заполните и подтвердите сведения для знакомства.',
    'questionnaire_incomplete': 'Приглашение не отправлено: в сведениях организации не заполнен обязательный минимум.',
    'organization_changed': 'Сведения организации изменились. Проверьте и подтвердите их.',
    'member_unavailable': 'Участник недоступен для приглашения в этой организации.',
    'permission_denied': 'Недостаточно прав для приглашения в эту организацию.',
    'mail_not_configured': 'Почтовый сервис не настроен для отправки приглашений.',
    'provider_rejected': 'Почтовый сервис отклонил запрос.',
    'failed_unclassified': 'Приглашение не отправлено. Причину отказа пока не удалось уточнить.',
    'operation_mismatch': 'Данные попытки не совпадают с текущим действием.',
    'delivery_unknown': 'Не удалось подтвердить отправку. Проверьте эту попытку.',
}


def message(code):
    return MESSAGES.get(code, code if code in REASONS else MESSAGES['failed_unclassified'])


class InvitationRefusal(ValueError):
    def __init__(self, reason_code: str, reason_params=None):
        self.reason_code = reason_code
        self.reason_params = reason_params or {}
        super().__init__(reason_code)


def facts(delivery: str, stored=None, *, reason_code=None) -> dict:
    """Outcome certainty comes from state, never from the precision of an error string."""
    saved = {}
    if isinstance(stored, str):
        try:
            candidate = json.loads(stored)
            if isinstance(candidate, dict) and candidate.get('contract') == 'invitation_reason/1':
                saved = candidate
        except (ValueError, TypeError):
            pass
    outcome = {'accepted': 'accepted', 'error': 'failed', 'queued': 'pending', 'not_sent': 'not_attempted'}.get(delivery, 'unknown')
    default = {'accepted': 'accepted', 'error': 'failed_unclassified', 'queued': 'queued', 'sending': 'sending', 'not_sent': 'not_attempted'}.get(delivery, 'delivery_unknown')
    code = reason_code or saved.get('reason_code') or default
    if code not in REASONS:
        code = default
    if delivery == 'accepted':
        code = 'accepted'
    elif outcome == 'unknown' and code not in {'delivery_unknown', 'sending', 'context_changed'}:
        code = default
    elif outcome == 'pending':
        code = 'queued'
    elif outcome == 'failed' and code in {'accepted', 'queued', 'sending', 'delivery_unknown', 'context_changed'}:
        code = 'failed_unclassified'
    stage, action = REASONS[code]
    params = {}
    retry = saved.get('reason_params', {}).get('retry_after_seconds') if isinstance(saved.get('reason_params'), dict) else None
    missing = saved.get('reason_params', {}).get('missing_fields') if isinstance(saved.get('reason_params'), dict) else None
    if code == 'questionnaire_incomplete' and isinstance(missing, list):
        params['missing_fields'] = [field for field in ('purpose', 'results_usage') if field in missing]
    if code == 'provider_limit' and type(retry) is int and 0 <= retry <= 86400:
        params['retry_after_seconds'] = retry
    return dict(outcome=outcome, reason_code=code, reason_params=params, next_action=action, failure_stage=stage)


def encode_reason(delivery, code, params=None, recipients=None):
    value = facts(delivery, json.dumps({'contract': 'invitation_reason/1', 'reason_code': code, 'reason_params': params or {}}))
    return json.dumps({'contract': 'invitation_reason/1', **value, **({'recipient_fingerprint': recipient_fingerprint(recipients)} if recipients else {})}, ensure_ascii=True)


def recipient_fingerprint(recipients):
    canonical = json.dumps(sorted(set(recipients)), separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def stored_recipient_fingerprint(stored):
    try:
        data = json.loads(stored or '{}')
        if not isinstance(data, dict) or data.get('contract') != 'invitation_reason/1':
            return None
        value = data.get('recipient_fingerprint')
        return value if isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value) else None
    except (ValueError, TypeError):
        return None

// Safe server vocabulary. Provider messages and arbitrary item.error never reach the DOM.
const reasons = {
  organization_unsupported: 'Приглашение недоступно: этот вариант участия организации пока не поддерживается',
  access_changed: 'Приглашение не отправлено: организация или доступ участника изменились',
  permission_changed: 'Приглашение не отправлено: ваши права на организацию изменились',
  session_expired: 'Сессия завершилась. Войдите снова, чтобы проверить приглашения',
  invalid_request: 'Не удалось подготовить корректный запрос приглашения',
  batch_incomplete: 'Не удалось подтвердить исход для всех выбранных участников',
  invalid_email: 'Приглашение не отправлено: указан некорректный email',
  questionnaire_unconfirmed: 'Приглашение не отправлено: для этой оценки не подтверждены сведения организации',
  questionnaire_incomplete: 'Приглашение не отправлено: заполните цель оценки и использование результатов',
  organization_changed: 'Приглашение не отправлено: сведения организации изменились. Проверьте и подтвердите их',
  member_unavailable: 'Участника нельзя пригласить в эту организацию. Обновите список и проверьте его доступ',
  permission_denied: 'Недостаточно прав для приглашения участников этой организации',
  mail_not_configured: 'Приглашения недоступны: сервис отправки не настроен',
  provider_rejected: 'Приглашение не отправлено: почтовый сервис отклонил запрос',
  provider_recipient: 'Приглашение не отправлено: почтовый сервис отклонил адрес участника',
  provider_sender: 'Приглашение не отправлено: почтовый сервис не подтвердил отправителя. Требуется проверка оператором',
  provider_access: 'Приглашение не отправлено: почтовый сервис отклонил доступ. Требуется проверка оператором',
  provider_limit: 'Почтовый сервис временно ограничил отправку. Повторите позже',
  provider_temporary: 'Почтовый сервис временно отказал в отправке. Повторите позже',
  context_changed: 'Почтовый сервис мог принять письмо, но состояние приглашения изменилось',
  operation_mismatch: 'Не удалось восстановить эту попытку: её данные не совпадают с текущим действием',
  link_used: 'Ссылка использована', link_revoked: 'Ссылка отозвана', link_expired: 'Срок ссылки истёк',
};
const common = new Set(['mail_not_configured', 'provider_access', 'provider_sender', 'provider_limit', 'provider_temporary', 'permission_denied', 'permission_changed', 'session_expired']);
export const invitationFacts = (item = {}) => {
  const delivery = item.delivery_status || item.invitation_delivery_status || item.status || 'not_sent';
  const outcome = delivery === 'not_sent' ? 'not_attempted' : ['accepted', 'already_registered'].includes(delivery) ? 'accepted' : delivery === 'error' ? 'failed' :
    ['queued', 'in_flight'].includes(delivery) ? 'pending' : 'unknown';
  return { ...item, delivery_status: delivery, outcome };
};
export const invitationMessage = (value = {}, { compact = false } = {}) => {
  const item = invitationFacts(value);
  if (item.outcome === 'not_attempted') return 'Письмо не отправлено';
  if (item.outcome === 'accepted') return item.replayed ? 'Эта попытка уже подтверждена: письмо принято сервисом' : 'Письмо принято почтовым сервисом';
  if (compact && common.has(item.reason_code)) return item.outcome === 'failed' ? 'Приглашение не отправлено' : 'Исход отправки уточняется';
  if (item.replayed && item.outcome === 'failed') return 'Предыдущая попытка завершилась ошибкой: ' + (reasons[item.reason_code] || 'причину отказа пока не удалось уточнить');
  if (reasons[item.reason_code]) return reasons[item.reason_code];
  if (item.outcome === 'failed') return 'Приглашение не отправлено. Причину отказа пока не удалось уточнить';
  if (item.delivery_status === 'in_flight') return 'Отправляем приглашение';
  if (item.delivery_status === 'queued') return 'Приглашение подготовлено. Отправка ещё не подтверждена';
  if (item.reason_code === 'operation_not_found') return 'Результат этой попытки пока не найден';
  if (item.reason_code === 'sending') return 'Отправка ещё не подтверждена. Проверяем эту попытку';
  return 'Не удалось подтвердить отправку. Письмо могло быть принято сервисом';
};
export const invitationCommonMessage = (items = []) => [...new Set(items.filter(item => common.has(item.reason_code))
  .map(item => invitationMessage(item)))].join('. ');
export const invitationSummary = (items = []) => {
  const counts = { accepted: 0, failed: 0, unknown: 0 };
  items.forEach(item => { const fact = invitationFacts(item); if (fact.outcome !== 'not_attempted') counts[fact.outcome === 'pending' ? 'unknown' : fact.outcome] += 1; });
  return 'Приняты сервисом: ' + counts.accepted + '. Не отправлены: ' + counts.failed + '. Исход уточняется: ' + counts.unknown;
};
export const safeInvitationItem = (item = {}) => {
  const clean = { email: String(item.email || '').trim().toLowerCase() };
  if (['not_sent', 'accepted', 'already_registered', 'error', 'queued', 'sending', 'uncertain', 'in_flight'].includes(item.status)) clean.status = item.status;
  for (const key of ['invitation_id']) if (Number.isInteger(item[key]) && item[key] > 0) clean[key] = item[key];
  for (const key of ['created_at', 'expires_at']) if (typeof item[key] === 'string' && Number.isFinite(Date.parse(item[key]))) clean[key] = new Date(item[key]).toISOString();
  if (['not_sent', 'accepted', 'error', 'queued', 'sending', 'uncertain', 'in_flight'].includes(item.delivery_status)) clean.delivery_status = item.delivery_status;
  if (['not_created', 'active', 'expired', 'revoked', 'used'].includes(item.link_status)) clean.link_status = item.link_status;
  if (Object.prototype.hasOwnProperty.call(reasons, item.reason_code) || ['delivery_unknown', 'operation_not_found', 'failed_unclassified', 'queued', 'sending', 'accepted', 'not_attempted'].includes(item.reason_code)) clean.reason_code = item.reason_code;
  if (['none', 'check', 'retry', 'retry_later', 'review_member', 'review_organization', 'operator', 'refresh_context'].includes(item.next_action)) clean.next_action = item.next_action;
  if (typeof item.operation_id === 'string' && item.operation_id.length <= 200) clean.operation_id = item.operation_id;
  if (item.replayed === true) clean.replayed = true;
  const missing = item.reason_params?.missing_fields;
  if (item.reason_code === 'questionnaire_incomplete' && Array.isArray(missing)) clean.reason_params = { missing_fields: ['purpose', 'results_usage'].filter(field => missing.includes(field)) };
  const retry = item.reason_params?.retry_after_seconds;
  if (item.reason_code === 'provider_limit' && Number.isInteger(retry) && retry >= 0 && retry <= 86400) clean.reason_params = { retry_after_seconds: retry };
  return clean;
};
export const exactInvitationItems = (response, emails, previous = [], operationId = null) => {
  const items = Array.isArray(response?.items) ? response.items : [];
  const scopeMatches = items.every(item => emails.includes(String(item?.email || '').trim().toLowerCase()));
  return emails.map(email => {
    const found = items.filter(item => String(item?.email || '').trim().toLowerCase() === email);
    const savedItem = (Array.isArray(previous) ? previous : []).find(item => item.email === email);
    const saved = savedItem ? safeInvitationItem(savedItem) : null;
    const identityMatches = scopeMatches && found.length === 1 && (!operationId || !found[0].operation_id || found[0].operation_id === operationId) &&
      !(saved?.invitation_id && found[0].invitation_id && saved.invitation_id !== found[0].invitation_id);
    const candidate = identityMatches && ['accepted', 'already_registered', 'error', 'queued', 'sending', 'uncertain'].includes(found[0].status) ? safeInvitationItem(found[0]) : null;
    // A missing row cannot erase a known refusal before INSERT or a confirmed acceptance.
    if (saved && ['accepted', 'failed'].includes(invitationFacts(saved).outcome) && (!candidate || invitationFacts(candidate).outcome === 'unknown')) return saved;
    return candidate || { email, status: 'uncertain', reason_code: 'delivery_unknown' };
  });
};
export const invitationLinkMessage = (status, expires = '') => ({
  not_created: 'Персональная ссылка не создана', active: expires ? 'Ссылка действует до ' + expires : 'Актуальность ссылки не подтверждена',
  expired: 'Срок ссылки истёк', revoked: 'Ссылка отозвана', used: 'Ссылка использована',
}[status] || 'Актуальность ссылки не подтверждена');

export const invitationMissingText = item => {
  const names = { purpose: 'цель оценки', results_usage: 'использование результатов' };
  const fields = item.reason_params?.missing_fields;
  return item.reason_code === 'questionnaire_incomplete' && Array.isArray(fields)
    ? fields.filter(field => Object.prototype.hasOwnProperty.call(names, field)).map(field => names[field]).join(', ') : '';
};

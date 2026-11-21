export const participantReportAudience = 'Вы и действующие администраторы вашей организации.';

// W02 v5 participant copy. Status and permitted actions still come from server contracts.
export const waitingPresentation = (readiness = {}) => {
  const reason = String(readiness.reason || '');
  if (reason.startsWith('participant_fields:')) {
    const labels = { position: 'должность', full_name: 'ФИО', email: 'email' };
    const missing = reason.slice('participant_fields:'.length).split(',').map((key) => labels[key]).filter(Boolean);
    return { title: 'Нужно уточнить сведения участника',
      description: missing.length ? 'В карточке участника не заполнены: ' + missing.join(', ') + '.' : 'В карточке участника не заполнены обязательные сведения.',
      detail: 'Когда сведения будут дополнены, вы сможете продолжить здесь.', button: 'Проверить готовность' };
  }
  const organizationReasons = {
    active_membership: ['Нужно уточнить доступ к организации', 'Сейчас нельзя однозначно подтвердить ваше активное участие в организации.'],
    confirmed_questionnaire: ['Анкета назначения пока не подтверждена', 'Для назначенной оценки пока нет подтверждённой анкеты.'],
    early_minimum: ['Нужно дополнить анкету назначения', 'В анкете назначенной оценки отсутствуют обязательные сведения.'],
    assessment_assignment: ['Нужно уточнить назначение оценки', 'Найдено несколько назначений. Сейчас нельзя однозначно определить вашу оценку.'],
  };
  if (readiness.status === 'waiting_for_organization' && organizationReasons[reason]) return {
    title: organizationReasons[reason][0], description: organizationReasons[reason][1],
    detail: 'Когда настройка будет завершена, здесь появится следующий шаг.', button: 'Проверить готовность',
  };
  if (readiness.status === 'waiting_for_assignment') return {
    title: 'Оценка пока не назначена', description: 'Сейчас для вашего аккаунта нет назначенной оценки.',
    detail: 'Проверьте назначение позже. Когда оно появится, вы сможете продолжить здесь.', button: 'Проверить назначение',
  };
  if (['expired', 'access_expired'].includes(readiness.status)) return {
    title: 'Срок доступа к оценке закончился', description: 'Сейчас начать эту оценку нельзя. Если появится новое назначение или изменится доступ, состояние обновится здесь.',
    detail: 'Время выполнения ещё не идёт.', button: 'Проверить состояние',
  };
  if (readiness.status === 'network') return {
    title: 'Не удалось проверить готовность', description: 'Нет связи с сервером. Пока неизвестно, завершилась ли подготовка.',
    detail: 'Повторите проверку. Это не запускает подготовку заново.', button: 'Повторить проверку',
  };
  return { title: 'Нужны сведения организации',
    description: 'Организация ещё завершает настройку вашей оценки. Когда сведения будут готовы, здесь появится следующий шаг.',
    detail: 'Время выполнения ещё не идёт.', button: 'Проверить готовность' };
};

export const readinessPresentation = (status, { retryAllowed = false, pendingStart = false, readbackAdmitted = false } = {}) => {
  const action = 'refresh';
  const base = { action, button: 'Проверить состояние', timeNotice: true };
  const copy = {
    conflict: { title: 'Состояние оценки изменилось', description: 'Во время действия изменились сведения или назначение оценки.',
      detail: 'Обновите состояние, чтобы продолжить с актуальными данными. Сохранённые ответы останутся на месте.', button: 'Обновить состояние' },
    service: { title: 'Подготовка временно недоступна', description: 'Сервис сейчас не отвечает. Ваши ответы сохранены.',
      detail: 'Проверьте состояние позже. Повторная проверка не создаёт новую подготовку.' },
    access: { title: 'Доступ к оценке изменился', description: 'Сейчас нет подтверждённого доступа к этой оценке.',
      detail: 'Обновите состояние. Ваши ранее сохранённые ответы не удаляются.', button: 'Обновить состояние' },
    plan_blocked: { title: 'Старт оценки пока недоступен', description: 'План подготовлен, но готовность к началу ещё не подтверждена.',
      detail: 'Обновите состояние. До подтверждения начать оценку нельзя.' },
    plan_missing: { title: 'Подготовленный план пока недоступен', description: 'Подготовка завершилась, но план оценки ещё не получен.',
      detail: 'Повторите проверку. Знакомство заново проходить не нужно.' },
    network: { ...waitingPresentation({ status: 'network' }) },
    organization: { title: 'Нужны сведения организации',
      description: 'Организация ещё завершает настройку вашей оценки. Ваши ответы сохранены, повторно заполнять их не потребуется.',
      detail: 'Когда сведения будут готовы, здесь появится следующий шаг.', button: 'Проверить готовность' },
    failed: { title: 'Подготовка оценки', description: 'Ваши ответы сохранены.',
      detail: retryAllowed ? 'Вы можете повторить подготовку. Повторно проходить знакомство не нужно.' :
        'Повторная подготовка пока недоступна. Вы можете проверить, изменилось ли состояние.',
      action: retryAllowed ? 'retry' : action, button: retryAllowed ? 'Повторить подготовку' : base.button },
    preparing: { title: 'Готовим вашу оценку', description: 'Готовим план и первую ситуацию.',
      detail: 'Вы можете вернуться позже. Ваши ответы сохранены.', button: 'Проверить готовность' },
  };
  if (status === 'ready') {
    if (pendingStart) return readbackAdmitted ? {
      title: 'Начало оценки ещё не подтверждено', description: 'Проверка показала, что оценка пока не началась. Можно повторить переход к первой ситуации.',
      detail: 'Повтор не создаёт новую оценку.', action: 'start', button: 'Повторить старт',
    } : {
      title: 'Проверяем начало оценки', description: 'Ответ на нажатие «Приступить к оценке» не получен. Оценка могла уже начаться.',
      detail: 'Сначала проверьте состояние. Если начало подтверждено, вы перейдёте к текущей ситуации.', action: 'check_start', button: base.button,
    };
    return { title: 'Ваши кейсы подготовлены', description: 'Прочитайте условия каждой ситуации и отвечайте так, как поступили бы на работе.',
      action: 'start', button: 'Приступить к оценке' };
  }
  return { ...base, ...(copy[status] || copy.preparing) };
};

// Fixed decorative W02 icons; no server text is interpolated into SVG.
export const readinessIcon = (status) => {
  const icons = {
    ready: '<path d="m5 12 4 4L19 6"/>',
    clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    info: '<circle cx="12" cy="12" r="8"/><path d="M12 11v5m0-9v.1"/>',
    error: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.1"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  };
  const kind = status === 'ready' ? 'ready' : ['preparing', 'loading', 'plan_missing', 'expired', 'access_expired'].includes(status) ? 'clock'
    : ['failed', 'network', 'service', 'load-error'].includes(status) ? 'error' : ['access', 'plan_blocked'].includes(status) ? 'lock' : 'info';
  return '<svg viewBox="0 0 24 24">' + icons[kind] + '</svg>';
};

// Only the public preparation error projection is suitable for participant copy.
const preparationFailureCodes = new Set([
  'ASSESSMENT_CYCLE_PREPARATION_FAILED',
  'ASSESSMENT_CYCLE_PREPARATION_TECHNICAL_FAILURE',
  'ASSESSMENT_VERIFICATION_INCOMPLETE',
  'ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE',
  'ASSESSMENT_AS_NOT_ADMITTED',
]);
export const preparationFailureMessage = (error) => preparationFailureCodes.has(error?.code) ? error.message : '';

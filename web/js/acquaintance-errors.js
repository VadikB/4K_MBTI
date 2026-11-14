// Participant-safe presentation for acquaintance and its first explicit start.
// Technical IDs stay separate from the explanation; unknown API detail is not UI copy.
const reasons = {
  ASSIGNMENT_CANCELLED: 'Назначение оценки отменено. Обратитесь к администратору организации.',
  AS_NOT_ADMITTED: 'Ситуация не прошла обязательную проверку. Обратитесь к организатору оценки.',
  ASSESSMENT_AS_NOT_ADMITTED: 'Ситуация не прошла обязательную проверку. Обратитесь к организатору оценки.',
  ASSESSMENT_START_NOT_READY: 'Условия старта ещё не подтверждены. Проверьте готовность оценки.',
  M7_START_NOT_ADMITTED: 'Старт оценки не допущен: обязательные условия не подтверждены. Обратитесь к организатору оценки.',
  W02_ACQUAINTANCE_NOT_READY: 'Сведения для знакомства пока не готовы. Проверьте готовность или обратитесь к организатору.',
  W02_ANSWER_REQUIRED: 'Напишите ответ перед сохранением.',
  W02_THREE_ANSWERS_REQUIRED: 'Ответьте на все три вопроса перед подтверждением.',
  W02_CONSENT_REQUIRED: 'Подтвердите согласие перед сохранением ответов.',
  W02_CONSENT_VERSION_MISMATCH: 'Условия согласия изменились. Обновите сведения и подтвердите актуальные условия.',
  W02_ANSWERS_FROZEN: 'Ответы уже подтверждены. Для их изменения нужно новое назначение оценки.',
  W02_CONFIRMATION_REQUIRED: 'Подтвердите ответы перед подготовкой оценки.',
  W02_MANDATORY_STEPS_REQUIRED: 'Завершите обязательные шаги знакомства перед стартом.',
  W02_ORGANIZATION_DATA_REQUIRED: 'Для оценки нужны подтверждённые сведения организации. Обратитесь к организатору.',
  W02_ASSIGNMENT_SOURCES_REQUIRED: 'Источники назначения не подтверждены. Обратитесь к организатору оценки.',
  W02_ASSIGNMENT_SCOPE_MISMATCH: 'Назначение изменилось. Обновите состояние знакомства.',
  W02_PROFILE_ASSIGNMENT_SCOPE_MISMATCH: 'Профиль не соответствует текущему назначению. Обновите состояние и обратитесь к организатору.',
  W02_PROFILE_CONFLICT_REQUIRES_RESPONSIBLE: 'В сведениях профиля есть противоречия. Их должен проверить ответственный за оценку.',
  M4_PROFILE_SCOPE_MISMATCH: 'Профиль не соответствует выбранной оценке. Обновите состояние и подтвердите актуальный профиль.',
  M4_PROFILE_NOT_READY: 'Контекст оценки ещё не подтверждён. Проверьте готовность профиля.',
  M4_SOURCE_UNAVAILABLE: 'Источники профиля недоступны. Обратитесь к ответственному за оценку.',
  M4_CHECKSUM_MISMATCH: 'Целостность источников профиля не подтверждена. Обратитесь к ответственному за оценку.',
};

export const acquaintanceErrorMessage = (error) => {
  const raw = String(error?.message || '');
  const code = error?.code || Object.keys(reasons).find((key) => raw === key || raw.startsWith(key + ':'));
  const reference = error?.requestId || error?.operationId ||
    (/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(raw.trim()) ? raw.trim() : null);
  const suffix = reference ? ` Код обращения: ${reference}.` : '';
  if (reasons[code]) return reasons[code] + suffix;
  if (error?.name === 'AssessmentStartUnknown') {
    const causeCode = error.cause?.code || Object.keys(reasons).find((key) =>
      String(error.cause?.message || '').split(':')[0] === key);
    return (reasons[causeCode] ? reasons[causeCode] + ' ' : '') + raw + suffix;
  }
  if (['TypeError', 'AbortError', 'RequestDeadlineError'].includes(error?.name) ||
      /failed to fetch|networkerror|load failed|network request failed|fetch failed/i.test(raw)) {
    return 'Не удалось получить подтверждение сервера. Проверьте соединение и состояние перед повтором. Введённый текст оставлен на этой странице.' + suffix;
  }
  if (error?.status) {
    const message = error.status === 403 ? 'Доступ к этой оценке не подтверждён. Обновите состояние.'
      : error.status === 409 ? 'Состояние оценки изменилось или старт недоступен. Обновите состояние; если отказ повторится, обратитесь к организатору.'
        : 'Не удалось подтвердить действие. Проверьте состояние и повторите проверку.';
    return message + suffix;
  }
  return raw || 'Не удалось подтвердить действие. Повторите проверку состояния.';
};

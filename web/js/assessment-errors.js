let assessmentViewGeneration = 0;
export const getAssessmentViewGeneration = () => assessmentViewGeneration;
export const advanceAssessmentViewGeneration = () => { assessmentViewGeneration += 1; };

// Assessment UI policy only; business refusals from the API retain their reason.
export const assessmentRuntimeErrorMessage = (error, { draftSaved = false } = {}) => {
  const raw = String(error?.message || '');
  if (['QuotaExceededError', 'SecurityError', 'InvalidStateError'].includes(error?.name)) {
    return 'Хранилище браузера недоступно. Сохранение введённого текста не подтверждено. Оставьте страницу открытой.';
  }
  const technical = error?.name === 'TypeError' || error?.name === 'AbortError'
    || /failed to fetch|networkerror|load failed|network request failed|fetch failed/i.test(raw);
  if (technical) {
    return 'Не удалось обновить состояние оценки. Проверьте соединение.'
      + (draftSaved ? ' Введённый текст сохранён.' : ' Сохранение введённого текста не подтверждено.');
  }
  return raw || 'Не удалось обновить состояние оценки. Повторите действие.';
};

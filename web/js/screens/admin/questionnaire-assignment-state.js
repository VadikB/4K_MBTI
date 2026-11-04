// UI read certainty is separate from the server's questionnaire confirmation.
export const questionnaireAssignmentState = (loadState, confirmed) => {
  const status = loadState?.status;
  if (!['ready', 'empty'].includes(status)) {
    const checking = status === 'loading';
    return {
      canAssign: false,
      label: (confirmed ? 'подтверждена по сохранённой редакции; ' : '') +
        (checking ? 'проверяем актуальность' : 'актуальность не проверена'),
      blocker: checking
        ? 'Проверяем сохранённую анкету. Дождитесь завершения чтения.'
        : 'Не удалось проверить сохранённую анкету. Повторите загрузку; подтверждение не отменено.',
    };
  }
  return confirmed ? { canAssign: true, label: 'подтверждена', blocker: null }
    : { canAssign: false, label: 'не подтверждена',
      blocker: 'Анкета для выбранной оценки не подтверждена. Подтвердите сведения перед назначением.' };
};

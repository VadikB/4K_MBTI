const unknownFailure = 'Произошла ошибка обработки. Подробности пока недоступны';

const participantMessages = {
  answer: 'Ответ сохранён, но обработать его не удалось. Отправлять ответ повторно не нужно. Обратитесь к администратору оценки.',
  report: 'Прохождение завершено. Не удалось сформировать итоговый отчёт.',
  calculation: 'Не удалось рассчитать итоговый результат',
};

export const participantFailureMessage = (stage) => participantMessages[stage] || unknownFailure;

export const adminFailureCopy = (stage) => ({
  answer: {
    title: 'Не удалось обработать ответ участника',
    detail: 'Ответ сохранён. Прохождение остановилось на обработке ответа в текущей ситуации',
  },
  report: {
    title: 'Не удалось сформировать итоговый отчёт',
    detail: 'Сбор ответов завершён. Ошибка возникла при подготовке отчёта',
  },
  calculation: {
    title: participantMessages.calculation,
    detail: 'Сбор ответов завершён. Не удалось рассчитать итоговый результат',
  },
}[stage] || { title: unknownFailure, detail: unknownFailure });

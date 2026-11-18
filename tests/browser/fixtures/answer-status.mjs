// The existing status zone contains the accepted receipt as well as errors.
// Only confirmed neutral receipt states satisfy a successful answer check.
export const acceptedAnswerNotice = page => page.locator('#interview-error.processing-notice[data-tone="neutral"]')
  .filter({ hasText: /^Ответ сохранён\.(?:$| (?:Ожидайте завершения обработки\.|Состояние обработки уточняется\.|Обработка занимает больше времени\.))/ });

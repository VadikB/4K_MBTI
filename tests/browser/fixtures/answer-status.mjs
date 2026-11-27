// After the server confirms the Turn, the zone may show its neutral receipt or
// be cleared when the character has replied/processing has finished. Visible
// read errors, failed processing and unknown receipts never satisfy this check.
export const settledAnswerStatus = page => page.locator('#interview-error[hidden]').or(
  page.locator('#interview-error.processing-notice[data-tone="neutral"]')
    .filter({ hasText: /^Ответ сохранён\.(?:$| (?:Идёт обработка|Состояние обработки уточняется\.|Обработка занимает больше времени\.))/ }));

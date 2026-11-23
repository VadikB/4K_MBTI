import { state } from '../state.js';

const pending = new WeakMap();
const initialLabels = new WeakMap();
const labelFor = (button) => button.querySelector('[data-report-pdf-label]') || button;
const failureMessage = 'Не удалось скачать PDF. Попробуйте ещё раз.';

export const resetReportDownload = (button) => {
  pending.get(button)?.abort();
  pending.delete(button);
  button.removeAttribute('aria-busy');
  const label = labelFor(button);
  if (initialLabels.has(label)) label.textContent = initialLabels.get(label);
};

// The deadline includes reading the body, not just receiving HTTP headers.
export const withReportDeadline = async (read, controller = new AbortController()) => {
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    return await read(controller.signal);
  } finally {
    clearTimeout(timer);
  }
};

export const downloadReportPdf = async ({ button, status, url, filename, isCurrent = () => true }) => {
  if (pending.has(button) || button.disabled) return;
  const identityEpoch = state.identityEpoch;
  const ownerId = state.pendingUser?.id;
  const screen = state.currentScreen;
  const reportEpoch = state.reportRequestEpoch;
  const controller = new AbortController();
  pending.set(button, controller);
  const current = () => pending.get(button) === controller && button.isConnected
    && state.identityEpoch === identityEpoch && state.pendingUser?.id === ownerId
    && state.currentScreen === screen && state.reportRequestEpoch === reportEpoch && isCurrent();
  const label = labelFor(button);
  if (!initialLabels.has(label)) initialLabels.set(label, label.textContent);
  const restoreFocus = document.activeElement === button;
  let unavailable = false;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  if (status) status.textContent = 'Скачиваем PDF…';
  try {
    const blob = await withReportDeadline(async (signal) => {
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', signal });
      if (!response.ok) throw Object.assign(new Error('PDF_UNAVAILABLE'), { status: response.status });
      if (response.headers.get('content-type')?.split(';')[0].trim() !== 'application/pdf') {
        throw new Error('PDF_INVALID_TYPE');
      }
      const result = await response.blob();
      if (await result.slice(0, 5).text() !== '%PDF-') throw new Error('PDF_INVALID');
      return result;
    }, controller);
    if (!current()) return;
    const href = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = href;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
    label.textContent = initialLabels.get(label);
    if (status) status.textContent = 'PDF скачан.';
  } catch (error) {
    if (!current()) return;
    const refused = [401, 403].includes(error.status);
    const missing = error.status === 404;
    unavailable = refused || missing;
    label.textContent = unavailable ? initialLabels.get(label) : 'Повторить скачивание PDF';
    if (status) status.textContent = refused ? 'Доступ к PDF этой редакции недоступен.'
      : missing ? 'Сохранённая редакция для PDF не найдена.' : failureMessage;
  } finally {
    if (pending.get(button) === controller) {
      const canRefocus = restoreFocus && current() && document.activeElement === document.body;
      pending.delete(button);
      button.disabled = unavailable;
      button.removeAttribute('aria-busy');
      if (canRefocus && unavailable && status) {
        status.tabIndex = -1;
        status.focus({ preventScroll: true });
      } else if (canRefocus && !unavailable) {
        button.focus({ preventScroll: true });
      }
    }
  }
};

export const bindReportPdf = (button, options) => {
  button.addEventListener('click', () => void downloadReportPdf({ button, ...options }));
};

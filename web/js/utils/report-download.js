import { state } from '../state.js';

const pending = new WeakMap();
const failureMessage = 'Не удалось скачать PDF. Попробуйте ещё раз.';

export const resetReportDownload = (button) => {
  pending.get(button)?.abort();
  pending.delete(button);
  button.removeAttribute('aria-busy');
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
  if (pending.has(button)) return;
  const identityEpoch = state.identityEpoch;
  const ownerId = state.pendingUser?.id;
  const screen = state.currentScreen;
  const reportEpoch = state.reportRequestEpoch;
  const controller = new AbortController();
  pending.set(button, controller);
  const current = () => pending.get(button) === controller && button.isConnected
    && state.identityEpoch === identityEpoch && state.pendingUser?.id === ownerId
    && state.currentScreen === screen && state.reportRequestEpoch === reportEpoch && isCurrent();
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  if (status) status.textContent = 'Скачиваем PDF…';
  try {
    const blob = await withReportDeadline(async (signal) => {
      const response = await fetch(url, { credentials: 'same-origin', signal });
      if (!response.ok || response.headers.get('content-type')?.split(';')[0].trim() !== 'application/pdf') {
        throw new Error('PDF_UNAVAILABLE');
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
    if (status) status.textContent = 'PDF скачан.';
  } catch {
    if (current() && status) status.textContent = failureMessage;
  } finally {
    if (pending.get(button) === controller) {
      pending.delete(button);
      button.disabled = false;
      button.removeAttribute('aria-busy');
    }
  }
};

export const bindReportPdf = (button, options) => {
  button.addEventListener('click', () => void downloadReportPdf({ button, ...options }));
};

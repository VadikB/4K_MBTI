let unauthorizedResponseHandler = null;
let sessionGeneration = 0;
let unauthorizedRecovery = null;
let sessionChannel = null;
let requestTrackingInstalled = false;
const responseGenerations = new WeakMap();

const isCurrentGeneration = (generation) => generation === sessionGeneration;

export const getSessionGeneration = () => sessionGeneration;

export const advanceSessionGeneration = ({ broadcast = true } = {}) => {
  sessionGeneration += 1;
  if (broadcast) {
    sessionChannel?.postMessage({ type: 'session-generation-changed' });
  }
  return sessionGeneration;
};

export const createSessionAwareFetch = (fetchImplementation) => async (...args) => {
  const requestGeneration = sessionGeneration;
  const response = await fetchImplementation(...args);
  responseGenerations.set(response, requestGeneration);
  return response;
};

export const installSessionRequestTracking = () => {
  if (requestTrackingInstalled || typeof globalThis.fetch !== 'function') {
    return;
  }
  globalThis.fetch = createSessionAwareFetch(globalThis.fetch.bind(globalThis));
  requestTrackingInstalled = true;

  if (typeof window !== 'undefined' && typeof window.BroadcastChannel === 'function') {
    sessionChannel = new window.BroadcastChannel('agent4k-session-generation');
    sessionChannel.addEventListener('message', (event) => {
      if (event.data?.type === 'session-generation-changed') {
        advanceSessionGeneration({ broadcast: false });
        Promise.resolve(unauthorizedResponseHandler?.({ advance: false, broadcast: false })).catch((error) => {
          console.error('Failed to reconcile a session change from another tab', error);
        });
      }
    });
  }
};

export const registerUnauthorizedResponseHandler = (handler) => {
  unauthorizedResponseHandler = typeof handler === 'function' ? handler : null;
};

const notifyUnauthorizedResponse = (requestGeneration) => {
  if (!unauthorizedResponseHandler || !isCurrentGeneration(requestGeneration)) {
    return;
  }
  if (unauthorizedRecovery?.generation === requestGeneration) {
    return;
  }
  const recovery = {
    generation: requestGeneration,
    promise: Promise.resolve()
    .then(() => {
      if (isCurrentGeneration(requestGeneration)) {
        return unauthorizedResponseHandler();
      }
    })
    .catch((error) => {
      console.error('Failed to recover from an expired server session', error);
    })
    .finally(() => {
      if (unauthorizedRecovery === recovery) {
        unauthorizedRecovery = null;
      }
    }),
  };
  unauthorizedRecovery = recovery;
};

export class ApiResponseError extends Error {
  constructor(message, status, { code = null, requestId = null, outcomeUnknown = false } = {}) {
    super(message);
    this.name = 'ApiResponseError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.outcomeUnknown = outcomeUnknown;
  }
}

export class StaleApiResponseError extends Error {
  constructor() {
    super('Ответ относится к устаревшей пользовательской сессии.');
    this.name = 'StaleApiResponseError';
  }
}

export const authenticatedJourneyErrorMessage = (error) => error?.status === 401
  ? 'Сессия входа не сохранилась. Повторите вход; если ошибка повторится, обратитесь к администратору стенда.'
  : 'Не удалось определить актуальный этап. Обновите страницу или повторите вход.';

const apiErrorMessages = {
  PURGE_PREVIEW_STALE: 'Состав удаления изменился. Обновите предварительный просмотр и подтвердите новый состав; удаление не выполнено.',
  PURGE_ATTRIBUTION_SCHEMA_UNSAFE: 'Удаление остановлено: обнаружена небезопасная ссылка авторства. Передайте код обращения техническому администратору.',
  PURGE_EXECUTION_FAILED: 'Удаление не подтверждено и было отменено. Обновите состояние; перед повтором передайте код обращения техническому администратору.',
  CANNOT_PURGE_CURRENT_ACCOUNT: 'Нельзя удалить аккаунт, под которым выполнен текущий вход. Используйте другой аккаунт суперадминистратора.',
  CANNOT_PURGE_ORGANIZATION_WITH_CURRENT_ACCOUNT: 'Нельзя удалить организацию вместе с аккаунтом текущего входа. Используйте другой аккаунт суперадминистратора.',
  ORGANIZATION_MEMBERSHIP_CONFLICT: 'Пользователь уже состоит в другой организации. Суперадминистратор может открыть текущую организацию или выполнить явный перенос.',
  ORGANIZATION_TRANSFER_LAST_ADMIN: 'Перенос невозможен: сначала назначьте другого администратора исходной организации.',
  ORGANIZATION_TRANSFER_ACTIVE_ACQUAINTANCE: 'Перенос невозможен, пока участник проходит знакомство. Завершите текущий процесс или обратитесь к суперадминистратору.',
  ORGANIZATION_TRANSFER_SOURCE_CHANGED: 'Состав исходной организации изменился. Обновите список перед повтором.',
  ORGANIZATION_TRANSFER_TARGET_INACTIVE: 'Целевая организация неактивна. Выберите активную организацию.',
  ORGANIZATION_TRANSFER_TARGET_NOT_FOUND: 'Целевая организация не найдена. Обновите список организаций.',
  PROGRAM_ROLE_SELECTION_REQUIRED: 'Выберите одну из разрешённых ролей для этой оценки.',
  PROGRAM_ROLE_NOT_AVAILABLE: 'Выбранная роль недоступна для этой версии программы. Обновите список ролей и выберите доступную.',
  PROGRAM_NOT_CONNECTED: 'К организации не подключена программа оценки. Сначала подключите опубликованную программу.',
  PROGRAM_NOT_AVAILABLE: 'Выбранная программа недоступна. Выберите опубликованную версию.',
  PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS: 'Эта версия программы больше не принимает новые назначения. Подключите актуальную опубликованную версию.',
  PROGRAM_ASSIGNMENT_REF_MISMATCH: 'Выбранная оценка не соответствует подключённой программе. Выберите оценку этой программы и повторите назначение.',
  PROGRAM_CONFIGURATION_NOT_AVAILABLE: 'Настройка программы не завершена. Обратитесь к суперадминистратору.',
  PROGRAM_CATALOG_NOT_AVAILABLE: 'Каталог подключённой программы недоступен для новых назначений. Обратитесь к суперадминистратору.',
  PROGRAM_CATALOG_VERSION_MISMATCH: 'Версии программы и каталога не совпадают. Обратитесь к суперадминистратору.',
  PROGRAM_CATALOG_SCOPE_MISMATCH: 'Каталог программы недоступен этой организации. Обратитесь к суперадминистратору.',
  PROGRAM_SOURCE_SELECTION_STALE: 'Выбранная роль или версия программы устарела. Обновите карточку и повторите назначение.',
  ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED: 'Подтвердите сведения выбранной оценки перед назначением.',
  ASSIGNMENT_ALREADY_STARTED: 'Оценка уже началась. Отменить назначение нельзя.',
  ASSIGNMENT_CANCELLED: 'Это назначение оценки отменено администратором. Обратитесь к администратору организации.',
  ASSIGNMENT_NOT_FOUND: 'Назначение оценки не найдено или недоступно.',
  ASSIGNMENT_LINK_UNKNOWN: 'Отмена остановлена: для прежнего цикла нельзя однозначно определить поколение назначения. Обратитесь к техническому администратору.',
  ASSIGNMENT_CANCEL_IDEMPOTENCY_CONFLICT: 'Запрос отмены устарел. Обновите страницу и повторите действие.',
  ASSIGNMENT_STATE_STALE: 'Состояние назначения изменилось. Обновите страницу.',
  EMAIL_PROVIDER_NOT_CONFIGURED: 'Сервис приглашений не настроен. Обратитесь к техническому администратору.',
};

const errorCodeFrom = (data) => {
  const detail = data && typeof data === 'object' ? data.detail : null;
  const direct = data && typeof data === 'object' ? data.code || data.error_code : null;
  if (direct) return String(direct);
  if (detail && typeof detail === 'object') return String(detail.code || detail.error_code || '') || null;
  if (typeof detail !== 'string') return null;
  const normalized = detail.trim();
  if (Object.hasOwn(apiErrorMessages, normalized)) return normalized;
  return Object.keys(apiErrorMessages)
    .sort((left, right) => right.length - left.length)
    .find((code) => normalized.startsWith(code + ':')) || null;
};

const appendRequestId = (message, requestId) => requestId ? `${message} Код обращения: ${requestId}.` : message;

export const readApiResponse = async (response, fallbackMessage, { recoverUnauthorized = true } = {}) => {
  const requestGeneration = responseGenerations.get(response) ?? sessionGeneration;
  const rawText = await response.text();
  let data = null;

  if (rawText) {
    try {
      data = JSON.parse(rawText);
    } catch (_error) {
      data = null;
    }
  }

  if (!isCurrentGeneration(requestGeneration)) {
    throw new StaleApiResponseError();
  }

  if (!response.ok) {
    if (response.status === 401 && recoverUnauthorized) {
      notifyUnauthorizedResponse(requestGeneration);
    }
    const requestId = String(response.headers.get('x-request-id') || data?.request_id || data?.reference_id || '').trim() || null;
    const code = errorCodeFrom(data);
    const detailText = typeof data?.detail === 'string' ? data.detail : '';
    if (code === 'ORGANIZATION_MEMBERSHIP_CONFLICT' && detailText.startsWith(code + ':')) {
      throw new ApiResponseError(
        appendRequestId(detailText.slice(code.length + 1).trim(), requestId), response.status, { code, requestId },
      );
    }
    if (code && apiErrorMessages[code]) {
      throw new ApiResponseError(appendRequestId(apiErrorMessages[code], requestId), response.status, { code, requestId });
    }
    if (response.status >= 500) {
      throw new ApiResponseError(appendRequestId(
        'Сервис не смог выполнить операцию. Повторная отправка может быть небезопасна — сначала обновите состояние.', requestId,
      ), response.status, { code, requestId, outcomeUnknown: true });
    }
    if (data && typeof data === 'object' && 'detail' in data && data.detail) {
      const detail = typeof data.detail === 'object' ? data.detail.message : data.detail;
      throw new ApiResponseError(String(detail || fallbackMessage), response.status, { code, requestId });
    }
    if (rawText && rawText.trim()) {
      const contentType = String(response.headers.get('content-type') || '').toLowerCase();
      const looksLikeHtml = contentType.includes('text/html') || /^\s*<(?:!doctype|html|head|body)\b/i.test(rawText);
      if (looksLikeHtml) {
        throw new ApiResponseError(
          `${fallbackMessage} Сервер вернул ошибку ${response.status}. Попробуйте отправить еще раз.`,
          response.status,
        );
      }
      throw new ApiResponseError(rawText.trim().slice(0, 240), response.status, { code, requestId });
    }
    throw new ApiResponseError(fallbackMessage, response.status);
  }

  if (data === null) {
    throw new Error(fallbackMessage);
  }

  return data;
};

// The deadline covers headers AND body. Some proxies send headers then stall.
export const fetchWithDeadline = async (url, options = {}, timeoutMs = null) => {
  const controller = new AbortController();
  const deadline = timeoutMs ?? (String(options.method || 'GET').toUpperCase() === 'GET' ? 15000 : 30000);
  let timer;
  const forwardAbort = () => controller.abort(options.signal?.reason);
  options.signal?.addEventListener('abort', forwardAbort, { once: true });
  if (options.signal?.aborted) forwardAbort();
  try {
    return await Promise.race([
      (async () => {
        const response = await fetch(url, { ...options, signal: controller.signal });
        const body = await response.text();
        const buffered = new Response(body || null, {
          status: response.status, statusText: response.statusText, headers: response.headers,
        });
        responseGenerations.set(buffered, responseGenerations.get(response) ?? sessionGeneration);
        return buffered;
      })(),
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          const error = new Error('Сервер не ответил вовремя. Проверьте результат операции.');
          error.name = 'RequestDeadlineError';
          reject(error);
          controller.abort();
        }, deadline);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', forwardAbort);
  }
};

export const createOperationId = () =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : 'op-' + Date.now() + '-' + Math.random().toString(16).slice(2);

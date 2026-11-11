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
  PURGE_EXECUTION_FAILED: 'Не удалось подтвердить результат удаления. Проверьте исход той же подтверждённой операции; при повторном отказе передайте код обращения техническому администратору.',
  DELETION_RECEIPT_CONFLICT: 'Подтверждённая команда не соответствует квитанции удаления. Не повторяйте удаление с другими параметрами; обратитесь к техническому администратору.',
  CANNOT_PURGE_CURRENT_ACCOUNT: 'Нельзя удалить аккаунт, под которым выполнен текущий вход. Используйте другой аккаунт суперадминистратора.',
  CANNOT_PURGE_ORGANIZATION_WITH_CURRENT_ACCOUNT: 'Нельзя удалить организацию вместе с аккаунтом текущего входа. Используйте другой аккаунт суперадминистратора.',
  ORGANIZATION_MEMBERSHIP_CONFLICT: 'Пользователь уже состоит в другой организации. Добавление в другую организацию недоступно. Обратитесь к суперадминистратору.',
  ORGANIZATION_TRANSFER_LAST_ADMIN: 'Смена организации недоступна. Управляйте полномочиями в текущей организации.',
  ORGANIZATION_TRANSFER_ACTIVE_ACQUAINTANCE: 'Смена организации недоступна. Обратитесь к суперадминистратору.',
  ORGANIZATION_TRANSFER_SOURCE_CHANGED: 'Состав исходной организации изменился. Обновите список перед повтором.',
  ORGANIZATION_TRANSFER_TARGET_INACTIVE: 'Смена организации недоступна. Обратитесь к суперадминистратору.',
  ORGANIZATION_TRANSFER_TARGET_NOT_FOUND: 'Смена организации недоступна. Обновите список организаций.',
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
  INVITATION_ALREADY_USED: 'Приглашение уже использовано. Обычный вход и назначение участника сохранены.',
  INVITATION_NOT_FOUND: 'Приглашение больше не найдено. Обновите список участников.',
  INVITATION_STATE_CHANGED: 'Состояние участника изменилось. Обновите список участников перед следующим действием.',
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
    const detailText = typeof data?.detail === 'string' ? data.detail : String(data?.detail?.message || '');
    if (code === 'ORGANIZATION_MEMBERSHIP_CONFLICT' && detailText) {
      // Old servers may still attach an action that the current product cannot perform.
      const scopedReason = detailText.replace(/^ORGANIZATION_MEMBERSHIP_CONFLICT:\s*/, '')
        .replace(/(?:Суперадминистратор может|Откройте|Выполните)[^.!?]*(?:перенос|перенес)[^.!?]*[.!?]?/giu,
          'Добавление в другую организацию недоступно. Обратитесь к суперадминистратору.').trim();
      const message = scopedReason || apiErrorMessages[code];
      throw new ApiResponseError(appendRequestId(message, requestId), response.status, { code, requestId });
    }
    if (code && apiErrorMessages[code]) {
      throw new ApiResponseError(appendRequestId(apiErrorMessages[code], requestId), response.status, {
        code, requestId, outcomeUnknown: code === 'PURGE_EXECUTION_FAILED',
      });
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

const accountPurgeStorageKey = (actorId) => 'agent4k.accountPurge.' + Number(actorId);
const accountPurgeRequests = new Set();
const purgeCommandFields = ['actorId', 'targetUserId', 'email', 'fingerprint', 'operationId'];
const samePurgeCommand = (left, right) => purgeCommandFields.every((field) => left?.[field] === right?.[field]);
const purgeStorageError = () => new ApiResponseError(
  'Не удалось сохранить подтверждённую команду для восстановления после перезагрузки. Удаление не отправлено. Разрешите локальное хранилище и повторите подтверждение.',
  0, { code: 'PURGE_RECOVERY_STORAGE_UNAVAILABLE' },
);
const purgeRecoveryStorageError = () => new ApiResponseError(
  'Не удалось прочитать или сохранить состояние ранее подтверждённого удаления. Исход операции пока неизвестен. Восстановите доступ к локальному хранилищу и проверьте ту же операцию.',
  0, { code: 'PURGE_RECOVERY_STORAGE_UNAVAILABLE', outcomeUnknown: true },
);
const readAccountPurges = (actorId) => {
  const raw = globalThis.localStorage.getItem(accountPurgeStorageKey(actorId));
  const operations = raw ? JSON.parse(raw) : [];
  if (!Array.isArray(operations)) throw purgeStorageError();
  return operations.filter((operation) => Number(operation?.actorId) === Number(actorId) &&
    Number.isInteger(operation?.targetUserId) && operation.targetUserId > 0 &&
    operation.email && operation.fingerprint && operation.operationId);
};
const saveAccountPurges = (actorId, operations) => {
  try {
    const key = accountPurgeStorageKey(actorId);
    const serialized = JSON.stringify(operations);
    globalThis.localStorage.setItem(key, serialized);
    if (globalThis.localStorage.getItem(key) !== serialized) throw purgeStorageError();
  } catch (_error) {
    throw purgeStorageError();
  }
};

// Only the current actor can see or resume their own exact confirmed commands.
export const getPendingAccountPurges = (actorId) => {
  if (!Number(actorId)) return [];
  try { return readAccountPurges(actorId); } catch (_error) { return []; }
};

export const confirmAccountPurge = ({ actorId, targetUserId, email, fingerprint }) => {
  actorId = Number(actorId);
  targetUserId = Number(targetUserId);
  email = String(email || '').trim().toLowerCase();
  fingerprint = String(fingerprint || '').trim();
  if (!actorId || !Number.isInteger(targetUserId) || targetUserId <= 0 || !email || !fingerprint) {
    throw new ApiResponseError('Обновите состав удаления и подтвердите аккаунт заново.', 409);
  }
  let pending;
  try { pending = readAccountPurges(actorId); } catch (_error) { throw purgeStorageError(); }
  if (pending.some((operation) => operation.targetUserId === targetUserId)) {
    throw new ApiResponseError('Сначала выясните исход ранее подтверждённого удаления этого аккаунта.', 409,
      { code: 'PURGE_OUTCOME_PENDING', outcomeUnknown: true });
  }
  const operation = { actorId, targetUserId, email, fingerprint, operationId: createOperationId(), status: 'confirmed' };
  saveAccountPurges(actorId, [...pending, operation]);
  return Object.freeze(operation);
};

export const accountPurgeErrorMessage = (error, { phase = 'execute', unknown = error?.outcomeUnknown || !(error instanceof ApiResponseError) } = {}) => {
  if (error?.code === 'PURGE_RECOVERY_STORAGE_UNAVAILABLE') return error.message;
  if (phase === 'execute' && unknown) {
    return 'Исход удаления пока неизвестен. Проверьте результат той же подтверждённой операции. Новый состав удаления и новое подтверждение не требуются.';
  }
  if (error?.status === 401) return 'Сессия завершилась. Войдите снова, чтобы продолжить управление аккаунтами.';
  if (error?.status === 403) return 'Управление полным удалением доступно только суперадминистратору. Проверьте текущий аккаунт.';
  if (error?.code && apiErrorMessages[error.code]) return error.message;
  if (phase === 'preview') {
    return error?.status === 404
      ? 'Аккаунт или предварительный просмотр недоступен. Обновите список аккаунтов.'
      : 'Не удалось получить состав удаления. Проверьте соединение и повторите предварительный просмотр. Удаление не отправлено.';
  }
  return 'Удаление не выполнено. Обновите список и состав удаления, затем подтвердите действие заново.';
};

export const previewAccountPurge = async (targetUserId) => {
  const response = await fetchWithDeadline('/users/admin/users/' + Number(targetUserId) + '/purge-preview', {
    credentials: 'same-origin',
  });
  return readApiResponse(response, 'Не удалось построить состав полного удаления аккаунта.');
};

export const executeAccountPurge = async (operation, { actorId } = {}) => {
  if (Number(actorId) !== operation?.actorId) {
    throw new ApiResponseError('Подтверждение удаления относится к другому аккаунту входа.', 403);
  }
  let pending;
  try { pending = readAccountPurges(actorId); } catch (_error) { throw purgeRecoveryStorageError(); }
  const saved = pending.find((item) => item.targetUserId === operation.targetUserId);
  if (!samePurgeCommand(saved, operation)) {
    throw new ApiResponseError('Состав подтверждённой команды изменился. Обновите состояние удаления.', 409);
  }
  if (accountPurgeRequests.has(saved.operationId)) {
    throw new ApiResponseError('Удаление уже проверяется. Дождитесь результата.', 409,
      { code: 'PURGE_OUTCOME_PENDING', outcomeUnknown: true });
  }
  const wasUnknown = saved.status === 'unknown';
  // Persist before the request: closing/reloading the page must retain this same operation_id.
  try {
    saveAccountPurges(actorId, pending.map((item) => samePurgeCommand(item, saved) ? { ...saved, status: 'unknown' } : item));
  } catch (error) {
    throw wasUnknown ? purgeRecoveryStorageError() : error;
  }
  accountPurgeRequests.add(saved.operationId);
  try {
    const response = await fetchWithDeadline('/users/admin/users/' + saved.targetUserId + '/purge', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmation_email: saved.email, preview_fingerprint: saved.fingerprint,
        operation_id: saved.operationId, acknowledge_irreversible: true }),
    });
    // This POST reads the receipt before looking up the target. It safely recovers an already deleted target.
    const result = await readApiResponse(response, 'Не удалось подтвердить результат удаления.');
    if (result?.ok !== true || result.operation_id !== saved.operationId) {
      throw new ApiResponseError('Не удалось подтвердить результат удаления.', 0, { outcomeUnknown: true });
    }
    saveAccountPurges(actorId, readAccountPurges(actorId).filter((item) => !samePurgeCommand(item, saved)));
    return result;
  } catch (error) {
    const authoritativeRefusal = ['PURGE_PREVIEW_STALE', 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE'].includes(error?.code);
    const knownRefusal = error instanceof ApiResponseError && error.status >= 400 && error.status < 500 &&
      !error.outcomeUnknown && (!wasUnknown || authoritativeRefusal);
    if (knownRefusal) {
      saveAccountPurges(actorId, readAccountPurges(actorId).filter((item) => !samePurgeCommand(item, saved)));
      throw error;
    }
    throw new ApiResponseError(accountPurgeErrorMessage(error, { unknown: true }), error?.status || 0,
      { code: error?.code || null, requestId: error?.requestId || null, outcomeUnknown: true });
  } finally {
    accountPurgeRequests.delete(saved.operationId);
  }
};

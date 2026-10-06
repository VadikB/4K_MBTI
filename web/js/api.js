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
  constructor(message, status) {
    super(message);
    this.name = 'ApiResponseError';
    this.status = status;
  }
}

export class StaleApiResponseError extends Error {
  constructor() {
    super('Ответ относится к устаревшей пользовательской сессии.');
    this.name = 'StaleApiResponseError';
  }
}

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
    if (data && typeof data === 'object' && 'detail' in data && data.detail) {
      throw new ApiResponseError(data.detail, response.status);
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
      throw new ApiResponseError(rawText.trim().slice(0, 240), response.status);
    }
    throw new ApiResponseError(fallbackMessage, response.status);
  }

  if (data === null) {
    throw new Error(fallbackMessage);
  }

  return data;
};

export const createOperationId = () =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : 'op-' + Date.now() + '-' + Math.random().toString(16).slice(2);

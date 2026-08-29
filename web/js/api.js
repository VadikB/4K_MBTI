let unauthorizedResponseHandler = null;
let unauthorizedRecovery = null;

export const registerUnauthorizedResponseHandler = (handler) => {
  unauthorizedResponseHandler = typeof handler === 'function' ? handler : null;
};

const notifyUnauthorizedResponse = () => {
  if (!unauthorizedResponseHandler || unauthorizedRecovery) {
    return;
  }
  unauthorizedRecovery = Promise.resolve()
    .then(() => unauthorizedResponseHandler())
    .catch((error) => {
      console.error('Failed to recover from an expired server session', error);
    })
    .finally(() => {
      unauthorizedRecovery = null;
    });
};

export class ApiResponseError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiResponseError';
    this.status = status;
  }
}

export const readApiResponse = async (response, fallbackMessage) => {
  const rawText = await response.text();
  let data = null;

  if (rawText) {
    try {
      data = JSON.parse(rawText);
    } catch (_error) {
      data = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      notifyUnauthorizedResponse();
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

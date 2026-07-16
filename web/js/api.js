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
    if (data && typeof data === 'object' && 'detail' in data && data.detail) {
      throw new Error(data.detail);
    }
    if (rawText && rawText.trim()) {
      const contentType = String(response.headers.get('content-type') || '').toLowerCase();
      const looksLikeHtml = contentType.includes('text/html') || /^\s*<(?:!doctype|html|head|body)\b/i.test(rawText);
      if (looksLikeHtml) {
        throw new Error(`${fallbackMessage} Сервер вернул ошибку ${response.status}. Попробуйте отправить еще раз.`);
      }
      throw new Error(rawText.trim().slice(0, 240));
    }
    throw new Error(fallbackMessage);
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

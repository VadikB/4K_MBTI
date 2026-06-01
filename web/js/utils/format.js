import { ADMIN_PHONE } from '../config.js';

export const buildInitials = (fullName) => {
  if (!fullName) {
    return 'A';
  }

  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
};

export const formatDateTimeLocalValue = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const pad = (num) => String(num).padStart(2, '0');
  return (
    date.getFullYear() +
    '-' +
    pad(date.getMonth() + 1) +
    '-' +
    pad(date.getDate()) +
    'T' +
    pad(date.getHours()) +
    ':' +
    pad(date.getMinutes())
  );
};

export const formatDateInputValue = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const pad = (num) => String(num).padStart(2, '0');
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
};

export const normalizeExpertAssessmentDateForApi = (value) => {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return null;
  }
  return normalized + 'T00:00:00';
};

export const getSignupFirstName = (fullName, fallback = 'Пользователь') => {
  const parts = String(fullName || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length >= 2) {
    return parts[1];
  }
  return parts[0] || fallback;
};

export const sanitizeDisplayRole = (value) => {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е');
  if (!normalized) {
    return '';
  }
  if (
    normalized === 'не изменений' ||
    normalized === 'нет изменений' ||
    normalized === 'изменений нет' ||
    normalized === 'без изменений' ||
    normalized.includes('ничего не измен')
  ) {
    return '';
  }
  return String(value).trim();
};

export const sanitizeDisplayMetaText = (value) => {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е');
  if (!normalized) {
    return '';
  }
  if (
    normalized === 'не изменений' ||
    normalized === 'нет изменений' ||
    normalized === 'нет измеенний' ||
    normalized === 'изменений нет' ||
    normalized === 'без изменений' ||
    normalized.includes('ничего не измен')
  ) {
    return '';
  }
  return String(value).trim();
};

export const isAdminUserPayload = (user, explicitFlag = false) => {
  if (explicitFlag) {
    return true;
  }
  const digits = String(user?.phone || '').replace(/\D/g, '');
  return digits === ADMIN_PHONE;
};

export const buildExistingUserAgentMessage = (user, fallbackMessage = '') => {
  const fallback = String(fallbackMessage || '').trim();
  const normalizedFallback = fallback.toLowerCase().replace(/ё/g, 'е');
  if (
    normalizedFallback.includes('нужно ли внести изменения') &&
    normalizedFallback.includes('если изменений нет')
  ) {
    return fallback;
  }

  if (!user) {
    return fallback;
  }

  const name = String(user.full_name || 'пользователь').trim();
  const position = sanitizeDisplayRole(user.job_description || '');
  const duties = sanitizeDisplayMetaText(user.raw_duties || '');
  let message = 'Пользователь найден: ' + name + '. ';

  if (position || duties) {
    message += 'Нужно ли внести изменения в должность и должностные обязанности? ';
    if (!position && !duties) {
      message += 'Если изменений нет, просто напишите, что профиль актуален или что ничего не изменилось. ';
    } else {
      message += 'Если изменений нет, просто напишите, что профиль актуален или что ничего не изменилось. ';
    }
    message += 'Если изменения есть, отправьте сначала актуальную должность.';
    return message;
  }

  return message + 'Продолжим актуализацию профиля.';
};

export const shouldOfferNoChangesQuickReply = (message) => {
  const normalized = String(message || '').toLowerCase();
  return (
    normalized.includes('если изменений нет') &&
    normalized.includes('профиль актуален') &&
    normalized.includes('ничего не изменилось')
  );
};

export const escapeHtml = (value) =>
  String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

export const highlightAdminInsightFigures = (value) => {
  const text = String(value || '');
  const figurePattern = /(^|[^\p{L}\p{N}])(\d+(?:[.,]\d+)?\s*%?)(?=$|[^\p{L}\p{N}])/gu;
  let result = '';
  let lastIndex = 0;
  let match;
  while ((match = figurePattern.exec(text)) !== null) {
    const prefix = match[1] || '';
    const figure = match[2] || '';
    const figureStart = match.index + prefix.length;
    result += escapeHtml(text.slice(lastIndex, figureStart));
    result += '<span class="admin-detail-figure-chip">' + escapeHtml(figure.trim()) + '</span>';
    lastIndex = figureStart + figure.length;
  }
  result += escapeHtml(text.slice(lastIndex));
  return result.replace(/\n/g, '<br>');
};

export const formatProfileDate = (value) => {
  if (!value) {
    return 'Без даты';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Без даты';
  }
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

export const formatAdminReportDate = (item) => {
  const value = item.finished_at || item.started_at;
  if (!value) {
    return 'Без даты';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Без даты';
  }
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

export const parseJsonArrayField = (value) => {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value;
  }
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
};

import { fetchWithDeadline, readApiResponse } from '../api.js';
import { appealReplyAttribution } from '../appeal-presentation.js';
import { state } from '../state.js';
import { showParticipantDialog } from './participant-dialog.js';

export const readParticipantAppeals = async (ownerId, signal) => {
  const response = await fetchWithDeadline(`/users/${encodeURIComponent(ownerId)}/acquaintance/issues`, {
    credentials: 'same-origin', signal,
  });
  const { items } = await readApiResponse(response, 'Не удалось загрузить обращения');
  return Array.isArray(items) ? items : [];
};

export const renderParticipantAppeals = (container, items) => {
  container.replaceChildren();
  for (const item of items) {
    const article = document.createElement('article');
    article.className = 'card participant-appeal';
    const title = document.createElement(item.reply_message ? 'h3' : 'p');
    title.textContent = item.reply_message ? 'Ответ по вашему обращению' :
      item.status === 'in_progress' ? 'В работе' :
        item.status === 'resolved' ? 'Обработано ранее' : 'Ожидает ответа';
    article.append(title);

    const assessment = document.createElement('p');
    assessment.className = 'participant-appeal-assessment';
    const name = item.assessment_display_name?.trim();
    if (name) {
      assessment.textContent = name;
      article.append(assessment);
    }
    if (item.reply_message) {
      const reply = document.createElement('p');
      reply.textContent = item.reply_message;
      article.append(appealReplyAttribution(item), reply);
    }

    const original = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Ваше обращение';
    original.append(summary);
    if (!name) {
      assessment.textContent = 'Связь с оценкой неизвестна';
      original.append(assessment);
    }
    const message = document.createElement('p');
    message.textContent = item.message || '';
    original.append(message);
    article.append(original);
    container.append(article);
  }
};

export const openParticipantReplies = async (trigger) => {
  const ownerId = state.pendingUser?.id;
  if (!ownerId) return;
  const epoch = state.identityEpoch;
  const screen = state.currentScreen;
  const body = document.createElement('div');
  body.className = 'participant-replies';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.textContent = 'Загружаем ответы…';
  body.append(status);
  const closed = showParticipantDialog(trigger, {
    title: 'Ответы на обращения', body, cancel: 'Вернуться к знакомству', describeContents: false,
  });
  if (!body.isConnected) return;
  const controller = new AbortController();
  const close = () => body.closest('dialog')?.close();
  window.addEventListener('agent4k:assessment-context-cleared', close);
  void closed.then(() => {
    window.removeEventListener('agent4k:assessment-context-cleared', close);
    controller.abort();
  });

  const current = () => body.closest('dialog')?.open && state.identityEpoch === epoch &&
    state.pendingUser?.id === ownerId && state.currentScreen === screen;
  try {
    const replies = (await readParticipantAppeals(ownerId, controller.signal)).filter(item => item.reply_message);
    if (!current()) return;
    if (replies.length) renderParticipantAppeals(body, replies);
    else status.textContent = 'Ответов пока нет.';
  } catch {
    if (current()) status.textContent = 'Не удалось загрузить ответы. Откройте обращения ещё раз.';
  }
};

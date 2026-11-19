import { readApiResponse } from '../../api.js';
import { state } from '../../state.js';

const labels = { open: 'Новое', in_progress: 'В работе', answered: 'Ответ отправлен', resolved: 'Обработано ранее' };

export const mountMemberAppeals = (dialog, organizationId, userId) => {
  const epoch = state.identityEpoch;
  const actor = state.pendingUser?.id;
  const base = `/users/admin/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(userId)}/issues`;
  const section = document.createElement('section');
  section.className = 'admin-member-appeals';
  const heading = document.createElement('h4'); heading.textContent = 'Обращения участника';
  const body = document.createElement('div'); body.setAttribute('aria-live', 'polite');
  section.append(heading, body);
  dialog.querySelector('[data-card-actions]')?.before(section);
  const current = () => dialog.isConnected && epoch === state.identityEpoch && actor === state.pendingUser?.id;
  const request = async (url, options) => readApiResponse(await fetch(url, {
    credentials: 'same-origin', ...options,
    headers: options?.body ? { 'Content-Type': 'application/json' } : undefined,
  }), 'Не удалось проверить обращение');
  const drafts = new Map();
  const read = async () => {
    const data = await request(base);
    if (!current()) return [];
    return Array.isArray(data.items) ? data.items : [];
  };
  const render = (items) => {
    if (!current()) return;
    for (const input of body.querySelectorAll('textarea[data-issue-id]')) drafts.set(Number(input.dataset.issueId), input.value);
    body.replaceChildren();
    if (!items.length) { const empty = document.createElement('p'); empty.textContent = 'Обращений пока нет.'; body.append(empty); return; }
    for (const issue of items) {
      const card = document.createElement('article'); card.className = 'admin-member-appeal';
      const status = document.createElement('strong'); status.textContent = labels[issue.status] || issue.status;
      const context = document.createElement('p');
      context.textContent = issue.assignment_ref
        ? `Назначение: ${issue.assignment_ref} · № ${issue.assignment_id ?? 'неизвестен'} · редакция ${issue.questionnaire_revision_id ?? 'неизвестна'}`
        : 'Связь с назначением неизвестна';
      const message = document.createElement('p'); message.textContent = issue.message;
      card.append(status, context, message);
      if (issue.reply_message) {
        const reply = document.createElement('p'); reply.textContent = `Ответ: ${issue.reply_message}`; card.append(reply);
      } else if (['open', 'in_progress'].includes(issue.status)) {
        const feedback = document.createElement('p'); feedback.setAttribute('role', 'status');
        if (!issue.claimed_by_user_id || Number(issue.claimed_by_user_id) !== Number(actor)) {
          const claim = document.createElement('button'); claim.type = 'button'; claim.className = 'ghost-button compact-ghost'; claim.textContent = 'Взять в работу';
          claim.disabled = Boolean(issue.claimed_by_user_id && issue.claimed_by_active_admin);
          if (claim.disabled) feedback.textContent = 'В работе у другого администратора';
          claim.onclick = async () => {
            claim.disabled = true;
            try { await request(`${base}/${issue.id}/claim`, { method: 'POST' }); render(await read()); }
            catch (error) { try { render(await read()); } catch { feedback.textContent = error.message; claim.disabled = false; } }
          };
          card.append(claim);
        } else {
          const input = document.createElement('textarea'); input.dataset.issueId = issue.id;
          input.maxLength = 4000; input.placeholder = 'Ответ участнику'; input.value = drafts.get(Number(issue.id)) || '';
          const send = document.createElement('button'); send.type = 'button'; send.className = 'primary-button compact-primary'; send.textContent = 'Отправить ответ';
          send.onclick = async () => {
            const text = input.value.trim(); if (!text) { feedback.textContent = 'Введите ответ'; input.focus(); return; }
            send.disabled = true;
            try { await request(`${base}/${issue.id}/reply`, { method: 'POST', body: JSON.stringify({ message: text }) }); drafts.delete(Number(issue.id)); render(await read()); }
            catch (error) {
              try {
                const latest = await read();
                if (latest.find(item => Number(item.id) === Number(issue.id))?.reply_message === text) {
                  drafts.delete(Number(issue.id)); render(latest); return;
                }
              } catch { /* Keep the typed reply until a confirmed read. */ }
              feedback.textContent = `${error.message}. Текст ответа сохранён в форме.`; send.disabled = false;
            }
          };
          card.append(input, send);
        }
        card.append(feedback);
      }
      body.append(card);
    }
  };
  body.textContent = 'Загружаем обращения…';
  void read().then(render).catch(error => { if (current()) body.textContent = error.message; });
};

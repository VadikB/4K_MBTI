import { fetchWithDeadline, readApiResponse } from '../../api.js';
import { appealReplyAttribution } from '../../appeal-presentation.js';
import { state } from '../../state.js';

const labels = { open: 'Новое', in_progress: 'В работе', answered: 'Ответ отправлен', resolved: 'Обработано ранее' };

export const mountMemberAppeals = (dialog, organizationId, userId, { focus = false } = {}) => {
  const anchor = dialog.querySelector('[data-card-actions]');
  if (!anchor) return;
  const epoch = state.identityEpoch;
  const actor = state.pendingUser?.id;
  const base = `/users/admin/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(userId)}/issues`;
  const section = document.createElement('section');
  section.className = 'admin-member-appeals';
  const heading = document.createElement('h4');
  heading.id = 'admin-member-appeals-title';
  heading.textContent = 'Обращения участника';
  heading.tabIndex = -1;
  section.setAttribute('aria-labelledby', heading.id);
  const body = document.createElement('div');
  body.className = 'admin-member-appeals-list';
  section.append(heading, body);
  anchor.before(section);
  if (focus) heading.focus();

  const current = () => dialog.open && section.isConnected && epoch === state.identityEpoch && actor === state.pendingUser?.id;
  const request = async (url, options) => readApiResponse(await fetchWithDeadline(url, {
    credentials: 'same-origin', ...options,
    headers: options?.body ? { 'Content-Type': 'application/json' } : undefined,
  }), 'Не удалось загрузить обращения');
  const read = async () => {
    const { items } = await request(base);
    return Array.isArray(items) ? items : [];
  };

  const isClaimedHere = (issue) => issue.status === 'in_progress' &&
    issue.claimed_by_user_id != null && Number(issue.claimed_by_user_id) === Number(actor);
  const canClaim = (issue) => ['open', 'in_progress'].includes(issue.status) &&
    !isClaimedHere(issue) && !issue.claimed_by_active_admin;

  const renderIssue = (issue, draft = '') => {
    const card = document.createElement('article');
    card.className = 'admin-member-appeal';
    const status = document.createElement('h5');
    status.className = 'admin-member-appeal-state';
    status.tabIndex = -1;
    status.textContent = labels[issue.status] || 'Статус уточняется';
    const message = document.createElement('blockquote');
    message.textContent = issue.message;
    card.append(status, message);

    const feedback = document.createElement('p');
    feedback.className = 'admin-member-appeal-feedback';
    feedback.setAttribute('role', 'status');

    const change = async (action, button, input) => {
      if (!current() || button.disabled) return;
      const text = input?.value.trim();
      if (input && !text) {
        feedback.textContent = 'Введите ответ.';
        input.focus();
        return;
      }
      const hadFocus = card.contains(document.activeElement);
      button.disabled = true;
      if (input) input.readOnly = true;
      feedback.textContent = input ? 'Отправляем ответ…' : 'Берём обращение в работу…';
      try {
        await request(`${base}/${encodeURIComponent(issue.id)}/${action}`, {
          method: 'POST',
          body: input ? JSON.stringify({ message: text }) : undefined,
        });
      } catch { /* The command may have committed before its response was lost. */ }
      if (!current()) return;
      let latest;
      try {
        latest = (await read()).find(item => item.id === issue.id);
      } catch { /* Keep the form until a read confirms the saved state. */ }
      if (!current()) return;

      if (latest) {
        const saved = input && latest.reply_message === text && Number(latest.reply_author_user_id) === Number(actor);
        const retainedDraft = input && !saved ? input.value : '';
        const next = renderIssue(latest, retainedDraft);
        const followup = retainedDraft
          ? 'Отправка вашего ответа не подтверждена. Текст ответа сохранён в форме.'
          : action === 'claim' && canClaim(latest) ? 'Не удалось взять обращение в работу. Повторите попытку.' : '';
        const focused = document.activeElement;
        card.replaceWith(next);
        if (followup) next.querySelector('.admin-member-appeal-feedback').textContent = followup;
        if (card.contains(focused) || (hadFocus && (focused === document.body || focused === dialog))) {
          (next.querySelector('textarea:not([readonly])') || next.querySelector('h5')).focus();
        }
        return;
      }
      feedback.textContent = input
        ? 'Не удалось проверить отправку. Текст ответа сохранён в форме.'
        : 'Не удалось проверить состояние обращения. Повторите попытку.';
      if (input) input.readOnly = false;
      button.disabled = false;
      if (hadFocus && document.activeElement === document.body) button.focus();
    };

    const mayReply = isClaimedHere(issue) && !issue.reply_message;
    if (issue.reply_message) {
      const replyTitle = document.createElement('h6');
      replyTitle.textContent = 'Ответ участнику';
      const reply = document.createElement('p');
      reply.className = 'admin-member-appeal-reply';
      reply.textContent = issue.reply_message;
      card.append(replyTitle, appealReplyAttribution(issue), reply);
    } else if (canClaim(issue)) {
      const claim = document.createElement('button');
      claim.type = 'button';
      claim.className = 'primary-button compact-primary';
      claim.textContent = 'Взять в работу';
      claim.onclick = () => void change('claim', claim);
      card.append(claim);
    } else if (issue.status === 'in_progress' && !mayReply) {
      const owner = document.createElement('p');
      owner.textContent = 'В работе у другого администратора';
      card.append(owner);
    }

    if (mayReply || draft) {
      const input = document.createElement('textarea');
      input.id = 'admin-member-appeal-reply-' + issue.id;
      input.maxLength = 4000;
      input.rows = 3;
      input.value = draft;
      input.readOnly = !mayReply;
      const label = document.createElement('label');
      label.htmlFor = input.id;
      label.textContent = mayReply ? 'Ответ участнику' : 'Черновик ответа';
      card.append(label, input);
      if (mayReply) {
        const send = document.createElement('button');
        send.type = 'button';
        send.className = 'primary-button compact-primary';
        send.textContent = 'Отправить ответ';
        send.onclick = () => void change('reply', send, input);
        card.append(send);
      }
    }
    card.append(feedback);

    if (issue.assignment_id == null || issue.questionnaire_revision_id == null) {
      const uncertainty = document.createElement('p');
      uncertainty.className = 'admin-member-appeal-context';
      uncertainty.textContent = issue.assignment_id == null
        ? 'Связь с назначением неизвестна' : 'Редакция анкеты неизвестна';
      card.append(uncertainty);
    }
    const facts = [
      issue.assignment_ref && `Код оценки: ${issue.assignment_ref}`,
      issue.assignment_id != null && `Назначение № ${issue.assignment_id}`,
      issue.questionnaire_revision_id != null && `Редакция анкеты № ${issue.questionnaire_revision_id}`,
    ].filter(Boolean);
    if (facts.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Сведения о назначении';
      details.append(summary);
      facts.forEach(fact => {
        const field = document.createElement('p');
        field.textContent = fact;
        details.append(field);
      });
      card.append(details);
    }
    return card;
  };

  const loading = document.createElement('p');
  loading.setAttribute('role', 'status');
  loading.textContent = 'Загружаем обращения…';
  body.append(loading);
  void read().then(items => {
    if (!current()) return;
    if (items.length) body.replaceChildren(...items.map(issue => renderIssue(issue)));
    else loading.textContent = 'Обращений пока нет.';
  }).catch(error => { if (current()) loading.textContent = error.message; });
};

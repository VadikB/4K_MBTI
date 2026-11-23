import { invitationMessage, invitationLinkMessage } from './invitation-presentation.js';
const attemptKey = item => String(item?.operation_id || '') + ':' + String(item?.invitation_id || '');
const time = value => value ? new Date(value).toLocaleString('ru-RU', { timeZoneName: 'short' }) : 'Не сохранено';
export const mountInvitationDetails = (dialog, initial, refresh = null, { unboundRegistration = '' } = {}) => {
  const details = document.createElement('details');
  details.className = 'admin-invitation-details';
  details.innerHTML = '<summary>Сведения о приглашении</summary><dl><dt>ID попытки</dt><dd data-invite-id></dd><dt data-invite-case-label>Номер случая</dt><dd data-invite-case></dd><dt>Время</dt><dd data-invite-time></dd><dt>Диагностика</dt><dd data-invite-diagnostic></dd></dl><p data-invite-read-status role="status"></p><button type="button" data-invite-copy>Копировать сведения</button>';
  let current = initial;
  const render = item => {
    // Read the live open state at response time: toggles during I/O are authoritative.
    if (attemptKey(current) !== attemptKey(item)) details.open = false;
    current = item;
    details.querySelector('[data-invite-id]').textContent = item.operation_id || (item.invitation_id ? 'Запись ' + item.invitation_id : 'Попытка не сохранена');
    const caseNumber = details.querySelector('[data-invite-case]');
    caseNumber.textContent = item.invitation_id ? 'INV-' + item.invitation_id : '';
    caseNumber.hidden = details.querySelector('[data-invite-case-label]').hidden = !item.invitation_id;
    details.querySelector('[data-invite-time]').textContent = time(item.created_at);
    details.querySelector('[data-invite-diagnostic]').textContent = invitationMessage(item);
  };
  render(initial);
  details.querySelector('[data-invite-copy]').addEventListener('click', async () => {
    const label = details.querySelector('[data-invite-read-status]');
    try {
      await navigator.clipboard.writeText([details.querySelector('[data-invite-id]').textContent,
        details.querySelector('[data-invite-case]').textContent, time(current.created_at), invitationMessage(current)].filter(Boolean).join('\n'));
      label.textContent = 'Сведения скопированы';
    } catch { label.textContent = 'Не удалось скопировать сведения. Выделите текст вручную'; }
  });
  if (refresh) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = 'Обновить сведения';
    button.addEventListener('click', async () => {
      button.disabled = true;
      const label = details.querySelector('[data-invite-read-status]');
      label.textContent = 'Проверяем эту попытку';
      try {
        const result = await refresh(current);
        if (!details.isConnected || !result) return;
        render(result);
        label.textContent = '';
        const mail = dialog.querySelector('[data-card-invitation]');
        if (mail) mail.textContent = invitationMessage(result) + ' · ' + invitationLinkMessage(result.link_status, result.expires_at ? time(result.expires_at) : '');
      } catch (error) {
        if (details.isConnected) label.textContent = error?.status === 404
          ? 'Результат этой попытки пока не найден' : 'Не удалось обновить сведения. Последний подтверждённый исход сохранён';
      } finally { if (details.isConnected) button.disabled = false; }
    });
    details.append(button);
  }
  dialog.querySelector('form').insertBefore(details, dialog.querySelector('[data-card-actions]'));
  if (unboundRegistration) {
    const saved = document.createElement('section');
    saved.setAttribute('data-card-unbound-invitation', '');
    saved.innerHTML = '<p>Не удалось подтвердить, к какой оценке относится отправка</p>' +
      '<dl><dt>Отправка</dt><dd></dd><dt>Ссылка</dt><dd></dd><dt>Регистрация</dt><dd></dd></dl>';
    const [delivery, link, registration] = saved.querySelectorAll('dd');
    delivery.textContent = invitationMessage(initial);
    link.textContent = invitationLinkMessage(initial.link_status, initial.expires_at ? time(initial.expires_at) : '');
    registration.textContent = unboundRegistration;
    details.before(saved);
  }
  return { render, details };
};

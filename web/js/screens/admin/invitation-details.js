import { invitationMessage, invitationLinkMessage } from './invitation-presentation.js';
const attemptKey = item => String(item?.operation_id || '') + ':' + String(item?.invitation_id || '');
const time = value => value ? new Date(value).toLocaleString('ru-RU', { timeZoneName: 'short' }) : 'Не сохранено';
export const mountInvitationDetails = (dialog, initial, refresh = null) => {
  const details = document.createElement('details');
  details.className = 'admin-invitation-details';
  details.innerHTML = '<summary>Сведения о приглашении</summary><dl><dt>ID попытки</dt><dd data-invite-id></dd><dt>Время</dt><dd data-invite-time></dd><dt>Диагностика</dt><dd data-invite-diagnostic></dd></dl><p data-invite-read-status role="status"></p><button type="button" data-invite-copy>Копировать сведения</button>';
  let current = initial;
  const render = item => {
    // Read the live open state at response time: toggles during I/O are authoritative.
    if (attemptKey(current) !== attemptKey(item)) details.open = false;
    current = item;
    details.querySelector('[data-invite-id]').textContent = item.operation_id || (item.invitation_id ? 'Запись ' + item.invitation_id : 'Попытка не сохранена');
    details.querySelector('[data-invite-time]').textContent = time(item.created_at);
    details.querySelector('[data-invite-diagnostic]').textContent = invitationMessage(item);
  };
  render(initial);
  details.querySelector('[data-invite-copy]').addEventListener('click', async () => {
    const label = details.querySelector('[data-invite-read-status]');
    try {
      await navigator.clipboard.writeText([details.querySelector('[data-invite-id]').textContent,
        time(current.created_at), invitationMessage(current)].join('\n'));
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
  return { render, details };
};

import { createOperationId, fetchWithDeadline, readApiResponse } from '../../api.js';
import { escapeHtml } from '../../utils/format.js';

const organizationUrl = (id) => '/users/admin/organizations/' + Number(id);
const request = async (url, options, message) => readApiResponse(await fetchWithDeadline(url, {
  credentials: 'same-origin', cache: 'no-store', ...options,
}), message);

const button = (label, action, classes = 'ghost-button compact-ghost', extra = '') =>
  '<button type="button" class="' + classes + '" data-history-action="' + action + '"' + extra + '>' + label + '</button>';
const events = {
  created: 'Создана организация',
  program_connected: 'Подключена программа',
  administrator_added: 'Добавлен администратор',
};
const eventDate = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'medium' });
const timeline = (entries) => {
  const rows = entries.filter((event) => Object.hasOwn(events, event.kind) &&
    event.occurred_at && Number.isFinite(Date.parse(event.occurred_at)));
  if (!rows.length) return '<p>Подтверждённых событий пока нет.</p>';
  return '<ol class="org-history-timeline">' + rows.map((event) =>
    '<li><time datetime="' + escapeHtml(event.occurred_at) + '">' + eventDate.format(new Date(event.occurred_at)) +
    '</time><div><strong>' + events[event.kind] + '</strong>' +
    (event.subject ? '<p>' + escapeHtml(event.subject) + '</p>' : '') +
    (event.actor ? '<p>Автор · ' + escapeHtml(event.actor) + '</p>' : '') + '</div></li>',
  ).join('') + '</ol>';
};

const readHistory = async (id) => {
  const result = await request(organizationUrl(id) + '/history', {}, 'Не удалось прочитать журнал организации.');
  if (result.organization_id !== id || typeof result.is_active !== 'boolean' || !Array.isArray(result.events)) {
    throw new Error('Сервер не подтвердил состояние организации.');
  }
  return result;
};

const lifecycleRequests = new Map();
const changeAvailability = async (id, active, isCurrent) => {
  let commandError = null;
  try {
    await request(organizationUrl(id) + (active ? '/restore' : ''),
      { method: active ? 'POST' : 'DELETE' }, 'Не удалось изменить доступность организации.');
  } catch (error) {
    commandError = error;
  }
  if (!isCurrent()) return null;
  if (commandError && commandError.status >= 400 && commandError.status < 500 && !commandError.outcomeUnknown) {
    throw commandError;
  }
  // The write endpoint returns a registry. The read below addresses the original organization.
  const history = await readHistory(id);
  return { history, expected: active };
};

const storagePrefix = (actorId) => 'agent4k.organizationPurge.' + actorId + '.';
const storageKey = (actorId, organizationId) => storagePrefix(actorId) + organizationId;
const purgeRequests = new Set();
const settledPurges = new Set();

const pendingPurge = (actorId, organizationId) => {
  const raw = localStorage.getItem(storageKey(actorId, organizationId));
  if (!raw) return null;
  const command = JSON.parse(raw);
  if (command.actorId !== actorId || command.organizationId !== organizationId ||
      !command.confirmation_code || !command.preview_fingerprint || !command.operation_id) {
    throw new Error('Не удалось прочитать ключ подтверждённой операции удаления.');
  }
  return settledPurges.has(command.operation_id) ? null : command;
};

export const pendingOrganizationPurges = (actorId) => {
  const prefix = storagePrefix(actorId);
  try {
    return Object.keys(localStorage).filter((key) => key.startsWith(prefix))
      .map((key) => pendingPurge(actorId, Number(key.slice(prefix.length)))).filter(Boolean);
  } catch {
    return [];
  }
};

const savePurge = (actorId, organizationId, code, fingerprint) => {
  if (pendingPurge(actorId, organizationId)) throw new Error('Сначала проверьте исход прежней операции удаления.');
  const command = {
    actorId, organizationId, confirmation_code: code, preview_fingerprint: fingerprint,
    operation_id: createOperationId(), acknowledge_irreversible: true,
  };
  const key = storageKey(actorId, organizationId);
  const serialized = JSON.stringify(command);
  localStorage.setItem(key, serialized);
  if (localStorage.getItem(key) !== serialized) throw new Error('Не удалось сохранить ключ операции. Удаление не отправлено.');
  return command;
};

const clearPurge = (command) => {
  settledPurges.add(command.operation_id);
  try {
    const key = storageKey(command.actorId, command.organizationId);
    if (JSON.parse(localStorage.getItem(key))?.operation_id === command.operation_id) localStorage.removeItem(key);
  } catch { /* Server evidence remains valid if browser storage cannot be cleared. */ }
};

const purgeResult = async (command, mode, isCurrent) => {
  const { organizationId: id, operation_id, preview_fingerprint, confirmation_code, acknowledge_irreversible } = command;
  if (!isCurrent() || purgeRequests.has(operation_id)) return null;
  purgeRequests.add(operation_id);
  try {
    if (mode !== 'read') {
      try {
        await request(organizationUrl(id) + '/purge', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation_id, preview_fingerprint, confirmation_code, acknowledge_irreversible }),
        }, 'Не удалось подтвердить удаление организации.');
      } catch (error) {
        if ((mode === 'send' && error.status >= 400 && error.status < 500 &&
          !error.outcomeUnknown && error.code !== 'PURGE_EXECUTION_FAILED') || error.code === 'PURGE_PREVIEW_STALE') {
          clearPurge(command);
          return { error: error.message };
        }
      }
    }
    if (!isCurrent()) return null;
    try {
      const receipt = await request(organizationUrl(id) + '/purge/operations/' + encodeURIComponent(operation_id) +
        '?' + new URLSearchParams({ preview_fingerprint }), {}, 'Не удалось прочитать квитанцию удаления.');
      if (receipt.ok !== true || receipt.organization_id !== id || receipt.operation_id !== operation_id) {
        throw new Error('Сервер вернул другую операцию.');
      }
      clearPurge(command);
      return { confirmed: true };
    } catch (error) {
      const missing = error.code === 'DELETION_RECEIPT_NOT_FOUND';
      return { missing, error: missing ? 'Квитанция пока отсутствует. Можно проверить снова или повторить ту же команду.'
        : 'Исход удаления пока неизвестен. Проверьте квитанцию той же операции.' };
    }
  } finally {
    purgeRequests.delete(operation_id);
  }
};

export function mountOrganizationPurgeRecovery(root, command, { isCurrent, onPurged, initialResult, onRefused, allowRetry }) {
  root.innerHTML = '<div class="org-history-actions">' +
    button('Проверить результат удаления', 'read') +
    button('Повторить ту же команду', 'retry', 'ghost-button compact-ghost', ' hidden') +
    '</div><p class="platform-org-note" role="status">Исход подтверждённого удаления пока неизвестен.</p>';
  const read = root.querySelector('[data-history-action="read"]');
  const retry = root.querySelector('[data-history-action="retry"]');
  const status = root.querySelector('[role="status"]');
  const showResult = (result) => {
    status.textContent = result.missing && !allowRetry
      ? 'Квитанция пока отсутствует. Повтор команды недоступен в этом контуре.' : result.error;
    retry.hidden = !allowRetry || !result.missing;
  };
  if (initialResult) showResult(initialResult);
  const run = async (mode) => {
    read.disabled = retry.disabled = true;
    status.textContent = 'Проверяем квитанцию…';
    const result = await purgeResult(command, mode, isCurrent);
    if (!result || !isCurrent()) return;
    if (result.confirmed) return onPurged(command.organizationId);
    showResult(result);
    try {
      if (!pendingPurge(command.actorId, command.organizationId)) {
        if (onRefused) return onRefused(result.error);
        read.hidden = retry.hidden = true;
        return;
      }
    } catch {
      status.textContent = 'Не удалось прочитать сохранённую операцию.';
    }
    read.disabled = retry.disabled = false;
    read.focus({ preventScroll: true });
  };
  read.addEventListener('click', () => void run('read'));
  retry.addEventListener('click', () => { if (allowRetry) void run('retry'); });
}

const accountEffect = (account) => {
  if (account.preserved_reason === 'current_account') return 'Текущий аккаунт защищён';
  if (account.preserved_reason === 'configured_account') return 'Аккаунт защищён настройками доступа';
  if (account.configured_access_will_be_revoked) return 'Аккаунт удаляется. Настроенные полномочия будут отозваны';
  return account.will_delete_account ? 'Аккаунт удаляется' : 'Аккаунт сохраняется для другой организации';
};

const previewContent = (organization, preview) => {
  const blocked = preview.execution_blockers?.length > 0;
  const tableRows = Object.entries(preview.tables).filter(([, count]) => count > 0);
  const accounts = preview.accounts;
  return '<h4 tabindex="-1" data-purge-preview-title>Состав полного удаления</h4><p>' +
    escapeHtml(organization.name) + ' · код ' + escapeHtml(organization.code) + '</p>' +
    '<p>Всего связанных записей · <strong>' + Number(preview.total_rows) + '</strong></p>' +
    '<dl class="org-purge-counts">' + tableRows.map(([name, count]) =>
      '<div><dt>' + escapeHtml(name) + '</dt><dd>' + Number(count) + '</dd></div>',
    ).join('') + '</dl><h5>Учётные записи</h5>' +
    (accounts.length ? '<ul class="org-purge-accounts">' + accounts.map((account) =>
      '<li><strong>' + escapeHtml(account.email) + '</strong><span>' + accountEffect(account) + '</span></li>',
    ).join('') + '</ul>' : '<p>Связанных аккаунтов нет.</p>') +
    (blocked ? '<p role="status">Удаление пока заблокировано защищёнными аккаунтами.</p>' : '') +
    (!blocked && preview.execution_available === true ?
      '<form data-org-purge-form><label>Код организации<input name="confirmation_code" required autocomplete="off"></label>' +
      '<label class="org-purge-ack"><input type="checkbox" name="acknowledge_irreversible" required>Подтверждаю полное удаление. Действие необратимо.</label>' +
      '<button type="submit" class="ghost-button compact-ghost danger">Удалить полностью</button></form>' : '') +
    '<p role="status" data-purge-feedback></p>' + button('Закрыть просмотр', 'close-preview');
};

export function mountOrganizationHistory(root, organization, context) {
  const { actorId, isCurrent, onAvailability, onPurged, purgePreviewAvailable, physicalPurgeAvailable } = context;
  const id = Number(organization.id);
  const lifecycleKey = actorId + ':' + id;
  let executionAvailable = physicalPurgeAvailable;
  const visible = () => root.isConnected && isCurrent();
  root.innerHTML = '<section class="platform-org-summary-panel" aria-labelledby="org-history-heading">' +
    '<h3 id="org-history-heading" tabindex="-1">Журнал организации</h3><div data-history-events></div></section>' +
    '<section class="platform-org-summary-panel" aria-labelledby="org-availability-heading">' +
    '<h3 id="org-availability-heading">Управление доступностью</h3>' +
    '<p data-availability-note></p><div class="org-history-actions" data-lifecycle-actions></div>' +
    '<p data-lifecycle-status class="platform-org-note" tabindex="-1" role="status"></p></section>' +
    '<section class="platform-org-summary-panel org-history-details" aria-labelledby="org-purge-heading">' +
    '<h3 id="org-purge-heading" tabindex="-1">Полное удаление организации</h3><p>' +
    escapeHtml(organization.name) + ' · код ' + escapeHtml(organization.code) + '</p>' +
    '<p>Связанные данные будут удалены без возможности восстановления.</p>' +
    '<p class="platform-org-note" role="status" data-execution-availability>' +
    (purgePreviewAvailable && physicalPurgeAvailable ? 'Доступность исполнения уточняется при просмотре состава.'
      : 'Команда полного удаления недоступна в этом контуре.') + '</p><div data-org-purge>' +
    (purgePreviewAvailable ? button('Посмотреть состав удаления', 'preview') : '<p>Состав удаления недоступен.</p>') +
    '</div></section>';
  const list = root.querySelector('[data-history-events]');
  const actions = root.querySelector('[data-lifecycle-actions]');
  const status = root.querySelector('[data-lifecycle-status]');
  const note = root.querySelector('[data-availability-note]');
  let active = null;
  const applyHistory = (history) => {
    if (!visible()) return;
    active = history.is_active;
    onAvailability(id, active);
    list.innerHTML = timeline(history.events);
    note.textContent = active ? 'Организация станет неактивной. Состав, назначения, отчёты и история сохранятся.'
      : 'Восстановление возвращает доступ в границах текущих ролей. Состав, назначения и отчёты сохранены.';
    actions.innerHTML = button(active ? 'Деактивировать организацию' : 'Восстановить организацию', 'confirm-lifecycle');
  };
  const check = async (pending, focus = false) => {
    actions.replaceChildren();
    status.textContent = pending ? 'Проверяем состояние после команды…' : 'Читаем состояние организации…';
    try {
      const result = pending ? await pending : { history: await readHistory(id) };
      if (!visible() || !result) return;
      applyHistory(result.history);
      status.textContent = result.expected === undefined ? '' : result.expected === active
        ? (active ? 'Организация восстановлена.' : 'Организация деактивирована.')
        : 'Сервер пока показывает прежнее состояние. Можно проверить состояние ещё раз.';
      if (result.expected !== undefined && result.expected !== active) {
        actions.insertAdjacentHTML('beforeend', button('Проверить состояние', 'read-history'));
      }
    } catch (error) {
      if (!visible()) return;
      status.textContent = pending ? 'Не удалось подтвердить состояние после команды. Проверьте текущее состояние.'
        : error.message;
      if (active === null) list.textContent = 'Журнал сейчас недоступен.';
      actions.innerHTML = button('Проверить состояние', 'read-history');
    }
    if (focus) (status.textContent ? status : actions.querySelector('button')).focus({ preventScroll: true });
  };
  const confirm = (trigger) => {
    const desired = !active;
    const verb = desired ? 'Восстановить' : 'Деактивировать';
    const dialog = document.createElement('dialog');
    dialog.className = 'admin-member-card-dialog org-lifecycle-dialog';
    dialog.setAttribute('aria-labelledby', 'org-lifecycle-title');
    dialog.innerHTML = '<form method="dialog"><h3 id="org-lifecycle-title">' + verb + ' организацию?</h3><p>' +
      escapeHtml(organization.name) + ' · ' + escapeHtml(organization.code) + '</p><p>Администраторов · ' +
      Number(organization.admins?.length || 0) + ', отчётов · ' + Number(organization.reports_count || 0) +
      '</p><p>' + note.textContent +
      '</p><div class="org-history-actions"><button class="ghost-button compact-ghost" value="cancel" autofocus>Отмена</button>' +
      '<button class="primary-button compact-primary" value="confirm">' + verb + '</button></div></form>';
    root.append(dialog);
    dialog.addEventListener('close', () => {
      dialog.remove();
      if (!visible()) return;
      if (dialog.returnValue !== 'confirm') return trigger.focus();
      if (lifecycleRequests.has(lifecycleKey)) return;
      const pending = changeAvailability(id, desired, isCurrent).finally(() => lifecycleRequests.delete(lifecycleKey));
      lifecycleRequests.set(lifecycleKey, pending);
      void check(pending, true);
    }, { once: true });
    dialog.showModal();
  };

  const purge = root.querySelector('[data-org-purge]');
  const showPreviewButton = (message = '', focus = false) => {
    purge.innerHTML = '<p role="status">' + escapeHtml(message) + '</p>' +
      button(message ? 'Обновить состав удаления' : 'Посмотреть состав удаления', 'preview');
    if (focus) purge.querySelector('button').focus();
  };
  const recover = (command, initialResult) => {
    mountOrganizationPurgeRecovery(purge, command, {
      isCurrent, onPurged, initialResult, allowRetry: executionAvailable && purgePreviewAvailable,
      onRefused: (message) => {
        if (purgePreviewAvailable) showPreviewButton(message, true);
        else purge.textContent = message;
      },
    });
  };
  if (purge) {
    try {
      const pending = pendingPurge(actorId, id);
      if (pending) recover(pending);
    } catch (error) {
      purge.textContent = error.message;
    }
  }
  const showPreview = async (trigger) => {
    trigger.disabled = true;
    try {
      const pending = pendingPurge(actorId, id);
      if (pending) return recover(pending);
      const preview = await request(organizationUrl(id) + '/purge-preview', {}, 'Не удалось получить состав удаления.');
      if (!visible()) return;
      if (preview.target_id !== id || preview.target_type !== 'organization' ||
          !preview.fingerprint || !preview.tables || !Array.isArray(preview.accounts) ||
          !Array.isArray(preview.execution_blockers)) throw new Error('Сервер не подтвердил состав для этой организации.');
      executionAvailable = preview.execution_available === true;
      root.querySelector('[data-execution-availability]').textContent = !executionAvailable
        ? 'Команда полного удаления недоступна в этом контуре.'
        : preview.execution_blockers.length ? 'Исполнение заблокировано.' : 'Команда полного удаления доступна.';
      purge.innerHTML = previewContent(organization, preview);
      purge.querySelector('[data-purge-preview-title]').focus();
      const form = purge.querySelector('form');
      form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!visible()) return;
        const code = form.elements.confirmation_code.value;
        const feedback = purge.querySelector('[data-purge-feedback]');
        if (code !== organization.code || !form.elements.acknowledge_irreversible.checked) {
          feedback.textContent = 'Введите точный код организации и подтвердите необратимость.';
          form.elements.confirmation_code.focus();
          return;
        }
        const submit = form.querySelector('button');
        submit.disabled = true;
        let command;
        try {
          command = savePurge(actorId, id, code, preview.fingerprint);
        } catch {
          feedback.textContent = 'Не удалось сохранить подтверждённую команду. Проверьте доступ к хранилищу и состояние удаления.';
          submit.disabled = false;
          return;
        }
        form.hidden = true;
        feedback.textContent = 'Отправляем подтверждённую команду и проверяем квитанцию…';
        const result = await purgeResult(command, 'send', isCurrent);
        if (!result || !isCurrent()) return;
        if (result.confirmed) return onPurged(id);
        if (!visible()) return;
        if (result.missing !== undefined) {
          recover(command, result);
          purge.querySelector('button').focus();
        } else {
          showPreviewButton(result.error, true);
        }
      });
    } catch (error) {
      if (visible()) showPreviewButton(error.message, true);
    }
  };
  root.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-history-action]');
    if (!trigger || !visible()) return;
    if (trigger.dataset.historyAction === 'confirm-lifecycle') confirm(trigger);
    if (trigger.dataset.historyAction === 'read-history') void check(lifecycleRequests.get(lifecycleKey), true);
    if (trigger.dataset.historyAction === 'preview') void showPreview(trigger);
    if (trigger.dataset.historyAction === 'close-preview') showPreviewButton('', true);
  });
  void check(lifecycleRequests.get(lifecycleKey));
}

import { fetchWithDeadline, readApiResponse } from '../../api.js';
import { escapeHtml } from '../../utils/format.js';
import { invitationLinkMessage } from './invitation-presentation.js';

const preparationReference = /^P4K-[A-F0-9]{24}$/;
const invitationReference = /^INV-[1-9][0-9]{0,18}$/;
const httpReference = /^(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/i;
const positiveInteger = /^[1-9][0-9]*$/;
const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow',
});
const states = {
  admission_denied: ['Следующая ситуация не допущена', 'Отказ допуска', 'error',
    'Материалы следующей ситуации не прошли обязательную проверку. Новое задание по этой попытке не подтверждено.'],
  failed: ['Подготовка следующей ситуации завершилась с ошибкой', 'Сбой подготовки', 'error',
    'Сохранён отказ подготовки следующей ситуации.'],
  waiting: ['Готовится следующая ситуация', 'Ожидание', 'pending',
    'Запрос на подготовку сохранён. Допуск следующей ситуации ещё не подтверждён.'],
  unconfirmed: ['Подготовка следующей ситуации', 'Исход не подтверждён', 'pending',
    'Актуального подтверждения исхода нет.'],
  result_confirmed: ['Следующая ситуация допущена', 'Результат подтверждён', 'success',
    'Сохранён допуск новой ситуации для исходного назначения. Открытие ситуации выполняется отдельным действием.'],
  invitation_unknown: ['Исход приглашения неизвестен', 'Исход неизвестен', 'pending',
    'Попытка сохранена. Приём письма почтовым сервисом пока не подтверждён.'],
  invitation_pending: ['Приглашение в очереди', 'Ожидание', 'pending',
    'Запись приглашения создана. Подтверждения отправки пока нет.'],
  invitation_accepted: ['Отправка приглашения подтверждена', 'Принято сервисом', 'success',
    'Почтовый сервис принял письмо по исходной попытке.'],
  invitation_failed: ['Приглашение не отправлено', 'Отказ отправки', 'error',
    'По исходной попытке сохранён подтверждённый отказ.'],
  invitation_not_attempted: ['Приглашение создано', 'Отправка не начата', 'pending',
    'Сохранена запись приглашения.'],
};

const date = (value) => value && Number.isFinite(Date.parse(value))
  ? dateFormatter.format(new Date(value)) + ' МСК' : 'Нет подтверждённых сведений';
const numberLabel = (value) => '#' + escapeHtml(value);
const isInvitation = (model) => model.kind === 'invitation';
const stateFor = (model) => isInvitation(model) ? 'invitation_' + model.outcome : model.state;
const presentation = (model) => states[stateFor(model)] || states.unconfirmed;

function workspaceUrl(fields = {}) {
  return '/?' + new URLSearchParams({ screen: 'admin-platform-problems', ...fields });
}

function organizationUrl(id) {
  return '/?' + new URLSearchParams({ screen: 'admin-organizations', org: id });
}

function statusBadge(state) {
  const [, label, tone] = states[state] || states.unconfirmed;
  return '<span class="support-badge is-' + tone + '">' + label + '</span>';
}

function definitions(rows) {
  return '<dl class="support-definitions">' + rows.map(([label, value]) =>
    '<div><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd></div>').join('') + '</dl>';
}

function button(label, action, primary = false) {
  return '<button type="button" data-support-action="' + action + '" class="support-button' +
    (primary ? ' support-primary' : '') + '">' + label + '</button>';
}

function queueHtml({ items, next_before: nextBefore }, queueFields, before, invitationQueue) {
  const rows = items.map((item) =>
    '<tr><td><a class="support-link support-row-title" href="' +
      escapeHtml(workspaceUrl({ ...queueFields, issue: item.reference })) + '">' +
      presentation(item)[0] + '</a><div class="support-muted">' +
      escapeHtml(item.reference) + '</div></td>' +
    '<td data-label="Организация">' + numberLabel(item.organization_id) + '</td>' +
    '<td data-label="Состояние">' + statusBadge(stateFor(item)) + '</td>' +
    '<td data-label="Наблюдение">' + escapeHtml(date(item.last_confirmed_at)) + '</td></tr>').join('');
  const paging = [
    before ? '<a class="support-link" href="' + escapeHtml(workspaceUrl(queueFields)) +
      '">К новым случаям</a>' : '',
    nextBefore ? '<a class="support-link" href="' + escapeHtml(workspaceUrl({
      ...queueFields, before: nextBefore,
    })) + '">Более ранние случаи</a>' : '',
  ].join('');
  return (rows ? '<table class="support-table"><thead><tr><th scope="col">Проблема</th>' +
    '<th scope="col">Организация</th><th scope="col">Состояние</th><th scope="col">Наблюдение</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>' :
    '<p class="support-empty">' + (invitationQueue ? 'Приглашений с неизвестным исходом нет.' :
      'Неразрешённых сбоев подготовки следующей ситуации нет.') + '</p>') +
    (paging ? '<nav class="support-actions" aria-label="Страницы очереди">' + paging + '</nav>' : '');
}

function invitationHtml(model, queueUrl, handoffUrl, stale, readFailure) {
  const [title, , , fact] = presentation(model);
  const link = invitationLinkMessage(model.link_status, date(model.expires_at));
  const history = [
    ['Создана попытка', date(model.started_at)],
    ...(model.sent_at ? [['Письмо принято сервисом', date(model.sent_at)]] : []),
    ...(model.used_at ? [['Ссылка использована', date(model.used_at)]] : []),
    ...(model.link_status === 'expired' ? [['Срок ссылки истёк', date(model.expires_at)]] : []),
  ];
  return '<a class="support-link" href="' + escapeHtml(queueUrl) + '">← К проблемам</a>' +
    '<header class="support-heading"><div><div class="support-muted">Организация ' + numberLabel(model.organization_id) +
    '</div><h1 id="platform-problems-title" tabindex="-1">' + title + '</h1>' +
    '<p>Проверка исходной попытки персонального приглашения.</p></div>' +
    statusBadge(stale ? 'invitation_unknown' : stateFor(model)) + '</header>' +
    '<div class="support-actions"><a class="support-button support-primary" data-support-view="handoff" href="' +
    escapeHtml(handoffUrl) + '">Подготовить передачу</a>' + button('Проверить отправку', 'check') + '</div>' +
    '<p class="support-notice" data-support-feedback role="status"></p>' +
    '<div class="support-grid"><section class="support-card"><h2>Наблюдаемое поведение</h2>' +
    definitions([
      ['Исход отправки', fact],
      ['Состояние ссылки', link],
      ['Время последнего сохранённого факта', date(model.last_confirmed_at)],
      ['Время последнего успешного чтения', date(model.read_at)],
      ['Доступное действие', 'Проверить отправку по той же записи.'],
    ]) + '</section><section class="support-card"><h2>Сведения для поиска</h2>' +
    definitions([
      ['Номер попытки приглашения', model.reference],
      ['Назначение', model.assignment_ref || 'См. сохранённую запись'],
      ['Источник состояния', model.source],
      ['Категория исхода', model.reason_code],
      ...(readFailure?.status ? [['Ошибка запроса чтения', 'HTTP ' + readFailure.status]] : []),
      ...(readFailure?.code ? [['Код обращения · запрос чтения', readFailure.code]] : []),
    ]) + '</section><section class="support-card"><h2>Что видят в продукте</h2>' +
    definitions([
      ['Администратор организации', 'Автор может проверить исход исходной попытки в карточке участника.'],
      ['Ссылка участника', link],
    ]) + '</section><section class="support-card"><h2>Ход операции</h2>' + definitions(history) +
    '<a class="support-button" href="' + escapeHtml(organizationUrl(model.organization_id)) + '">К организации</a>' +
    '</section></div>';
}

function problemHtml(model, queueUrl, handoffUrl, stale) {
  const [title, , , fact] = states[model.state] || states.unconfirmed;
  const observed = model.stage_label || 'Этап не подтверждён';
  const previous = Number.isInteger(model.previous_position) && model.previous_position > 0
    ? 'Ситуация ' + model.previous_position + ' завершена. ' : '';
  const elapsed = [
    ['Запрос сохранён', date(model.started_at)],
    ...(model.stage_at ? [[observed, date(model.stage_at)]] : []),
    [model.result_confirmed_at ? 'Допуск подтверждён' : 'Последний подтверждённый факт',
      date(model.result_confirmed_at || model.last_confirmed_at)],
  ];
  return '<a class="support-link" href="' + escapeHtml(queueUrl) + '">← К проблемам</a>' +
    '<header class="support-heading"><div><div class="support-muted">Организация ' + numberLabel(model.organization_id) +
    '</div><h1 id="platform-problems-title" tabindex="-1">' + title + '</h1>' +
    '<p>Подготовка следующей ситуации в назначении ' + numberLabel(model.assignment_id) + '.</p></div>' +
    statusBadge(stale ? 'unconfirmed' : model.state) + '</header>' +
    '<div class="support-actions"><a class="support-button support-primary" data-support-view="handoff" href="' +
    escapeHtml(handoffUrl) + '">Подготовить передачу</a>' + button('Проверить состояние', 'check') + '</div>' +
    '<p class="support-notice" data-support-feedback role="status"></p>' +
    '<div class="support-grid"><section class="support-card"><h2>Наблюдаемое поведение</h2>' +
    definitions([
      ['Последний подтверждённый факт', model.state === 'unconfirmed' ? observed : previous + fact],
      ['Ожидаемое поведение', 'После допуска следующую ситуацию можно открыть отдельно.'],
      ['Время подтверждённого факта', date(model.last_confirmed_at)],
      ['Время последнего успешного чтения', date(model.read_at)],
      ['Доступное действие', 'Проверить состояние той же подготовки.'],
    ]) + '</section><section class="support-card"><h2>Сведения для поиска</h2>' +
    definitions([
      ['Номер подготовки и номер случая', model.reference],
      ['Поколение назначения', '#' + model.assignment_id],
      ['Последний этап', observed],
      ['Источник', model.stage_source ? model.source + ' · ' + model.stage_source : model.source],
      ...(model.failure_class ? [['Класс отказа', model.failure_class]] : []),
      ...(model.result_source ? [['Источник подтверждения допуска', model.result_source]] : []),
    ]) + '<p class="support-muted">Инженерный поиск принимает этот номер подготовки.</p></section>' +
    '<section class="support-card"><h2>Что видят в продукте</h2>' +
    definitions([
      ['Участник', model.state === 'admission_denied'
        ? 'Материалы следующей ситуации не прошли обязательную проверку. В подробностях доступен номер подготовки.'
        : 'Номер подготовки в подробностях состояния оценки.'],
      ['Администратор организации', 'При сбое карточка участника показывает номер случая и действие «Проверить состояние».'],
    ]) + '</section><section class="support-card"><h2>Ход операции</h2>' +
    definitions(elapsed) + '<a class="support-button" href="' +
    escapeHtml(organizationUrl(model.organization_id)) + '">К организации</a></section></div>';
}

function handoffHtml(model, problemUrl, packet) {
  return '<a class="support-link" data-support-view="problem" href="' + escapeHtml(problemUrl) + '">← К карточке проблемы</a>' +
    '<header class="support-heading"><div><div class="support-muted">Организация ' + numberLabel(model.organization_id) +
    '</div><h1 id="platform-problems-title" tabindex="-1">Передача разработчику</h1>' +
    '<p>' + presentation(model)[0] + '</p></div></header>' +
    '<p class="support-notice" data-support-feedback role="status"></p>' +
    '<div class="support-grid"><section class="support-card"><h2>Обезличенные сведения</h2>' +
    '<p>Скопируйте текст и передайте его через рабочий канал команды.</p>' +
    '<div class="support-actions">' + button('Скопировать сведения', 'copy', true) + '</div>' +
    '<p class="support-copy-status" data-support-copy-status role="status"></p>' +
    '<pre class="support-packet" tabindex="0" aria-label="Текст передачи">' + escapeHtml(packet) + '</pre></section>' +
    '<section class="support-card"><h2>Порядок разбора</h2><p>Разработчик ищет исходную попытку по ' +
    (isInvitation(model) ? 'номеру приглашения и организации' : 'номеру подготовки') +
    ' в закрытой диагностике. Текущий статус можно проверить в карточке этого случая.</p></section></div>';
}

export function mountPreparationProblems(root, isCurrent) {
  const params = new URLSearchParams(window.location.search);
  const reference = (params.get('issue') || '').trim().toUpperCase();
  const positive = (key) => {
    const value = params.get(key) || '';
    return positiveInteger.test(value) && Number.isSafeInteger(Number(value)) ? value : '';
  };
  const organization = positive('org');
  const before = positive('before');
  const invitationQueue = invitationReference.test(reference) || params.get('kind') === 'invitation';
  const invitationCase = invitationReference.test(reference);
  const endpoint = '/users/admin/support/' + (invitationCase || (!preparationReference.test(reference) && invitationQueue)
    ? 'invitations' : 'preparation');
  const queueFields = { ...(organization ? { org: organization } : {}), ...(invitationQueue ? { kind: 'invitation' } : {}) };
  const checkLabel = invitationCase ? 'Проверить отправку' : 'Проверить состояние';
  const activeTitle = invitationCase ? 'Проверка приглашения' : 'Подготовка следующей ситуации';
  const queueUrl = workspaceUrl(queueFields);
  const problemUrl = workspaceUrl({ ...queueFields, issue: reference });
  const handoffUrl = workspaceUrl({ ...queueFields, issue: reference, view: 'handoff' });
  const content = document.createElement('div');
  root.replaceChildren(content);
  const active = () => root.contains(content) && isCurrent();
  let view = params.get('view') === 'handoff' ? 'handoff' : 'problem';
  let model = null;
  let stale = false;
  let pending = false;
  let readFailure = null;

  const packet = () => model.handoff_text + (invitationCase && readFailure?.code
    ? '\nКод обращения (запрос чтения): ' + readFailure.code : '');

  const feedback = (message) => {
    const status = content.querySelector('[data-support-feedback]');
    if (status) status.textContent = message;
  };
  const renderProblem = (message = '') => {
    content.innerHTML = view === 'handoff' ? handoffHtml(model, problemUrl, packet()) :
      invitationCase ? invitationHtml(model, queueUrl, handoffUrl, stale, readFailure) :
        problemHtml(model, queueUrl, handoffUrl, stale);
    feedback(message || (stale ? 'Не удалось обновить состояние. Показан последний подтверждённый факт.' :
      model.state === 'unconfirmed' ? 'Актуального сигнала о ходе подготовки нет.' : ''));
  };
  const readProblem = async (trigger) => {
    if (pending) return;
    pending = true;
    const refocus = document.activeElement === trigger;
    if (trigger) trigger.setAttribute('aria-disabled', 'true');
    feedback('Проверяем состояние…');
    try {
      const candidate = await readApiResponse(await fetchWithDeadline(endpoint + '/' + encodeURIComponent(reference),
        { credentials: 'same-origin', cache: 'no-store' }, 10000), 'Не удалось проверить состояние.');
      if (!active()) return;
      if (candidate?.reference !== reference || !candidate.handoff_text) throw new Error('Invalid preparation response');
      model = candidate;
      stale = false;
      renderProblem(trigger ? 'Состояние исходной операции обновлено.' : '');
    } catch (error) {
      if (!active()) return;
      if ([401, 403, 404].includes(error?.status)) model = null;
      if (invitationCase) readFailure = {
        status: Number.isInteger(error?.status) && error.status >= 400 && error.status <= 599 ? error.status : null,
        code: httpReference.test(error?.requestId || '') ? error.requestId : null,
      };
      stale = true;
      if (model) renderProblem();
      else {
        const message = error?.status === 404 ? 'Случай с таким номером не найден.' :
          [401, 403].includes(error?.status) ? 'Доступ к случаю недоступен.' : 'Не удалось прочитать состояние.';
        content.innerHTML = '<a class="support-link" href="' + escapeHtml(queueUrl) + '">← К проблемам</a>' +
          '<h1 id="platform-problems-title" tabindex="-1">' + activeTitle + '</h1>' +
          '<p class="support-notice" role="status">' + message +
          (readFailure?.code ? ' Код обращения: ' + escapeHtml(readFailure.code) : '') + '</p>' +
          ([401, 403, 404].includes(error?.status) ? '' : button(checkLabel, 'check'));
      }
    } finally {
      pending = false;
      if (refocus && active() && (document.activeElement === trigger || document.activeElement === document.body)) {
        (content.querySelector('[data-support-action="check"]') || content.querySelector('h1'))?.focus({ preventScroll: true });
      }
    }
  };

  const readQueue = async () => {
    const target = content.querySelector('[data-support-list]');
    const filters = new URLSearchParams();
    if (organization) filters.set('organization_id', organization);
    if (before) filters.set('before', before);
    target.innerHTML = '<p class="support-empty" role="status">Загружаем проблемы…</p>';
    try {
      const response = await fetchWithDeadline(endpoint + (filters.size ? '?' + filters : ''),
        { credentials: 'same-origin', cache: 'no-store' }, 10000);
      const data = await readApiResponse(response, 'Не удалось загрузить проблемы.');
      if (!active()) return;
      if (!Array.isArray(data?.items)) throw new Error('Invalid preparation list');
      target.innerHTML = queueHtml(data, queueFields, before, invitationQueue);
    } catch (error) {
      if (!active()) return;
      const denied = [401, 403].includes(error?.status);
      target.innerHTML = '<p class="support-notice" role="status">' +
        (denied ? 'Доступ к очереди недоступен.' : 'Не удалось загрузить проблемы.') + '</p>' +
        (denied ? '' : button('Повторить чтение', 'queue'));
    }
  };

  content.addEventListener('click', async (event) => {
    const link = event.target.closest('[data-support-view]');
    if (link && model && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      view = link.dataset.supportView;
      window.history.pushState({}, '', link.href);
      renderProblem();
      content.querySelector('h1').focus();
      return;
    }
    const control = event.target.closest('[data-support-action]');
    if (control?.dataset.supportAction === 'check') void readProblem(control);
    if (control?.dataset.supportAction === 'queue') void readQueue();
    if (control?.dataset.supportAction === 'copy' && model) {
      const status = content.querySelector('[data-support-copy-status]');
      try {
        await navigator.clipboard.writeText(packet());
        status.textContent = 'Сведения скопированы.';
      } catch {
        status.textContent = 'Не удалось скопировать автоматически. Выделите текст и скопируйте его вручную.';
      }
    }
  });

  if (preparationReference.test(reference) || invitationCase) {
    content.innerHTML = '<h1 id="platform-problems-title">' + activeTitle + '</h1>' +
      '<p class="support-notice" data-support-feedback role="status"></p>';
    void readProblem();
    return;
  }

  const scope = organization ? { org: organization } : {};
  const queueLink = (label, invitation) => '<a class="support-link" href="' +
    escapeHtml(workspaceUrl(invitation ? { ...scope, kind: 'invitation' } : scope)) + '"' +
    (invitation === invitationQueue ? ' aria-current="page"' : '') + '>' + label + '</a>';
  content.innerHTML = '<header class="support-heading"><div><h1 id="platform-problems-title">Проблемы</h1>' +
    '<p>Найдите случай по организации, номеру подготовки или приглашения.</p></div></header>' +
    '<nav class="support-actions support-problem-types" aria-label="Типы проблем">' +
    queueLink('Подготовка ситуаций', false) + queueLink('Приглашения', true) + '</nav>' +
    '<section class="support-card"><form method="get" action="/" class="support-filter">' +
    '<input type="hidden" name="screen" value="admin-platform-problems">' +
    (invitationQueue ? '<input type="hidden" name="kind" value="invitation">' : '') +
    '<label>Поиск<input type="search" name="issue" ' +
    'placeholder="P4K-… или INV-…" title="Номер подготовки или приглашения" autocomplete="off"></label>' +
    '<label>Организация<input type="text" name="org" inputmode="numeric" pattern="[1-9][0-9]*" ' +
    'placeholder="Номер организации" value="' + escapeHtml(organization) + '"></label>' +
    '<button type="submit" class="support-button">Найти</button></form>' +
    (reference ? '<p class="support-notice" role="status">Введите номер подготовки или приглашения.</p>' : '') +
    '<div data-support-list></div></section>';
  void readQueue();
}

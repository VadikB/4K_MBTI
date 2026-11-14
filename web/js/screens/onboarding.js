import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import { stepBadgeLabel, onboardingTitle, onboardingDescription, featureList,
  onboardingVisual, onboardingNext, onboardingSkip, onboardingStepBackButton, onboardingPanel } from '../dom.js';
import { hideAllPanels, syncUrlState, openAcquaintanceWaiting } from '../router.js';
import { readApiResponse, createOperationId, fetchWithDeadline as fetch } from '../api.js';
import { prepareProductCycle, waitForProductCyclePreparation } from '../product-cycle-preparation.js';
import { hasPendingPreparedStart, readPendingPreparedStart } from '../product-cycle-start.js';
import { acquaintanceErrorMessage } from '../acquaintance-errors.js';
import { resumeOnboardingIndex, onboardingScopeKey, preparationView } from '../onboarding-flow.js';

let model = null;
let answers = {};
let savedAnswers = {};
let scopeKey = '';
let acquaintanceRequest = 0;
let reviewMode = false;
let busy = false;
let loadFailed = false;
let loading = false;
let errorMessage = '';
let notice = '';
let preparationError = null;
let startReadbackAdmitted = false;
let preparationTask = null;
let generation = 0;
let dialogState = null;
let dialogReturnFocus = null;
const issueDrafts = new Map();
let localOperation = null;
let progressTail = Promise.resolve();
const operationKeys = new Set();
const draftKeys = new Set();
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const questions = () => model?.readiness?.briefing?.questions || [];
const summaryIndex = () => 2 + questions().length;
const explanationIndex = () => summaryIndex() + 1;
const readinessIndex = () => explanationIndex() + 2;
const operationKey = () => 'agent4k.onboardingOperation:' + scopeKey + ':' + (model?.late_readiness?.personalized_profile_id || '');
const draftKey = () => 'agent4k.onboardingDraft:' + scopeKey;
const readDraft = () => {
  if (!scopeKey) return {};
  const key = draftKey(); draftKeys.add(key);
  try { return JSON.parse(window.sessionStorage.getItem(key) || '{}') || {}; } catch { return {}; }
};
const writeDraft = () => {
  if (!scopeKey) return;
  const key = draftKey(); draftKeys.add(key);
  const dirty = Object.fromEntries(Object.entries(answers).filter(([name, value]) => value !== savedAnswers[name]));
  try {
    if (Object.keys(dirty).length) window.sessionStorage.setItem(key, JSON.stringify(dirty));
    else window.sessionStorage.removeItem(key);
  } catch { /* The in-memory draft remains available until navigation. */ }
};
const storeOperation = (operation) => {
  localOperation = { operation_id: operation.operation_id, status: operation.status,
    ...(operation.error ? { error: operation.error } : {}) };
  model.preparation_operation = localOperation;
  const key = operationKey();
  operationKeys.add(key);
  try { window.sessionStorage.setItem(key, JSON.stringify(localOperation)); } catch { /* Server recovery remains authoritative. */ }
};
const paragraph = (text) => '<p>' + escape(text) + '</p>';
const resizeAnswer = (input) => {
  input.style.height = '48px';
  input.style.height = Math.min(120, Math.max(48, input.scrollHeight)) + 'px';
  input.style.overflowY = input.scrollHeight > 120 ? 'auto' : 'hidden';
};
const hasDesktopKeyboard = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches;
// W02 labels apply only to its exact schema; legacy briefing keeps its question labels.
const answerLabels = () => {
  const schema = model?.readiness?.briefing?.question_schema;
  const keys = ['work_situations', 'decision_situations', 'constraints_interactions'];
  const canonical = schema?.variant === 'corporate' && schema.version === '1.0' && schema.questions?.length === 3 &&
    schema.questions.every((item, index) => item.key === keys[index] && item.text === questions()[index]);
  return canonical ? ['Задачи и рабочие ситуации', 'Решения в вашей роли', 'Ограничения и взаимодействия'] : questions();
};
const fieldsHtml = () => {
  const fields = model?.readiness?.briefing?.provided_participant_fields || [];
  const known = fields.some((item) => item.key === 'full_name');
  const rows = known ? ['full_name', 'organization', 'position', 'role'].map((key) => key === 'organization'
    ? { label: 'Организация', value: model?.readiness?.organization_name }
    : fields.find((item) => item.key === key) || { label: key === 'position' ? 'Должность' : 'Роль в оценке' }) : fields;
  return '<dl class="onboarding-data">' + rows.map((item) =>
    '<div><dt>' + escape(item.label) + '</dt><dd>' + escape(item.value || 'Не указано') + '</dd></div>').join('') + '</dl>' +
    paragraph('Роль назначена в программе оценки. Она описывает тип деятельности и может отличаться от названия должности.') +
    paragraph('Далее вы расскажете о своей работе. Эти ответы нужны для подготовки ситуаций и сами по себе не определяют уровень компетенций.') +
    '<div class="onboarding-consent">' + paragraph(model?.readiness?.briefing?.consent_text || 'Текст согласия недоступен.') + '</div>';
};
const summaryHtml = () => answerLabels().map((label, index) =>
  '<div class="onboarding-summary-item"><span class="onboarding-summary-label">' + escape(label) + '</span>' +
  '<div class="onboarding-summary-answer">' + escape(answers[`answer_${index + 1}`]) + '</div></div>').join('') +
  '<p class="onboarding-summary-note">' + escape(model?.mandatory_complete ? 'Сведения подтверждены. Здесь сохранены ваши ответы.' :
    'После подтверждения эти сведения будут использованы для подготовки вашей оценки.') + '</p>';

// Approved W02 presentation copy; this does not change the assigned methodology or assessment rules.
const competencyCopy = {
  'коммуникация': ['Понимать и быть понятым', 'Понятно передавать смысл, слушать и прояснять, управлять взаимодействием.'],
  'командная работа': ['Работать на общий результат', 'Договариваться о ролях и ответственности, согласовывать действия и использовать вклад участников.'],
  'креативность': ['Находить и развивать решения', 'Замечать возможности, создавать и объединять решения, проверять и развивать их.'],
  'критическое мышление': ['Обосновывать выводы', 'Проверять информацию и основания, рассматривать альтернативы и учитывать ограничения.'],
};
const competenciesHtml = () => {
  const items = model?.competency_explanation?.items || [];
  if (!items.length) return paragraph('Описание назначенной модели появится после завершения настройки источников организацией.');
  return '<div class="onboarding-knowledge">' + items.map((item, index) => {
    const copy = competencyCopy[String(item.name).toLowerCase()];
    return '<article><div class="onboarding-competency-label">' + String(index + 1).padStart(2, '0') + ' / ' + escape(item.name) +
      '</div><h3>' + escape(copy?.[0] || item.name) + '</h3>' + paragraph(copy?.[1] || item.definition) + '</article>';
  }).join('') + '</div>' + paragraph('Оценка покажет, как эти компетенции проявляются в предложенных ситуациях. Один ответ не определяет общую картину.');
};

const timing = () => {
  const preparedPlanSnapshot = model?.prepared_plan;
  const preparedPlan = preparedPlanSnapshot?.plan || preparedPlanSnapshot;
  const assignedTiming = model?.assigned_timing?.status === 'resolved' ? model.assigned_timing : null;
  return preparedPlan || assignedTiming;
};
const processCopy = () => {
  const effective = timing();
  const hours = Number(effective?.calendar_window_seconds || 0) / 3600;
  const returnPolicy = model?.prepared_plan?.plan?.return_policy_snapshot ||
    model?.prepared_plan?.return_policy_snapshot || effective?.return_policy_snapshot;
  let returnCopy = '';
  if (returnPolicy?.resume_mode === 'same_assessment_situation') {
    returnCopy = '\n\nПосле перерыва вы продолжите ту же незавершённую ситуацию. Чтобы вернуться к работе, нажмите „Продолжить“.';
  } else if (returnPolicy?.resume_mode === 'replace_assessment_situation') {
    returnCopy = '\n\nПосле перерыва незавершённая ситуация будет заменена по правилам этой оценки. Завершённые ситуации повторять не потребуется.';
  } else if (returnPolicy) {
    returnCopy = '\n\nПорядок возврата определяется сохранёнными правилами этой оценки и будет показан при продолжении.';
  }
  return 'Прочитайте ситуацию и опишите, как будете действовать. Поясните своё решение.\n\n' +
    'В некоторых ситуациях есть виртуальный собеседник. Если не хватает информации, можно задать ему вопрос.\n\n' +
    'После завершения ситуации переходите к следующей. Между завершёнными ситуациями можно сделать перерыв.\n\n' +
    'После оценки вы получите личный отчёт: результаты, объяснения и ограничения выводов.\n\n' +
    'Перед началом вы увидите число ситуаций и доступное время на выполнение. Сейчас время оценки ещё не идёт.\n\n' +
    'Во время перерыва между завершёнными ситуациями время выполнения не расходуется, а общий срок завершения продолжает идти. ' +
    (returnCopy ? returnCopy.trim() : 'Порядок возврата к незавершённой ситуации определяется правилами назначенной оценки.') +
    (hours > 0 ? `\n\nЗавершить оценку нужно в течение ${hours} ч. после её начала.` : '');
};
const readinessStep = () => {
  const status = preparationView(model, preparationError);
  const operationId = model?.preparation_operation?.operation_id;
  const reference = operationId ? paragraph('Код обращения: ' + operationId) : '';
  if (status === 'conflict') return { title: 'Нужно обновить состояние назначения',
    description: 'Сервер не разрешил эту подготовку: состояние изменилось или другая операция ещё выполняется. Ответы сохранены; обновите состояние, затем обратитесь к ответственному, если ограничение остаётся.',
    body: reference, action: 'refresh', button: 'Обновить состояние' };
  if (status === 'service') return { title: 'Сервис подготовки временно недоступен',
    description: 'Не удалось получить ответ сервера. Это не подтверждённый отказ подготовки. Ответы и идентификатор операции сохранены; повторите проверку состояния.',
    body: reference, action: 'refresh', button: 'Проверить состояние' };
  if (status === 'access') return { title: 'Нет доступа к подготовке',
    description: 'Права или область назначения изменились. Обновите состояние; если доступ не восстановится, обратитесь к ответственному.',
    body: reference, action: 'refresh', button: 'Обновить состояние' };
  if (status === 'plan_blocked') return { title: 'Старт оценки пока заблокирован',
    description: 'Подготовка не подтверждает все условия старта. Обратитесь к организатору оценки.',
    body: reference, action: 'refresh', button: 'Обновить состояние' };
  if (status === 'plan_missing') return { title: 'Подготовленный план пока недоступен',
    description: 'Сервер сообщил о завершении операции, но допустимый подготовленный план не получен. Время оценки ещё не началось.',
    body: reference, action: 'refresh', button: 'Проверить состояние' };
  if (status === 'network') return { title: 'Не удалось проверить подготовку',
    description: 'Сейчас нет подтверждённого статуса сервера. Это не означает, что подготовка завершилась ошибкой. Ваши ответы и операция сохраняются.',
    body: reference, action: 'refresh', button: 'Проверить состояние' };
  if (status === 'organization') return { title: 'Для оценки ещё нужны сведения организации',
    description: 'Ваши ответы сохранены. Ответственный должен завершить настройку роли и источников оценки. Повторно отвечать на вопросы не нужно.',
    body: '<div class="onboarding-warning">Обратитесь к администратору вашей организации.</div>',
    action: 'refresh', button: 'Проверить готовность' };
  if (status === 'failed') {
    const canRetry = model?.preparation_operation?.retry_allowed === true;
    return { title: 'Не удалось подготовить оценку',
      description: model?.preparation_operation?.error?.message ||
        'Ваши ответы сохранены. Подготовка завершилась с ошибкой; обратитесь к ответственному за оценку.',
      body: reference, action: canRetry ? 'retry' : 'refresh',
      button: canRetry ? 'Повторить подготовку' : 'Проверить состояние' };
  }
  if (status === 'ready') {
    const plan = timing();
    const pendingStart = hasPendingPreparedStart(model?.prepared_plan?.cycle_id);
    if (pendingStart && !startReadbackAdmitted) return {
      title: 'Проверяем первый старт',
      description: 'Ответ на команду старта не получен. Ваши сведения сохранены. Сначала проверьте состояние: оценка могла уже начаться.',
      body: reference, action: 'check_start', button: 'Проверить состояние',
    };
    if (pendingStart) return {
      title: 'Старт ещё не подтверждён',
      description: 'Сервер показывает подготовленную, но ещё не предъявленную ситуацию. Можно явно повторить старт с прежним ключом операции.',
      body: reference, action: 'start', button: 'Повторить старт',
    };
    return { title: 'Можно приступать к оценке',
      description: 'Подготовлены план и первая ситуация. Следующие ситуации подготавливаются по ходу оценки. Время начнётся после вашего явного действия.' +
        (plan?.participant_notice ? '\n\n' + plan.participant_notice : ''),
      body: '<div class="onboarding-metrics"><div><strong>' +
        Number(Array.isArray(plan?.route) ? plan.route.length : 0) + '</strong>Ситуации в плане</div><div><strong>' +
        Math.ceil(Number(plan?.time_budget_seconds || 0) / 60) + ' мин.</strong>Время на выполнение</div></div>',
      action: 'start', button: 'Приступить к оценке' };
  }
  return { title: 'Готовим вашу оценку', description: 'Готовим первую ситуацию с учётом ваших сведений. Ответы сохранены. Время оценки ещё не началось.',
    body: '<p role="status"><span class="onboarding-spinner" aria-hidden="true"></span>' +
      (model?.preparation_operation?.status === 'queued' ? 'Операция в очереди' :
        model?.preparation_operation?.status === 'running' ? 'Подготовка выполняется' : 'Проверяем подготовку') + '</p>' + reference,
    action: 'refresh', button: 'Проверить состояние' };
};

const steps = () => {
  const briefing = model?.readiness?.briefing || {};
  return [
    { title: 'Рады знакомству!',
      description: (briefing.organizer || model?.readiness?.organization_name || 'Ваша организация') + ' приглашает вас пройти оценку универсальных компетенций 4К.',
      body: '<strong>Зачем проводится оценка</strong>' + paragraph(briefing.purpose) +
        '<strong>Как будут использоваться результаты</strong>' + paragraph(briefing.results_usage) +
        '<strong>Кто увидит результат</strong>' + paragraph('Вы и администраторы вашей организации.') +
        paragraph('Сначала проверим сведения о вас, затем расскажем об оценке. Время выполнения ещё не идёт.'), button: 'Начать знакомство' },
    { title: 'Проверьте ваши сведения', description: 'Эти сведения помогут подготовить подходящие для вас ситуации.',
      body: fieldsHtml(), action: 'consent', button: 'Подтвердить' },
    ...questions().map((question, index) => ({ title: question, questionNumber: `ВОПРОС ${index + 1} ИЗ ${questions().length}`,
      description: (index === 0 ? 'Расскажите немного о своей работе. ' : '') + 'Ответьте своими словами. Если точного ответа нет, можно написать «Не знаю».',
      answerKey: `answer_${index + 1}`, body: '', button: 'Отправить' })),
    { title: 'Всё верно?', description: 'Проверьте ответы перед подготовкой ситуаций. До подтверждения вы можете их уточнить.',
      body: summaryHtml(), action: 'confirm', button: model?.mandatory_complete ? 'К объяснению 4К' : 'Подтвердить' },
    { title: 'Что такое 4К', description: 'Четыре компетенции помогают разбираться в задачах, взаимодействовать с людьми и находить решения.',
      body: competenciesHtml(), button: 'Как проходит оценка' },
    { title: 'Как будет проходить оценка', description: processCopy(), body: '', action: 'process', button: 'Завершить знакомство' },
    readinessStep(),
  ];
};

const identity = () => String(state.pendingUser?.id || '');
const isCurrent = (owner, epoch, run) => identity() === owner && state.identityEpoch === epoch && generation === run;
const api = async (suffix, options = {}) => {
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  const result = await readApiResponse(await fetch('/users/' + encodeURIComponent(owner) + suffix,
    { credentials: 'same-origin', ...options, headers: { 'Content-Type': 'application/json', ...options.headers } },
  ), 'Не удалось сохранить или загрузить состояние. Ваш текст оставлен для повтора.');
  if (!isCurrent(owner, epoch, run)) throw Object.assign(new Error('Сессия изменилась.'), { name: 'PreparationWaitStopped' });
  return result;
};

const loadAcquaintance = async () => {
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  const requestNo = ++acquaintanceRequest;
  const next = await api('/acquaintance');
  if (!isCurrent(owner, epoch, run) || requestNo !== acquaintanceRequest) {
    throw Object.assign(new Error('Состояние знакомства изменилось.'), { name: 'PreparationWaitStopped' });
  }
  const nextScope = onboardingScopeKey(owner, next);
  const dirty = nextScope === scopeKey && !next.mandatory_complete
    ? Object.fromEntries(Object.entries(answers).filter(([key, value]) => value !== savedAnswers[key])) : {};
  scopeKey = nextScope;
  model = next;
  savedAnswers = { ...(next.state?.answers_json || {}) };
  if (next.mandatory_complete) {
    const key = draftKey();
    draftKeys.add(key);
    try { window.sessionStorage.removeItem(key); } catch { /* Confirmed server state remains authoritative. */ }
    answers = { ...savedAnswers };
  } else {
    answers = { ...savedAnswers, ...readDraft(), ...dirty };
  }
  loadFailed = false;
  if (next.preparation_operation) localOperation = next.preparation_operation;
  else {
    try { localOperation = JSON.parse(window.sessionStorage.getItem(operationKey()) || 'null'); }
    catch { localOperation = null; }
    if (localOperation?.operation_id) model.preparation_operation = localOperation;
  }
  return next;
};
const saveProgress = (status, index = state.onboardingIndex) => {
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  const task = progressTail.catch(() => {}).then(async () => {
    if (!isCurrent(owner, epoch, run)) throw Object.assign(new Error('Сессия изменилась.'), { name: 'PreparationWaitStopped' });
    const result = await api('/onboarding', { method: 'PUT', body: JSON.stringify({ status, current_step: index }) });
    if (model) model.onboarding = result;
  });
  progressTail = task;
  return task;
};
const persistProgress = () => {
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  void saveProgress('in_progress').catch(() => {
    if (!isCurrent(owner, epoch, run)) return;
    notice = 'Ответ сохранён. Не удалось обновить отметку шага; при возвращении этап определяется по сохранённым ответам.';
    showMessages();
  });
};
const showMessages = () => {
  const error = document.getElementById('onboarding-error');
  const status = document.getElementById('onboarding-notice');
  error.textContent = errorMessage; error.hidden = !errorMessage;
  status.textContent = notice; status.hidden = !notice;
};
const captureInput = () => {
  const key = steps()[state.onboardingIndex]?.answerKey;
  const input = onboardingPanel.querySelector('.onboarding-answer');
  if (key && input) answers[key] = input.value;
};
const transcript = (step, userText, user = false) => '<section class="onboarding-message onboarding-message--' +
  (user ? 'user' : 'assistant') + '"><div class="onboarding-author">' + (user ? 'Вы' : '4К Ассистент') +
  '</div><div class="onboarding-bubble">' + (user ? escape(userText) : (step.questionNumber ? '<p class="onboarding-question-number">' + escape(step.questionNumber) + '</p>' : '') + '<h3>' + escape(step.title) +
    '</h3><p' + (step.answerKey ? ' class="onboarding-question-hint"' : '') + '>' + escape(step.description) + '</p>' + (step.body || '')) + '</div></section>';

const closeDialog = () => {
  const dialog = document.getElementById('onboarding-dialog');
  dialog.close(); dialogState = null;
  dialogReturnFocus?.focus({ preventScroll: true }); dialogReturnFocus = null;
};
const openDialog = (kind, trigger) => {
  if (busy || reviewMode || (kind === 'answers' && model?.mandatory_complete)) return;
  const owner = identity(), epoch = state.identityEpoch, run = generation, scope = scopeKey;
  const current = () => isCurrent(owner, epoch, run) && scopeKey === scope && state.currentScreen === 'onboarding';
  const dialog = document.getElementById('onboarding-dialog');
  dialogReturnFocus = trigger;
  dialogState = { kind, pending: false };
  const isAnswers = kind === 'answers';
  dialog.innerHTML = '<form><button type="button" class="onboarding-dialog-close" aria-label="Закрыть">×</button>' +
    '<h2 id="onboarding-dialog-title">' + (isAnswers ? 'Ваши ответы' : 'Сообщить о неточности') + '</h2>' +
    (isAnswers ? answerLabels().map((label, index) => '<label for="onboarding-edit-' + index + '">' + escape(label) +
      '</label><textarea id="onboarding-edit-' + index + '" name="answer_' + (index + 1) + '" rows="3" maxlength="4000"></textarea>').join('') :
      '<p>Опишите, что нужно проверить. Сообщение будет сохранено в вашей организации. Роль и сведения автоматически не изменятся.</p>' +
      '<label for="onboarding-issue-text">Что нужно проверить?</label><textarea id="onboarding-issue-text" rows="4" maxlength="2000"></textarea>') +
    '<p class="onboarding-error" role="alert" tabindex="-1" hidden></p><p role="status" hidden></p>' +
    '<div class="onboarding-actions"><button type="submit" class="primary-button">' + (isAnswers ? 'Сохранить' : 'Отправить') +
    '</button><button type="button" class="ghost-button" data-cancel>Отмена</button></div></form>';
  const inputs = [...dialog.querySelectorAll('textarea')];
  for (const input of inputs) {
    input.value = isAnswers ? answers[input.name] || '' : issueDrafts.get(scope) || '';
    if (!isAnswers) input.addEventListener('input', () => issueDrafts.set(scope, input.value));
  }
  dialog.querySelector('[data-cancel]').addEventListener('click', closeDialog);
  dialog.querySelector('.onboarding-dialog-close').addEventListener('click', closeDialog);
  const cancel = (event) => { event.preventDefault(); if (!dialogState?.pending) closeDialog(); };
  dialog.oncancel = cancel;
  dialog.querySelector('form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!dialogState || dialogState.pending || !current()) return;
    const errorNode = dialog.querySelector('[role="alert"]');
    const empty = inputs.find((input) => !input.value.trim());
    errorNode.hidden = true;
    if (empty) { errorNode.textContent = isAnswers ? 'Заполните ответ. Можно написать «Не знаю».' : 'Опишите неточность.'; errorNode.hidden = false; empty.focus(); return; }
    dialogState.pending = true;
    dialog.querySelectorAll('button, textarea').forEach((node) => { node.disabled = true; });
    try {
      if (isAnswers) {
        const updated = Object.fromEntries(inputs.map((input) => [input.name, input.value]));
        const result = await api('/acquaintance/answers', { method: 'PUT', body: JSON.stringify({ answers: updated, confirm: false }) });
        if (!current()) return;
        if (!result?.answers_json || Object.entries(updated).some(([key, value]) => result.answers_json[key] !== value)) {
          throw new Error('Сохранение ответов не подтверждено. Ваш текст оставлен для повтора.');
        }
        model.state = result; savedAnswers = { ...result.answers_json }; answers = { ...savedAnswers }; writeDraft();
        closeDialog(); renderOnboarding(); document.getElementById('onboarding-edit-answers')?.focus();
      } else {
        const receipt = await api('/acquaintance/issues', { method: 'POST', body: JSON.stringify({ message: inputs[0].value }) });
        if (!current()) return;
        if (!receipt?.id || !receipt.status) throw new Error('Сохранение сообщения не подтверждено. Ваш текст оставлен для повтора.');
        issueDrafts.delete(scope);
        inputs[0].closest('form').querySelectorAll('label, textarea').forEach((node) => { node.hidden = true; });
        dialog.querySelector('[type="submit"]').hidden = true;
        const status = dialog.querySelector('[role="status"]'); status.hidden = false;
        status.textContent = 'Сообщение сохранено в вашей организации. Можно продолжить знакомство. Роль и сведения автоматически не изменились.';
        dialog.querySelector('[data-cancel]').textContent = 'Продолжить знакомство';
        dialog.querySelector('[data-cancel]').focus();
      }
    } catch (error) {
      if (current()) { errorNode.textContent = acquaintanceErrorMessage(error); errorNode.hidden = false; errorNode.focus(); }
    } finally {
      if (current() && dialogState) { dialogState.pending = false; dialog.querySelectorAll('button, textarea').forEach((node) => { node.disabled = false; }); }
    }
  });
  dialog.showModal(); inputs[0]?.focus();
};

export const renderOnboarding = ({ focus = false } = {}) => {
  const all = steps();
  state.onboardingIndex = Math.max(0, Math.min(state.onboardingIndex || 0, all.length - 1));
  const index = state.onboardingIndex;
  const step = loading ? { title: 'Загружаем знакомство', description: 'Проверяем назначение и сохранённый этап.', button: 'Загрузка…', body: '' }
    : loadFailed ? { title: 'Не удалось загрузить знакомство', description: 'Сейчас не удалось получить сохранённое состояние. Попробуйте ещё раз.', action: 'reload', button: 'Повторить', body: paragraph('Повторная проверка не стирает ранее сохранённые ответы.') }
      : reviewMode ? { title: 'Знакомство завершено', description: 'Вы можете прочитать сохранённые сообщения и ответы.', button: 'Вернуться к готовности оценки', body: '' } : all[index];
  onboardingPanel.dataset.step = String(index < 2 ? 1 : index <= summaryIndex() ? 2 : 3);
  stepBadgeLabel.textContent = reviewMode ? 'История знакомства' : index === readinessIndex() ? 'Готовность оценки' : 'Знакомство';
  onboardingStepBackButton.hidden = loading || loadFailed || reviewMode || index === 0;
  onboardingStepBackButton.disabled = busy;
  onboardingTitle.textContent = step.title;
  onboardingDescription.textContent = step.description;
  onboardingDescription.classList.toggle('onboarding-question-hint', Boolean(step.answerKey));
  const number = document.getElementById('onboarding-question-number');
  number.textContent = step.questionNumber || ''; number.hidden = !step.questionNumber;
  onboardingVisual.replaceChildren();
  featureList.innerHTML = step.body || '';
  const input = onboardingPanel.querySelector('.onboarding-answer');
  input.value = step.answerKey ? answers[step.answerKey] || '' : '';
  input.disabled = !step.answerKey || busy || reviewMode || Boolean(model?.mandatory_complete);
  input.placeholder = input.disabled ? 'Сейчас выберите действие под сообщением' : 'Напишите ответ…';
  input.setAttribute('aria-label', step.answerKey ? step.title : 'Ваш ответ');
  // A transport failure does not make a correct answer invalid.
  input.setAttribute('aria-invalid', 'false');
  const actions = document.getElementById('onboarding-actions');
  const composer = document.querySelector('.onboarding-composer-inner');
  (step.answerKey ? composer : actions).prepend(onboardingNext);
  composer.querySelector('.onboarding-send-placeholder').hidden = Boolean(step.answerKey);
  if (step.answerKey) onboardingNext.setAttribute('aria-label', step.button);
  else onboardingNext.removeAttribute('aria-label');
  onboardingNext.classList.toggle('onboarding-send', Boolean(step.answerKey));
  if (step.answerKey) composer.append(onboardingNext);
  window.requestAnimationFrame(() => resizeAnswer(input));
  actions.querySelectorAll('[data-secondary]').forEach((node) => node.remove());
  if (!loading && !loadFailed && !reviewMode) {
    const secondary = (id, label, kind) => {
      const button = document.createElement('button'); button.type = 'button'; button.id = id;
      button.className = kind === 'issue' ? 'onboarding-text-action' : 'ghost-button'; button.dataset.secondary = ''; button.textContent = label; button.disabled = busy;
      button.addEventListener('click', () => openDialog(kind, button)); actions.append(button);
    };
    if (step.action === 'confirm' && !model?.mandatory_complete) secondary('onboarding-edit-answers', 'Изменить мои ответы', 'answers');
    if (step.action === 'consent' || step.action === 'confirm') secondary('onboarding-report-issue', 'Сообщить о неточности', 'issue');
  }
  document.getElementById('onboarding-messages').innerHTML = loading || loadFailed ? '' : all.slice(0, reviewMode ? readinessIndex() : index).map((prior, priorIndex) => {
    const historical = priorIndex === summaryIndex() ? { ...prior, body: summaryHtml() } : prior;
    let html = transcript(historical);
    if (prior.answerKey && answers[prior.answerKey]) html += transcript(null, answers[prior.answerKey], true);
    else if (priorIndex === 0) html += transcript(null, 'Начать знакомство', true);
    else if (prior.action === 'consent' && model?.state?.consent_accepted_at) html += transcript(null, 'Подтвердить', true);
    else if (prior.action === 'confirm' && model?.mandatory_complete) html += transcript(null, 'Подтвердить', true);
    return html;
  }).join('');
  onboardingNext.textContent = busy ? 'Подождите…' : reviewMode ? 'Вернуться к готовности оценки'
    : step.button || 'Далее';
  onboardingNext.disabled = loading || busy || (!loadFailed && step.action === 'consent' && !model?.readiness?.briefing?.consent_text);
  onboardingSkip.hidden = loading || reviewMode || !model?.mandatory_complete || ![explanationIndex(), explanationIndex() + 1].includes(index);
  onboardingSkip.textContent = 'Перейти к готовности'; onboardingSkip.disabled = busy;
  document.getElementById('onboarding-home').disabled = loading || busy;
  showMessages();
  if (focus) window.requestAnimationFrame(() => {
    const current = onboardingPanel.querySelector('.onboarding-copy');
    current.scrollIntoView({ block: 'start' });
    if (errorMessage) document.getElementById('onboarding-error').focus({ preventScroll: true });
    else if (step.answerKey && !busy) onboardingPanel.querySelector('.onboarding-answer')?.focus({ preventScroll: true });
    else { onboardingTitle.tabIndex = -1; onboardingTitle.focus({ preventScroll: true }); }
  });
};

const beginPreparation = ({ retry = false } = {}) => {
  if (preparationTask?.generation === generation) return preparationTask.promise;
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  let scope = scopeKey;
  const current = () => isCurrent(owner, epoch, run) && scopeKey === scope && state.currentScreen === 'onboarding';
  const controller = new AbortController();
  const task = { generation: run, controller, promise: null };
  task.promise = (async () => {
    preparationError = null;
    try {
      const resolved = await api('/acquaintance/resolve-profile', { method: 'POST' });
      if (!current()) return;
      const resolvedScope = onboardingScopeKey(owner, resolved);
      if (resolvedScope !== scope) {
        scopeKey = resolvedScope;
        scope = resolvedScope;
        localOperation = null;
      }
      model = resolved;
      try { localOperation = JSON.parse(window.sessionStorage.getItem(operationKey()) || 'null'); }
      catch { localOperation = null; }
      if (model.late_readiness?.status !== 'ready_to_prepare') { renderOnboarding(); return; }
      let accepted = model.preparation_operation || localOperation;
      if (accepted?.status === 'failed' && !retry) { renderOnboarding(); return; }
      if (model.prepared_plan && (!accepted || accepted.status === 'completed')) { renderOnboarding(); return; }
      const callbacks = { signal: controller.signal, isCurrent: current,
        onRequested: (operation) => { if (current()) storeOperation(operation); },
        onAccepted: (operation) => { if (current()) storeOperation(operation); },
        onStatus: (operation) => { if (current()) { storeOperation(operation); if (state.onboardingIndex === readinessIndex()) renderOnboarding(); } },
      };
      // A lost command response has an operation ID: reconcile it through owned GET,
      // never send another preparation command merely because the page reloaded.
      const prepared = accepted && !retry
        ? await waitForProductCyclePreparation(accepted, callbacks)
        : await prepareProductCycle({ personalized_profile_id: model.late_readiness.personalized_profile_id,
          idempotency_key: !retry && accepted?.operation_id || createOperationId(), selected_skills: ['K1', 'K2', 'K3', 'K4'],
        }, callbacks);
      if (!current()) return;
      state.assessmentRuntimeKind = 'cycle'; state.productCycleId = prepared.plan.cycle_id;
      persistAssessmentContext();
      await loadAcquaintance();
      if (current()) renderOnboarding();
    } catch (error) {
      if (!current() || ['PreparationWaitStopped', 'StaleApiResponseError'].includes(error.name)) return;
      if (error.status === 409) {
        try {
          await loadAcquaintance();
          if (!model.mandatory_complete) state.onboardingIndex = resumeOnboardingIndex(model, model.onboarding);
        } catch { /* The original conflict remains distinct from a job failure. */ }
        if (!current()) return;
      }
      preparationError = error.name === 'PreparationFailed' ? { kind: 'failed' }
        : error.status === 403 ? { kind: 'access' } : error.status === 409 ? { kind: 'conflict' }
          : error.status >= 500 ? { kind: 'service' } : { kind: 'network' };
      if (error.status === 404 && localOperation) storeOperation({ ...localOperation, status: 'unknown' });
      if (error.name === 'PreparationFailed') storeOperation({ operation_id: error.operationId, status: 'failed', error: error.operationError, retry_allowed: error.retryAllowed === true });
      renderOnboarding();
    } finally { if (preparationTask === task) preparationTask = null; }
  })();
  preparationTask = task;
  return task.promise;
};

export const openOnboarding = async ({ currentStep = 0, reviewMode: requestedReview = false } = {}) => {
  closeDialog();
  generation += 1; preparationTask?.controller.abort(); busy = false; progressTail = Promise.resolve();
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  reviewMode = Boolean(requestedReview); errorMessage = ''; notice = ''; preparationError = null; startReadbackAdmitted = false;
  setCurrentScreen('onboarding'); hideAllPanels(); onboardingPanel.classList.remove('hidden');
  state.onboardingShown = true; state.onboardingIndex = Number(currentStep || 0);
  // Preserve navigation intent even if reload happens while the first GET is pending.
  persistAssessmentContext(); syncUrlState('onboarding');
  loading = true; renderOnboarding();
  try {
    await loadAcquaintance();
    if (!isCurrent(owner, epoch, run) || state.currentScreen !== 'onboarding') return;
    if (model.readiness.status !== 'ready') { loading = false; openAcquaintanceWaiting(model.readiness); return; }
    reviewMode = reviewMode && Boolean(model.mandatory_complete);
    state.onboardingIndex = reviewMode ? readinessIndex() : resumeOnboardingIndex(model, model.onboarding);
    if (!reviewMode && model.onboarding?.status === 'not_started') await saveProgress('in_progress');
  } catch (error) {
    if (!isCurrent(owner, epoch, run)) return;
    loadFailed = true; errorMessage = acquaintanceErrorMessage(error);
  }
  if (!isCurrent(owner, epoch, run) || state.currentScreen !== 'onboarding') return;
  loading = false;
  persistAssessmentContext(); syncUrlState('onboarding'); renderOnboarding({ focus: true });
  if (!loadFailed && model?.mandatory_complete && !reviewMode) void beginPreparation();
};

export const goBackInOnboarding = () => {
  if (loading || busy || state.onboardingIndex <= 0) return;
  captureInput(); errorMessage = ''; notice = '';
  state.onboardingIndex -= 1; renderOnboarding({ focus: true });
};

const advance = async () => {
  if (loading || busy) return;
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  captureInput();
  const step = steps()[state.onboardingIndex];
  busy = true; errorMessage = ''; notice = ''; renderOnboarding();
  try {
    if (loadFailed) { await openOnboarding(); return; }
    if (reviewMode) {
      const { loadUserJourneyState } = await import('../session.js');
      const journey = await loadUserJourneyState({ allowAdmin: true });
      if (!isCurrent(owner, epoch, run)) return;
      if (journey?.next_action !== 'show_onboarding') {
        const { loadInterview } = await import('../screen-loaders.js');
        const interview = await loadInterview();
        if (isCurrent(owner, epoch, run)) await interview.handleAssessmentEntryClick();
        return;
      }
      await loadAcquaintance();
      if (model.readiness.status !== 'ready') { openAcquaintanceWaiting(model.readiness); return; }
      reviewMode = false;
      state.onboardingIndex = model.mandatory_complete ? readinessIndex() : resumeOnboardingIndex(model, model.onboarding);
      persistAssessmentContext();
      if (model.mandatory_complete) void beginPreparation();
      return;
    }
    if (step.answerKey) {
      if (model.mandatory_complete) { state.onboardingIndex += 1; return; }
      if (!String(answers[step.answerKey] || '').trim()) throw new Error('Напишите ответ. Если точного ответа нет, можно написать «Не знаю».');
      model.state = await api('/acquaintance/answers', { method: 'PUT', body: JSON.stringify({ answers: { [step.answerKey]: answers[step.answerKey] }, confirm: false }) });
      savedAnswers = { ...model.state.answers_json };
      writeDraft();
      state.onboardingIndex += 1; persistProgress();
    } else if (step.action === 'consent') {
      model.state = await api('/acquaintance/consent', { method: 'POST', body: JSON.stringify({ version: model.readiness.briefing.consent_version }) });
      state.onboardingIndex += 1; persistProgress();
    } else if (step.action === 'confirm') {
      if (!model.mandatory_complete) {
        model.state = await api('/acquaintance/answers', { method: 'PUT', body: JSON.stringify({ answers, confirm: true }) });
        savedAnswers = { ...model.state.answers_json }; model.mandatory_complete = true;
        writeDraft();
      }
      state.onboardingIndex = explanationIndex();
      renderOnboarding({ focus: true }); persistProgress();
      void beginPreparation(); // Confirmation never awaits preparation before showing 4К.
    } else if (step.action === 'process') {
      await saveProgress('completed', readinessIndex()); state.onboardingIndex = readinessIndex();
      void beginPreparation();
    } else if (['refresh', 'retry'].includes(step.action)) {
      await loadAcquaintance();
      if (model.readiness.status !== 'ready') { openAcquaintanceWaiting(model.readiness); return; }
      if (!model.mandatory_complete) state.onboardingIndex = resumeOnboardingIndex(model, model.onboarding);
      else void beginPreparation({ retry: step.action === 'retry' });
    } else if (step.action === 'check_start') {
      const cycleId = model.prepared_plan?.cycle_id;
      if (!cycleId) throw new Error('Подготовленный цикл пока недоступен. Проверьте готовность.');
      const readback = await readPendingPreparedStart(cycleId);
      if (!readback) throw new Error('Состояние старта не найдено. Обновите готовность.');
      if (readback.started) {
        const { loadInterview } = await import('../screen-loaders.js');
        const interview = await loadInterview();
        if (!isCurrent(owner, epoch, run)) return;
        await interview.startAssessmentInterview({ preparedCycleId: cycleId });
      } else startReadbackAdmitted = true;
    } else if (step.action === 'start') {
      startReadbackAdmitted = false;
      const cycleId = model.prepared_plan?.cycle_id;
      if (!cycleId) throw new Error('Подготовленный цикл пока недоступен. Проверьте готовность.');
      await saveProgress('completed', readinessIndex());
      const { loadInterview } = await import('../screen-loaders.js');
      const interview = await loadInterview();
      if (!isCurrent(owner, epoch, run)) return;
      await interview.startAssessmentInterview({ preparedCycleId: cycleId });
    } else {
      await saveProgress('in_progress', state.onboardingIndex + 1); state.onboardingIndex += 1;
    }
    persistAssessmentContext();
  } catch (error) {
    if (isCurrent(owner, epoch, run)) errorMessage = acquaintanceErrorMessage(error);
  } finally {
    if (isCurrent(owner, epoch, run)) { busy = false; if (state.currentScreen === 'onboarding') renderOnboarding({ focus: true }); }
  }
};

export const initOnboarding = () => {
  onboardingNext.addEventListener('click', () => { void advance(); });
  const input = onboardingPanel.querySelector('.onboarding-answer');
  input.addEventListener('input', () => {
    const key = steps()[state.onboardingIndex]?.answerKey;
    if (!key || input.disabled) return;
    answers[key] = input.value; writeDraft(); errorMessage = ''; notice = ''; showMessages(); resizeAnswer(input);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing || !hasDesktopKeyboard() || busy || input.disabled) return;
    event.preventDefault(); onboardingNext.click();
  });
  onboardingStepBackButton.addEventListener('click', goBackInOnboarding);
  onboardingSkip.addEventListener('click', async () => {
    if (busy || reviewMode || !model?.mandatory_complete || ![explanationIndex(), explanationIndex() + 1].includes(state.onboardingIndex)) return;
    busy = true; renderOnboarding();
    const owner = identity(), epoch = state.identityEpoch, run = generation;
    try { await saveProgress('completed', readinessIndex()); state.onboardingIndex = readinessIndex(); void beginPreparation(); }
    catch (error) { if (isCurrent(owner, epoch, run)) errorMessage = acquaintanceErrorMessage(error); }
    finally { if (isCurrent(owner, epoch, run)) { busy = false; renderOnboarding({ focus: true }); } }
  });
  document.getElementById('onboarding-home').addEventListener('click', async () => {
    if (busy) return;
    captureInput();
    if (Object.entries(answers).some(([key, value]) => value !== savedAnswers[key])) {
      writeDraft();
    }
    const owner = identity(), epoch = state.identityEpoch, run = generation;
    busy = true; renderOnboarding();
    try {
      const { loadUserJourneyState } = await import('../session.js');
      if (!isCurrent(owner, epoch, run)) return;
      const journey = await loadUserJourneyState({ allowAdmin: true });
      if (!isCurrent(owner, epoch, run)) return;
      if (journey?.can_open_dashboard) {
        const payload = await api('/session-bootstrap');
        state.dashboard = payload.dashboard;
        const dashboard = await import('./dashboard.js');
        if (isCurrent(owner, epoch, run)) dashboard.openDashboard();
      } else if (journey?.next_action === 'wait_for_acquaintance_data') openAcquaintanceWaiting(journey.acquaintance.readiness);
      else { notice = 'Сейчас доступно продолжение знакомства. Уже сохранённые ответы остаются на месте.'; showMessages(); }
    } catch (error) { if (isCurrent(owner, epoch, run)) { errorMessage = acquaintanceErrorMessage(error); showMessages(); } }
    finally { if (isCurrent(owner, epoch, run)) { busy = false; if (state.currentScreen === 'onboarding') renderOnboarding(); } }
  });
  window.addEventListener('agent4k:assessment-context-cleared', () => {
    closeDialog(); issueDrafts.clear();
    generation += 1; preparationTask?.controller.abort(); preparationTask = null;
    progressTail = Promise.resolve();
    for (const key of operationKeys) { try { window.sessionStorage.removeItem(key); } catch { /* No storage access. */ } }
    for (const key of draftKeys) { try { window.sessionStorage.removeItem(key); } catch { /* No storage access. */ } }
    draftKeys.clear();
    operationKeys.clear(); model = null; answers = {}; savedAnswers = {}; scopeKey = ''; localOperation = null;
    busy = false; loading = false; errorMessage = ''; notice = ''; preparationError = null;
  });
};

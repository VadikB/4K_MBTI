import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import { stepBadgeLabel, onboardingTitle, onboardingDescription, featureList,
  onboardingVisual, onboardingNext, onboardingSkip, onboardingStepBackButton, onboardingPanel } from '../dom.js';
import { hideAllPanels, syncUrlState, openAcquaintanceWaiting } from '../router.js';
import { readApiResponse, createOperationId, fetchWithDeadline as fetch } from '../api.js';
import { prepareProductCycle, waitForProductCyclePreparation } from '../product-cycle-preparation.js';
import { resumeOnboardingIndex, onboardingScopeKey, preparationView } from '../onboarding-flow.js';

let model = null;
let answers = {};
let savedAnswers = {};
let scopeKey = '';
let reviewMode = false;
let busy = false;
let loadFailed = false;
let loading = false;
let errorMessage = '';
let notice = '';
let preparationError = null;
let preparationTask = null;
let generation = 0;
let editingFromSummary = false;
let localOperation = null;
let progressTail = Promise.resolve();
const operationKeys = new Set();
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const questions = () => model?.readiness?.briefing?.questions || [];
const summaryIndex = () => 2 + questions().length;
const explanationIndex = () => summaryIndex() + 1;
const readinessIndex = () => explanationIndex() + 2;
const operationKey = () => 'agent4k.onboardingOperation:' + scopeKey + ':' + (model?.late_readiness?.personalized_profile_id || '');
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
const fieldsHtml = () => '<dl class="onboarding-data">' +
  (model?.readiness?.briefing?.provided_participant_fields || []).map((item) =>
    '<div><dt>' + escape(item.label) + '</dt><dd>' + escape(item.value || 'Ожидает уточнения организацией') + '</dd></div>').join('') + '</dl>';
const summaryHtml = (editable) => questions().map((question, index) => {
  const key = `answer_${index + 1}`;
  return '<div class="onboarding-summary-item"><strong>' + escape(question) + '</strong>' +
    '<div class="onboarding-summary-answer">' + escape(answers[key]) + '</div>' +
    (editable ? '<button type="button" class="onboarding-edit-answer" data-edit-answer="' + index +
      '" aria-label="Изменить ответ на вопрос ' + (index + 1) + '">Изменить</button>' : '') + '</div>';
}).join('');

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
  return 'Вам предстоит разобраться в практических ситуациях. Опишите, как будете действовать, и поясните решения.\n\n' +
    'В некоторых ситуациях есть собеседник. Если не хватает информации, можно задать ему вопрос.\n\n' +
    'Между завершёнными ситуациями можно сделать перерыв. Во время такого перерыва время на выполнение не расходуется, но общий срок завершения продолжает идти.\n\n' +
    (hours > 0 ? `Завершить оценку нужно в течение ${hours} ч. после её начала.` :
      'Фактические параметры появятся после подготовки плана, до явного старта.') +
    returnCopy;
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
  if (status === 'plan_missing') return { title: 'Подготовленный план пока недоступен',
    description: 'Сервер сообщил о завершении операции, но допустимый подготовленный план не получен. Время оценки ещё не началось.',
    body: reference, action: 'refresh', button: 'Проверить состояние' };
  if (status === 'network') return { title: 'Не удалось проверить подготовку',
    description: 'Сейчас нет подтверждённого статуса сервера. Это не означает, что подготовка завершилась ошибкой. Ваши ответы и операция сохраняются.',
    body: reference, action: 'refresh', button: 'Проверить состояние' };
  if (status === 'organization') return { title: 'Для оценки ещё нужны сведения организации',
    description: 'Ваши ответы сохранены. Ответственный должен завершить настройку роли и источников оценки. Повторно отвечать на вопросы не нужно.',
    body: '<div class="onboarding-warning">' + escape(model?.readiness?.responsible_contact
      ? 'Контакт ответственного: ' + model.readiness.responsible_contact : 'Обратитесь к ответственному за оценку в вашей организации.') + '</div>',
    action: 'refresh', button: 'Проверить готовность' };
  if (status === 'failed') return { title: 'Не удалось подготовить оценку',
    description: model?.preparation_operation?.error?.code === 'ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE'
      ? model.preparation_operation.error.message
      : 'Ваши ответы сохранены. Подготовка завершилась технической ошибкой; можно повторить её или передать код обращения ответственному.',
    body: reference, action: 'retry', button: 'Повторить подготовку' };
  if (status === 'ready') {
    const plan = timing();
    return { title: 'Можно приступать к оценке',
      description: 'Подготовлены план и первая ситуация. Следующие ситуации подготавливаются по ходу оценки. Время начнётся после вашего явного действия.',
      body: '<div class="onboarding-metrics"><div><strong>' +
        Number(Array.isArray(plan?.route) ? plan.route.length : 0) + '</strong>Ситуации в плане</div><div><strong>' +
        Math.ceil(Number(plan?.time_budget_seconds || 0) / 60) + ' мин.</strong>Время на выполнение</div></div>',
      action: 'start', button: 'Приступить к оценке' };
  }
  return { title: 'Готовим вашу оценку', description: 'Ваши ответы сохранены. Дождитесь готовности плана и первой ситуации. Время выполнения ещё не идёт; закрытие вкладки не отменяет серверную подготовку.',
    body: '<p role="status"><span class="onboarding-spinner" aria-hidden="true"></span>' +
      (model?.preparation_operation?.status === 'queued' ? 'Операция в очереди' :
        model?.preparation_operation?.status === 'running' ? 'Подготовка выполняется' : 'Проверяем подготовку') + '</p>' + reference,
    action: 'refresh', button: 'Проверить состояние' };
};

const steps = () => {
  const briefing = model?.readiness?.briefing || {};
  return [
    { title: 'Оценку организует ' + (briefing.organizer || model?.readiness?.organization_name || 'ваша организация'),
      description: briefing.purpose || '', body: '<strong>Как используются результаты</strong>' + paragraph(briefing.results_usage) +
        '<strong>Кто получит результаты</strong>' + paragraph(briefing.result_recipients), button: 'Начать знакомство' },
    { title: 'Проверьте предоставленные сведения', description: briefing.consent_text || 'Текст согласия недоступен. Обратитесь к ответственному.',
      body: fieldsHtml(), action: 'consent', button: model?.state?.consent_accepted_at ? 'Продолжить' : 'Согласен и продолжить' },
    ...questions().map((question, index) => ({ title: question,
      description: (index === 0 ? 'Расскажите немного о своей работе. ' : '') + 'Ответьте своими словами. Если точного ответа нет, можно написать «Не знаю».',
      answerKey: `answer_${index + 1}`, body: '', button: editingFromSummary ? 'Сохранить ответ' : 'Сохранить и продолжить' })),
    { title: 'Проверьте ваши ответы', description: model?.mandatory_complete
      ? 'Сведения подтверждены. Здесь сохранены ваши ответы.' : 'До подтверждения можно адресно исправить каждый собственный ответ.',
      body: summaryHtml(!model?.mandatory_complete && !reviewMode), action: 'confirm', button: model?.mandatory_complete ? 'К объяснению 4К' : 'Подтвердить' },
    { title: 'Что показывает оценка 4К', description: 'Четыре взаимосвязанные компетенции рассматриваются в практических ситуациях.',
      body: (model?.competency_explanation?.items || []).length
        ? '<div class="onboarding-knowledge">' + model.competency_explanation.items.map((item) =>
          '<article><h3>' + escape(item.name) + '</h3>' + paragraph(item.definition) + '</article>').join('') + '</div>'
        : paragraph('Описание назначенной модели появится после завершения настройки источников организацией.'), button: 'Как проходит оценка' },
    { title: 'Как будет проходить оценка', description: processCopy(), body: '', action: 'process', button: 'К готовности оценки' },
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
  const next = await api('/acquaintance');
  if (!isCurrent(owner, epoch, run)) throw Object.assign(new Error('Сессия изменилась.'), { name: 'PreparationWaitStopped' });
  const nextScope = onboardingScopeKey(owner, next);
  const dirty = nextScope === scopeKey && !next.mandatory_complete
    ? Object.fromEntries(Object.entries(answers).filter(([key, value]) => value !== savedAnswers[key])) : {};
  scopeKey = nextScope;
  model = next;
  savedAnswers = { ...(next.state?.answers_json || {}) };
  answers = { ...savedAnswers, ...dirty };
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
  const input = featureList.querySelector('.onboarding-answer');
  if (key && input) answers[key] = input.value;
};
const transcript = (step, userText, user = false) => '<section class="onboarding-message onboarding-message--' +
  (user ? 'user' : 'assistant') + '"><div class="onboarding-author">' + (user ? 'Вы' : '4К Ассистент') +
  '</div><div class="onboarding-bubble">' + (user ? escape(userText) : '<h3>' + escape(step.title) +
    '</h3>' + paragraph(step.description) + (step.body || '')) + '</div></section>';

const reportIssue = () => {
  const details = document.createElement('details'); details.className = 'onboarding-data-issue';
  details.innerHTML = '<summary>Сообщить о неточности</summary><label>Что нужно проверить?<textarea rows="2" maxlength="2000"></textarea></label>' +
    '<button type="button" class="ghost-button">Передать ответственному</button><p role="status"></p>';
  const button = details.querySelector('button'), input = details.querySelector('textarea'), result = details.querySelector('[role="status"]');
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    if (!input.value.trim()) { result.textContent = 'Опишите неточность.'; input.focus(); return; }
    button.disabled = true;
    try {
      await api('/acquaintance/issues', { method: 'POST', body: JSON.stringify({ message: input.value }) });
      result.textContent = 'Сообщение сохранено и доступно ответственному вашей организации.';
    } catch (error) { result.textContent = error.message; }
    finally { button.disabled = false; }
  });
  return details;
};

export const renderOnboarding = ({ focus = false } = {}) => {
  const all = steps();
  state.onboardingIndex = Math.max(0, Math.min(state.onboardingIndex || 0, all.length - 1));
  const index = state.onboardingIndex;
  const step = loading ? { title: 'Загружаем знакомство', description: 'Проверяем сохранённый этап и готовность оценки.', button: 'Подождите…', body: '' }
    : loadFailed ? { title: 'Не удалось загрузить знакомство', description: 'Сохранённые ответы остаются на сервере.', action: 'reload', button: 'Повторить', body: '' } : all[index];
  onboardingPanel.dataset.step = String(index < 2 ? 1 : index <= summaryIndex() ? 2 : 3);
  stepBadgeLabel.textContent = index < explanationIndex() ? 'Знакомство' : index === readinessIndex() ? 'Готовность оценки' : 'Оценка 4К';
  onboardingStepBackButton.hidden = loading || loadFailed || index === 0;
  onboardingStepBackButton.disabled = busy;
  onboardingTitle.textContent = step.title;
  onboardingDescription.textContent = step.description;
  onboardingVisual.replaceChildren();
  featureList.innerHTML = step.body || '';
  if (step.answerKey) {
    const input = document.createElement('textarea'); input.className = 'onboarding-answer';
    input.rows = 1; input.maxLength = 4000; input.value = answers[step.answerKey] || '';
    input.setAttribute('aria-label', step.title); input.setAttribute('aria-describedby', 'onboarding-error');
    input.setAttribute('aria-invalid', String(Boolean(errorMessage))); input.disabled = busy || reviewMode || Boolean(model?.mandatory_complete);
    input.addEventListener('input', () => {
      answers[step.answerKey] = input.value;
      errorMessage = ''; notice = ''; input.setAttribute('aria-invalid', 'false'); showMessages();
      resizeAnswer(input);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.shiftKey || event.isComposing || !hasDesktopKeyboard() || busy) return;
      event.preventDefault();
      onboardingNext.click();
    });
    featureList.append(input);
    window.requestAnimationFrame(() => resizeAnswer(input));
  }
  if (step.action === 'consent') featureList.append(reportIssue());
  document.getElementById('onboarding-messages').innerHTML = loading || loadFailed ? '' : all.slice(0, index).map((prior, priorIndex) => {
    const historical = priorIndex === summaryIndex() ? { ...prior, body: summaryHtml(false) } : prior;
    let html = transcript(historical);
    if (prior.answerKey && answers[prior.answerKey]) html += transcript(null, answers[prior.answerKey], true);
    else if (priorIndex === 0) html += transcript(null, 'Начать знакомство', true);
    else if (prior.action === 'consent' && model?.state?.consent_accepted_at) html += transcript(null, 'Согласен и продолжить', true);
    else if (prior.action === 'confirm' && model?.mandatory_complete) html += transcript(null, 'Подтвердить', true);
    return html;
  }).join('');
  onboardingNext.textContent = busy ? 'Подождите…' : reviewMode ? 'Вернуться к оценке'
    : step.answerKey && model?.mandatory_complete ? 'Продолжить' : step.button || 'Далее';
  onboardingNext.disabled = loading || busy || (!loadFailed && step.action === 'consent' && !model?.readiness?.briefing?.consent_text);
  onboardingSkip.hidden = loading || reviewMode || !model?.mandatory_complete || ![explanationIndex(), explanationIndex() + 1].includes(index);
  onboardingSkip.textContent = 'Перейти к готовности'; onboardingSkip.disabled = busy;
  document.getElementById('onboarding-home').disabled = loading || busy;
  featureList.querySelectorAll('[data-edit-answer]').forEach((button) => button.addEventListener('click', () => {
    if (busy || model?.mandatory_complete || reviewMode) return;
    editingFromSummary = true; errorMessage = ''; notice = '';
    state.onboardingIndex = 2 + Number(button.dataset.editAnswer); renderOnboarding({ focus: true });
  }));
  showMessages();
  if (focus) window.requestAnimationFrame(() => {
    const current = onboardingPanel.querySelector('.onboarding-copy');
    current.scrollIntoView({ block: 'start' });
    if (errorMessage) document.getElementById('onboarding-error').focus({ preventScroll: true });
    else if (step.answerKey && !busy) featureList.querySelector('textarea')?.focus({ preventScroll: true });
    else { onboardingTitle.tabIndex = -1; onboardingTitle.focus({ preventScroll: true }); }
  });
};

const beginPreparation = ({ retry = false } = {}) => {
  if (preparationTask?.generation === generation) return preparationTask.promise;
  const owner = identity(), epoch = state.identityEpoch, run = generation, scope = scopeKey;
  const current = () => isCurrent(owner, epoch, run) && scopeKey === scope && state.currentScreen === 'onboarding';
  const controller = new AbortController();
  const task = { generation: run, controller, promise: null };
  task.promise = (async () => {
    preparationError = null;
    try {
      const resolved = await api('/acquaintance/resolve-profile', { method: 'POST' });
      if (!current()) return;
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
      const prepared = accepted && !retry && accepted.status !== 'unknown'
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
      if (error.name === 'PreparationFailed') storeOperation({ operation_id: error.operationId, status: 'failed', error: error.operationError });
      renderOnboarding();
    } finally { if (preparationTask === task) preparationTask = null; }
  })();
  preparationTask = task;
  return task.promise;
};

export const openOnboarding = async ({ currentStep = 0, reviewMode: requestedReview = false } = {}) => {
  generation += 1; preparationTask?.controller.abort(); busy = false; progressTail = Promise.resolve();
  const owner = identity(), epoch = state.identityEpoch, run = generation;
  reviewMode = Boolean(requestedReview); errorMessage = ''; notice = ''; preparationError = null;
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
    state.onboardingIndex = reviewMode ? explanationIndex() : resumeOnboardingIndex(model, model.onboarding);
    if (!reviewMode && model.onboarding?.status === 'not_started') await saveProgress('in_progress');
  } catch (error) {
    if (!isCurrent(owner, epoch, run)) return;
    loadFailed = true; errorMessage = error.message;
  }
  if (!isCurrent(owner, epoch, run) || state.currentScreen !== 'onboarding') return;
  loading = false;
  persistAssessmentContext(); syncUrlState('onboarding'); renderOnboarding({ focus: true });
  if (!loadFailed && model?.mandatory_complete && !reviewMode) void beginPreparation();
};

export const goBackInOnboarding = () => {
  if (loading || busy || state.onboardingIndex <= 0) return;
  captureInput(); errorMessage = ''; notice = '';
  state.onboardingIndex = editingFromSummary ? summaryIndex() : state.onboardingIndex - 1;
  editingFromSummary = false; renderOnboarding({ focus: true });
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
      const { loadInterview } = await import('../screen-loaders.js');
      const interview = await loadInterview();
      if (isCurrent(owner, epoch, run)) await interview.handleAssessmentEntryClick();
      return;
    }
    if (step.answerKey) {
      if (model.mandatory_complete) { state.onboardingIndex += 1; return; }
      if (!String(answers[step.answerKey] || '').trim()) throw new Error('Напишите ответ. Если точного ответа нет, можно написать «Не знаю».');
      model.state = await api('/acquaintance/answers', { method: 'PUT', body: JSON.stringify({ answers: { [step.answerKey]: answers[step.answerKey] }, confirm: false }) });
      savedAnswers = { ...model.state.answers_json };
      state.onboardingIndex = editingFromSummary ? summaryIndex() : state.onboardingIndex + 1;
      editingFromSummary = false; persistProgress();
    } else if (step.action === 'consent') {
      model.state = await api('/acquaintance/consent', { method: 'POST', body: JSON.stringify({ version: model.readiness.briefing.consent_version }) });
      state.onboardingIndex += 1; persistProgress();
    } else if (step.action === 'confirm') {
      if (!model.mandatory_complete) {
        model.state = await api('/acquaintance/answers', { method: 'PUT', body: JSON.stringify({ answers, confirm: true }) });
        savedAnswers = { ...model.state.answers_json }; model.mandatory_complete = true;
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
    } else if (step.action === 'start') {
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
    if (isCurrent(owner, epoch, run)) errorMessage = error.message || 'Не удалось сохранить действие. Повторите попытку.';
  } finally {
    if (isCurrent(owner, epoch, run)) { busy = false; if (state.currentScreen === 'onboarding') renderOnboarding({ focus: true }); }
  }
};

export const initOnboarding = () => {
  onboardingNext.addEventListener('click', () => { void advance(); });
  onboardingStepBackButton.addEventListener('click', goBackInOnboarding);
  onboardingSkip.addEventListener('click', async () => {
    if (busy || reviewMode || !model?.mandatory_complete || ![explanationIndex(), explanationIndex() + 1].includes(state.onboardingIndex)) return;
    busy = true; renderOnboarding();
    const owner = identity(), epoch = state.identityEpoch, run = generation;
    try { await saveProgress('completed', readinessIndex()); state.onboardingIndex = readinessIndex(); void beginPreparation(); }
    catch (error) { if (isCurrent(owner, epoch, run)) errorMessage = error.message; }
    finally { if (isCurrent(owner, epoch, run)) { busy = false; renderOnboarding({ focus: true }); } }
  });
  document.getElementById('onboarding-home').addEventListener('click', async () => {
    if (busy) return;
    captureInput();
    if (Object.entries(answers).some(([key, value]) => value !== savedAnswers[key])) {
      notice = 'В поле есть неотправленный текст. Сохраните ответ перед переходом; текст оставлен здесь.'; showMessages(); return;
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
    } catch (error) { if (isCurrent(owner, epoch, run)) { errorMessage = error.message; showMessages(); } }
    finally { if (isCurrent(owner, epoch, run)) { busy = false; if (state.currentScreen === 'onboarding') renderOnboarding(); } }
  });
  window.addEventListener('agent4k:assessment-context-cleared', () => {
    generation += 1; preparationTask?.controller.abort(); preparationTask = null;
    progressTail = Promise.resolve();
    for (const key of operationKeys) { try { window.sessionStorage.removeItem(key); } catch { /* No storage access. */ } }
    operationKeys.clear(); model = null; answers = {}; savedAnswers = {}; scopeKey = ''; localOperation = null;
    busy = false; loading = false; errorMessage = ''; notice = ''; preparationError = null;
  });
};

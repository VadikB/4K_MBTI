import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import {
  stepBadgeLabel,
  onboardingTitle,
  onboardingDescription,
  featureList,
  onboardingVisual,
  onboardingNext,
  onboardingSkip,
  onboardingStepBackButton,
  onboardingPanel,
} from '../dom.js';
import { onboardingSteps } from '../config.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { openAiWelcome } from './ai-welcome.js';
import { readApiResponse } from '../api.js';
import { createOperationId } from '../api.js';
import { prepareProductCycle } from '../product-cycle-preparation.js';

let onboardingReviewMode = false;
let acquaintanceModel = null;
let acquaintanceAnswers = {};

const feature = (title, text) => ({ title, text, icon: '/web/assets/icons/file-icon.svg' });

const acquaintanceSteps = () => {
  const briefing = acquaintanceModel?.readiness?.briefing || {};
  const questions = Array.isArray(briefing.questions) ? briefing.questions : [];
  const provided = Array.isArray(briefing.provided_participant_fields) ? briefing.provided_participant_fields : [];
  const preparedPlanSnapshot = acquaintanceModel?.prepared_plan || null;
  const preparedPlan = preparedPlanSnapshot?.plan || preparedPlanSnapshot;
  const assignedTiming = acquaintanceModel?.assigned_timing?.status === 'resolved'
    ? acquaintanceModel.assigned_timing : null;
  const effectiveTiming = preparedPlan || assignedTiming;
  const calendarHours = effectiveTiming ? Math.ceil(Number(effectiveTiming.calendar_window_seconds || 0) / 3600) : 0;
  const returnCopy = preparedPlan?.return_policy_snapshot
    ? '\n\nЕсли прервать незавершённую ситуацию, при возвращении её содержание может обновиться. При этом ваше место в оценке сохранится — завершённые ситуации повторять не потребуется.'
    : '';
  const readyDescription = preparedPlan
    ? 'Вам предстоит разобраться в нескольких ситуациях. Опишите, как вы будете действовать, и поясните свои решения.\n\n' +
      'В некоторых ситуациях у вас будет собеседник. Если для решения не хватает информации, можно задать собеседнику вопрос.\n\n' +
      'Между ситуациями можно сделать перерыв. Завершите текущую ситуацию и переходите к следующей, когда будете готовы. Во время такого перерыва время на выполнение не расходуется, но общий срок завершения оценки продолжает идти.\n\n' +
      `Завершить оценку нужно в течение ${calendarHours} ч. после её начала.` + returnCopy
    : 'Система подготовит план и покажет фактические параметры до старта. Срок начнётся только после явного начала первой ситуации.';
  const planFeatures = preparedPlan ? [
    feature('Ситуации', String(Array.isArray(preparedPlan.route) ? preparedPlan.route.length : 0)),
    feature('Время на выполнение', `${Math.ceil(Number(preparedPlan.time_budget_seconds || 0) / 60)} мин.`),
  ] : [];
  const steps = [
    {
      step: 'Знакомство', progressIndex: 0,
      title: `Оценку организует ${briefing.organizer || acquaintanceModel?.readiness?.organization_name || 'ваша организация'}`,
      description: briefing.purpose || '',
      features: [feature('Как используются результаты', briefing.results_usage || ''),
        feature('Кто получит результаты', briefing.result_recipients || '')],
    },
    {
      step: 'Ваши данные', progressIndex: 0,
      title: 'Проверьте сведения перед продолжением',
      description: briefing.consent_text || 'Подтвердите согласие на использование указанных сведений в рамках оценки.',
      features: provided.map((item) => feature(String(item.label || 'Сведения'), String(item.value || ''))),
      finalButton: 'Согласен и продолжить', action: 'consent',
    },
    {
      step: 'О вашей работе', progressIndex: 1,
      title: 'Расскажите немного о своей работе',
      description: 'Это поможет нам подготовить ситуации, близкие к тем, с которыми вы сталкиваетесь.',
      features: [],
    },
    ...questions.map((question, index) => ({
      step: 'Ваш ответ', progressIndex: 1, title: question,
      description: 'Ответьте своими словами. Если точного ответа нет, можно написать «Не знаю».',
      features: [], answerKey: `answer_${index + 1}`, finalButton: 'Сохранить и продолжить',
    })),
    {
      step: 'Проверка', progressIndex: 1, title: 'Проверьте ваши ответы',
      description: 'До подтверждения можно вернуться и исправить только собственные ответы.',
      features: [], action: 'confirm', finalButton: 'Подтвердить',
    },
    {
      step: 'Модель 4К', progressIndex: 2, title: 'Что показывает оценка 4К',
      description: 'Оценка рассматривает четыре взаимосвязанные компетенции в практических ситуациях.',
      features: [
        feature('Критическое мышление', 'Помогает анализировать информацию, проверять основания и принимать взвешенные решения.'),
        feature('Креативность', 'Помогает находить новые варианты и работать с нестандартными ограничениями.'),
        feature('Коммуникация', 'Помогает ясно доносить позицию и учитывать адресата.'),
        feature('Командная работа', 'Помогает согласовывать действия, роли и общий результат.'),
      ],
    },
    {
      step: 'Перед началом', progressIndex: 2, title: 'Как будет проходить оценка',
      description: acquaintanceModel?.late_readiness?.status === 'ready_to_prepare'
        ? readyDescription
        : 'Ваши ответы сохранены. Организация ещё готовит исходные данные для оценки.',
      features: planFeatures, action: 'finish',
      finalButton: preparedPlan ? 'Приступить к оценке'
        : acquaintanceModel?.late_readiness?.status === 'ready_to_prepare' ? 'Перейти к готовности оценки' : 'Проверить готовность',
    },
  ];
  return steps;
};

const currentSteps = () => onboardingReviewMode ? onboardingSteps : acquaintanceSteps();

const loadAcquaintance = async () => {
  const response = await fetch('/users/' + state.pendingUser.id + '/acquaintance', { credentials: 'same-origin' });
  acquaintanceModel = await readApiResponse(response, 'Не удалось проверить готовность знакомства.');
  acquaintanceAnswers = { ...(acquaintanceModel.state?.answers_json || {}) };
};

const saveOnboardingState = async (status, currentStep = state.onboardingIndex) => {
  if (!state.pendingUser?.id) {
    return null;
  }
  const response = await fetch('/users/' + state.pendingUser.id + '/onboarding', {
    method: 'PUT',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      status,
      current_step: Math.max(0, Number(currentStep || 0)),
    }),
  });
  return readApiResponse(response, 'Не удалось сохранить состояние онбординга.');
};

export const renderOnboarding = () => {
  const steps = currentSteps();
  const step = steps[state.onboardingIndex];
  onboardingPanel.dataset.step = String(step.progressIndex + 1);
  stepBadgeLabel.textContent = step.step;
  if (onboardingStepBackButton) {
    onboardingStepBackButton.hidden = state.onboardingIndex === 0;
  }
  onboardingTitle.textContent = step.title;
  onboardingDescription.textContent = step.description;
  featureList.innerHTML = '';
  step.features.forEach((feature) => {
    const item = document.createElement('div');
    item.className = 'feature-item';
    const icon = document.createElement('span');
    icon.className = 'feature-icon';
    icon.setAttribute('aria-hidden', 'true');
    const image = document.createElement('img');
    image.src = feature.icon;
    image.alt = '';
    image.loading = 'eager';
    icon.appendChild(image);

    const title = document.createElement('strong');
    title.textContent = feature.title;

    const text = document.createElement('span');
    text.textContent = feature.text;

    item.append(icon, title, text);
    featureList.appendChild(item);
  });
  onboardingVisual.innerHTML = step.visual || '';
  if (step.answerKey) {
    const input = document.createElement('textarea');
    input.className = 'onboarding-answer';
    input.rows = 3;
    input.maxLength = 4000;
    input.setAttribute('aria-label', step.title);
    input.value = acquaintanceAnswers[step.answerKey] || '';
    input.addEventListener('input', () => { acquaintanceAnswers[step.answerKey] = input.value; });
    featureList.appendChild(input);
  }
  if (step.action === 'confirm') {
    Object.entries(acquaintanceAnswers).sort().forEach(([_key, value], index) => {
      const item = document.createElement('div');
      item.className = 'feature-item onboarding-answer-summary';
      const title = document.createElement('strong'); title.textContent = `Ответ ${index + 1}`;
      const text = document.createElement('span'); text.textContent = value;
      item.append(title, text); featureList.appendChild(item);
    });
  }
  if (step.action === 'consent' && !onboardingReviewMode) {
    const details = document.createElement('details');
    details.className = 'onboarding-data-issue';
    const summary = document.createElement('summary');
    summary.textContent = 'Сообщить о неточности';
    const input = document.createElement('textarea');
    input.rows = 2; input.maxLength = 2000;
    input.setAttribute('aria-label', 'Описание неточности');
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'ghost-button'; button.textContent = 'Передать ответственному';
    const status = document.createElement('span'); status.setAttribute('role', 'status');
    button.addEventListener('click', async () => {
      const message = input.value.trim(); if (!message) return;
      button.disabled = true;
      try {
        const response = await fetch('/users/' + state.pendingUser.id + '/acquaintance/issues', {
          method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message }),
        });
        await readApiResponse(response, 'Не удалось передать сообщение ответственному.');
        status.textContent = 'Сообщение сохранено и доступно ответственному вашей организации.';
      } catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    });
    details.append(summary, input, button, status); featureList.appendChild(details);
  }
  onboardingNext.innerHTML =
    '<span>' +
    (step.finalButton || 'Далее') +
    '</span><img class="button-arrow" src="/web/assets/icons/forward-arrow-white-icon.svg" alt="" aria-hidden="true">';
  window.scrollTo({ top: 0, left: 0 });
};

export const openOnboarding = async ({ currentStep = 0, reviewMode = false } = {}) => {
  onboardingReviewMode = Boolean(reviewMode);
  if (!onboardingReviewMode) await loadAcquaintance();
  const steps = currentSteps();
  state.onboardingIndex = Math.min(
    Math.max(0, Number(currentStep || 0)),
    Math.max(0, steps.length - 1),
  );
  state.onboardingShown = true;
  onboardingSkip.hidden = !onboardingReviewMode;
  if (!onboardingReviewMode) {
    try {
      await saveOnboardingState('in_progress', state.onboardingIndex);
    } catch (error) {
      console.error('Failed to persist onboarding start', error);
    }
  }
  setCurrentScreen('onboarding');
  persistAssessmentContext();
  renderOnboarding();
  hideAllPanels();
  onboardingPanel.classList.remove('hidden');
  syncUrlState('onboarding');
};

export const goBackInOnboarding = () => {
  if (state.onboardingIndex > 0) {
    state.onboardingIndex -= 1;
    renderOnboarding();
    return;
  }

  openAiWelcome();
};

export const initOnboarding = () => {
  onboardingNext.addEventListener('click', async () => {
    const steps = currentSteps();
    const step = steps[state.onboardingIndex];
    if (!onboardingReviewMode && step.answerKey) {
      const answer = String(acquaintanceAnswers[step.answerKey] || '').trim();
      if (!answer) return;
      const response = await fetch('/users/' + state.pendingUser.id + '/acquaintance/answers', {
        method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: { [step.answerKey]: answer }, confirm: false }),
      });
      await readApiResponse(response, 'Не удалось сохранить ответ. Текст оставлен в поле для повтора.');
    }
    if (!onboardingReviewMode && step.action === 'consent') {
      const response = await fetch('/users/' + state.pendingUser.id + '/acquaintance/consent', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: acquaintanceModel.readiness.briefing.consent_version }),
      });
      await readApiResponse(response, 'Не удалось сохранить согласие.');
    }
    if (!onboardingReviewMode && step.action === 'confirm') {
      const response = await fetch('/users/' + state.pendingUser.id + '/acquaintance/answers', {
        method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: acquaintanceAnswers, confirm: true }),
      });
      await readApiResponse(response, 'Не удалось подтвердить ответы.');
      await loadAcquaintance();
      if (acquaintanceModel.late_readiness?.status === 'ready_to_prepare' && !state.productCycleId) {
        const prepared = await prepareProductCycle({
          personalized_profile_id: acquaintanceModel.late_readiness.personalized_profile_id,
          idempotency_key: createOperationId(), selected_skills: ['K1', 'K2', 'K3', 'K4'],
        });
        state.assessmentRuntimeKind = 'cycle'; state.productCycleId = prepared.plan.cycle_id;
        acquaintanceModel.prepared_plan = {
          cycle_id: prepared.plan.cycle_id,
          revision_id: prepared.plan.revision_id,
          revision_no: prepared.plan.revision_no,
          plan: prepared.plan.plan,
        };
        persistAssessmentContext();
      }
    }
    if (!onboardingReviewMode && step.action === 'finish'
        && acquaintanceModel?.late_readiness?.status !== 'ready_to_prepare') {
      await loadAcquaintance();
      renderOnboarding();
      return;
    }
    if (state.onboardingIndex < steps.length - 1) {
      state.onboardingIndex += 1;
      renderOnboarding();
      if (!onboardingReviewMode) {
        try {
          await saveOnboardingState('in_progress');
        } catch (error) {
          console.error('Failed to persist onboarding progress', error);
        }
      }
      return;
    }

    if (onboardingReviewMode) {
      openAiWelcome();
      return;
    }

    try {
      await saveOnboardingState('completed');
    } catch (error) {
      console.error('Failed to persist onboarding completion', error);
      return;
    }
    await loadAcquaintance();
    openAiWelcome();
  });

  onboardingSkip.addEventListener('click', async () => {
    if (onboardingReviewMode) {
      openAiWelcome();
      return;
    }
    try {
      await saveOnboardingState('skipped');
    } catch (error) {
      console.error('Failed to persist onboarding skip', error);
      return;
    }
    openAiWelcome();
  });

  if (onboardingStepBackButton) {
    onboardingStepBackButton.addEventListener('click', goBackInOnboarding);
  }
};

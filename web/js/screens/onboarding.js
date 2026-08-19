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

let onboardingReviewMode = false;

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
  const step = onboardingSteps[state.onboardingIndex];
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
  onboardingVisual.innerHTML = step.visual;
  onboardingNext.innerHTML =
    '<span>' +
    (step.finalButton || 'Далее') +
    '</span><img class="button-arrow" src="/web/assets/icons/forward-arrow-white-icon.svg" alt="" aria-hidden="true">';
  window.scrollTo({ top: 0, left: 0 });
};

export const openOnboarding = async ({ currentStep = 0, reviewMode = false } = {}) => {
  onboardingReviewMode = Boolean(reviewMode);
  state.onboardingIndex = Math.min(
    Math.max(0, Number(currentStep || 0)),
    Math.max(0, onboardingSteps.length - 1),
  );
  state.onboardingShown = true;
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
    if (state.onboardingIndex < onboardingSteps.length - 1) {
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

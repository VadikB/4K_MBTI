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
import { hideAllPanels, syncUrlState, returnToStart } from '../router.js';
import { openAiWelcome } from './ai-welcome.js';

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

export const openOnboarding = () => {
  state.onboardingIndex = 0;
  state.onboardingShown = true;
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

  returnToStart();
};

export const initOnboarding = () => {
  onboardingNext.addEventListener('click', () => {
    if (state.onboardingIndex < onboardingSteps.length - 1) {
      state.onboardingIndex += 1;
      renderOnboarding();
      return;
    }

    openAiWelcome();
  });

  onboardingSkip.addEventListener('click', () => {
    returnToStart();
  });

  if (onboardingStepBackButton) {
    onboardingStepBackButton.addEventListener('click', goBackInOnboarding);
  }
};

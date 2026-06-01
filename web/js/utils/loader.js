import {
  appLoader,
  appLoaderTitle,
  appLoaderText,
  appLoaderProgressLabel,
  appLoaderProgressValue,
  appLoaderProgressBar,
  appLoaderSteps,
} from '../dom.js';

let loaderFlowTimerId = null;
let loaderFlowSteps = [];
let loaderFlowStepIndex = 0;
let loaderProgressPollId = null;
let loaderProgressValueOverride = null;

export const stopLoaderProgressPolling = () => {
  if (loaderProgressPollId) {
    window.clearInterval(loaderProgressPollId);
    loaderProgressPollId = null;
  }
};

export const clearLoaderFlowTimer = () => {
  if (loaderFlowTimerId) {
    window.clearInterval(loaderFlowTimerId);
    loaderFlowTimerId = null;
  }
};

export const renderLoaderFlow = () => {
  const totalSteps = loaderFlowSteps.length || 1;
  const activeIndex = Math.min(loaderFlowStepIndex, totalSteps - 1);
  const activeStep = loaderFlowSteps[activeIndex] || null;
  const progressValue =
    loaderProgressValueOverride == null
      ? Math.round(((activeIndex + 1) / totalSteps) * 100)
      : loaderProgressValueOverride;

  appLoaderProgressLabel.textContent = activeStep?.label || 'Подготовка';
  appLoaderProgressValue.textContent = progressValue + '%';
  appLoaderProgressBar.style.width = progressValue + '%';
  appLoaderSteps.innerHTML = '';

  loaderFlowSteps.forEach((step, index) => {
    const item = document.createElement('div');
    let statusClass = 'pending';
    let badgeLabel = String(index + 1);
    if (index < activeIndex) {
      statusClass = 'done';
      badgeLabel = '✓';
    } else if (index === activeIndex) {
      statusClass = 'active';
      badgeLabel = '•';
    }
    item.className = 'app-loader-step ' + statusClass;
    item.innerHTML =
      '<div class="app-loader-step-badge">' +
      badgeLabel +
      '</div>' +
      '<div class="app-loader-step-copy">' +
      '<strong>' +
      step.label +
      '</strong>' +
      '<span>' +
      step.description +
      '</span>' +
      '</div>';
    appLoaderSteps.appendChild(item);
  });
};

export const applyLoaderProgressSnapshot = (snapshot) => {
  if (!snapshot || !Array.isArray(snapshot.steps) || !snapshot.steps.length) {
    return;
  }
  appLoaderTitle.textContent = snapshot.title || appLoaderTitle.textContent;
  appLoaderText.textContent = snapshot.message || appLoaderText.textContent;
  loaderFlowSteps = snapshot.steps;
  loaderFlowStepIndex = Number(snapshot.current_step_index || 0);
  loaderProgressValueOverride = Number(snapshot.progress_percent || 0);
  clearLoaderFlowTimer();
  renderLoaderFlow();
};

export const startLoaderProgressPolling = (operationId) => {
  stopLoaderProgressPolling();
  if (!operationId) {
    return;
  }
  const poll = async () => {
    try {
      const response = await fetch('/users/operations/' + operationId, {
        credentials: 'same-origin',
      });
      if (!response.ok) {
        return;
      }
      const snapshot = await response.json();
      applyLoaderProgressSnapshot(snapshot);
      if (snapshot.status === 'completed' || snapshot.status === 'failed') {
        stopLoaderProgressPolling();
      }
    } catch (_error) {
      // ignore intermittent polling errors while the main request is still running
    }
  };
  void poll();
  loaderProgressPollId = window.setInterval(() => {
    void poll();
  }, 350);
};

export const showLoader = (title, text, steps = null) => {
  void title;
  void text;
  void steps;
  appLoader.classList.add('hidden');
};

export const hideLoader = () => {
  clearLoaderFlowTimer();
  stopLoaderProgressPolling();
  loaderFlowSteps = [];
  loaderFlowStepIndex = 0;
  loaderProgressValueOverride = null;
  appLoader.classList.add('hidden');
};

import { state, persistAssessmentContext } from '../../state.js';
import {
  adminPromptLabPanel,
  adminPromptLabSourceSelect,
  adminPromptLabPromptName,
  adminPromptLabPromptText,
  adminPromptLabUserSelect,
  adminPromptLabCaseSelect,
  adminPromptLabCasePickerButton,
  adminPromptLabCasePickerSummary,
  adminPromptLabCaseDialog,
  adminPromptLabCaseDialogClose,
  adminPromptLabCaseDialogList,
  adminPromptLabUserName,
  adminPromptLabRoleSelect,
  adminPromptLabPosition,
  adminPromptLabCompanyIndustry,
  adminPromptLabDuties,
  adminPromptLabProfileJson,
  adminPromptLabRunButton,
  adminPromptLabStatus,
  adminPromptLabProgress,
  adminPromptLabProgressTitle,
  adminPromptLabProgressValue,
  adminPromptLabProgressText,
  adminPromptLabProgressBar,
  adminPromptLabResult,
  adminPromptLabTabCasesButton,
  adminPromptLabTabDialogButton,
  adminPromptLabPaneCases,
  adminPromptLabPaneDialog,
  adminPromptLabDialogUserSelect,
  adminPromptLabDialogCaseSelect,
  adminPromptLabDialogCasePickerButton,
  adminPromptLabDialogCasePickerSummary,
  adminPromptLabDialogCaseDialog,
  adminPromptLabDialogCaseDialogClose,
  adminPromptLabDialogCaseDialogList,
  adminPromptLabDialogCaseHint,
  adminPromptLabDialogPrepareButton,
  adminPromptLabDialogStatus,
  adminPromptLabDialogCaseSourceSelect,
  adminPromptLabDialogCasePromptText,
  adminPromptLabDialogSourceSelect,
  adminPromptLabDialogPromptText,
  adminPromptLabDialogResult,
  adminPromptLabDialogUserMessage,
  adminPromptLabDialogSendButton,
  adminPromptLabDialogResetButton,
  adminPromptLabBackButton,
} from '../../dom.js';
import { escapeHtml, sanitizeDisplayRole, sanitizeDisplayMetaText, buildInitials } from '../../utils/format.js';
import { readApiResponse, createOperationId } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { setCurrentScreen } from '../../state.js';
export const stopAdminPromptLabPolling = () => {
  if (state.adminPromptLabPollId) {
    window.clearInterval(state.adminPromptLabPollId);
    state.adminPromptLabPollId = null;
  }
};

export const renderAdminPromptLabProgress = () => {
  if (!adminPromptLabProgress) {
    return;
  }
  const status = state.adminPromptLabProgressStatus;
  const visible = status === 'preparing' || status === 'failed' || status === 'ready';
  const progressPercent = Math.max(0, Math.min(100, Number(state.adminPromptLabProgressPercent || 0)));
  adminPromptLabProgress.classList.toggle('hidden', !visible);
  if (adminPromptLabProgressTitle) {
    adminPromptLabProgressTitle.textContent = state.adminPromptLabProgressTitle || 'Формируем кейсы';
  }
  if (adminPromptLabProgressValue) {
    adminPromptLabProgressValue.textContent = progressPercent + '%';
  }
  if (adminPromptLabProgressText) {
    adminPromptLabProgressText.textContent = state.adminPromptLabProgressMessage || 'Генерация кейсов выполняется.';
  }
  if (adminPromptLabProgressBar) {
    adminPromptLabProgressBar.style.width = progressPercent + '%';
  }
};

export const startAdminPromptLabPolling = (operationId) => {
  stopAdminPromptLabPolling();
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
      if (state.adminPromptLabOperationId !== operationId) {
        stopAdminPromptLabPolling();
        return;
      }
      state.adminPromptLabProgressPercent = Number(snapshot.progress_percent || 0);
      state.adminPromptLabProgressTitle = snapshot.title || 'Формируем кейсы';
      state.adminPromptLabProgressMessage = snapshot.message || 'Генерация кейсов выполняется.';
      if (snapshot.status === 'failed') {
        state.adminPromptLabProgressStatus = 'failed';
      } else if (snapshot.status === 'completed') {
        state.adminPromptLabProgressStatus = 'ready';
      } else {
        state.adminPromptLabProgressStatus = 'preparing';
      }
      renderAdminPromptLabProgress();
      if (snapshot.status === 'completed' || snapshot.status === 'failed') {
        stopAdminPromptLabPolling();
      }
    } catch (_error) {
      // keep prompt lab polling resilient to short polling failures
    }
  };
  void poll();
  state.adminPromptLabPollId = window.setInterval(() => {
    void poll();
  }, 500);
};

export const loadAdminPromptLab = async () => {
  const response = await fetch('/users/admin/prompt-lab', {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить Prompt Lab.');
  state.adminPromptLab = data;
  persistAssessmentContext();
};

export const loadPromptLabSystemCasePreview = async () => {
  const userId = Number(adminPromptLabUserSelect?.value || 0);
  const selectedCaseCodes = getSelectedPromptLabCaseCodes();
  const caseIdCode =
    selectedCaseCodes.find((code) => code && code !== '__all__') ||
    String(state.adminPromptLab?.cases?.[0]?.case_id_code || '').trim();
  if (!userId || !caseIdCode) {
    return;
  }
  const response = await fetch(
    '/users/admin/prompt-lab/system-case-preview?user_id=' +
      encodeURIComponent(userId) +
      '&case_id_code=' +
      encodeURIComponent(caseIdCode),
    { credentials: 'same-origin' },
  );
  const data = await readApiResponse(response, 'Не удалось загрузить кейс из системы.');
  state.adminPromptLabPreviewResult = {
    id: 'system-preview',
    total_cases: 1,
    user: data.user,
    case: data.case,
    case_items: [
      {
        ...data,
        case_number: 1,
        personalized_context: '',
        personalized_task: '',
        system_prompt: '',
      },
    ],
  };
};

export const setPromptLabStatus = (message, tone = 'muted') => {
  if (!adminPromptLabStatus) {
    return;
  }
  adminPromptLabStatus.textContent = message || '';
  adminPromptLabStatus.classList.toggle('hidden', !message);
  adminPromptLabStatus.dataset.tone = tone;
};

export const getSelectedPromptLabUser = () => {
  const userId = Number(adminPromptLabUserSelect?.value || 0);
  const users = Array.isArray(state.adminPromptLab?.users) ? state.adminPromptLab.users : [];
  return users.find((item) => Number(item.id) === userId) || null;
};

export const getSelectedPromptLabCaseCodes = () => {
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const availableCodes = new Set(cases.map((item) => String(item.case_id_code || '').trim()).filter(Boolean));
  const selectedCodes = Array.isArray(state.adminPromptLabSelectedCaseCodes)
    ? state.adminPromptLabSelectedCaseCodes
    : [];
  if (!selectedCodes.length) {
    return [];
  }
  if (selectedCodes.includes('__all__')) {
    return ['__all__'];
  }
  return selectedCodes.filter((code) => availableCodes.has(code));
};

export const setSelectedPromptLabCaseCodes = (codes) => {
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const availableCodes = new Set(cases.map((item) => String(item.case_id_code || '').trim()).filter(Boolean));
  const normalizedCodes = [];
  const seen = new Set();
  for (const rawCode of Array.isArray(codes) ? codes : []) {
    const code = String(rawCode || '').trim();
    if (!code || seen.has(code)) {
      continue;
    }
    if (code === '__all__') {
      state.adminPromptLabSelectedCaseCodes = ['__all__'];
      if (adminPromptLabCaseSelect) {
        Array.from(adminPromptLabCaseSelect.options).forEach((option) => {
          option.selected = option.value === '__all__';
        });
      }
      return;
    }
    if (!availableCodes.has(code)) {
      continue;
    }
    normalizedCodes.push(code);
    seen.add(code);
  }
  if (!normalizedCodes.length && cases.length) {
    const fallbackCode = String(cases[0].case_id_code || '').trim();
    state.adminPromptLabSelectedCaseCodes = fallbackCode ? [fallbackCode] : [];
  } else {
    state.adminPromptLabSelectedCaseCodes = normalizedCodes;
  }
  if (adminPromptLabCaseSelect) {
    const selectedSet = new Set(state.adminPromptLabSelectedCaseCodes);
    Array.from(adminPromptLabCaseSelect.options).forEach((option) => {
      option.selected = selectedSet.has(String(option.value || '').trim());
    });
  }
};

export const syncPromptLabCasePickerSummary = () => {
  if (!adminPromptLabCasePickerSummary) {
    return;
  }
  const selectedCodes = getSelectedPromptLabCaseCodes();
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  if (selectedCodes.includes('__all__')) {
    adminPromptLabCasePickerSummary.textContent = 'Выбраны все шаблоны кейсов';
    return;
  }
  if (!selectedCodes.length) {
    adminPromptLabCasePickerSummary.textContent = 'Кейсы не выбраны';
    return;
  }
  const selectedItems = cases.filter((item) => selectedCodes.includes(String(item.case_id_code || '').trim()));
  if (!selectedItems.length) {
    adminPromptLabCasePickerSummary.textContent = 'Выбрано кейсов: ' + selectedCodes.length;
    return;
  }
  if (selectedItems.length === 1) {
    const item = selectedItems[0];
    adminPromptLabCasePickerSummary.textContent = [item.case_id_code, item.title].filter(Boolean).join(' · ');
    return;
  }
  adminPromptLabCasePickerSummary.textContent = 'Выбрано кейсов: ' + selectedItems.length;
};

export const isPromptLabDialogCase = (item) => {
  if (!item || typeof item !== 'object') {
    return false;
  }
  if (item.is_dialog_case === true) {
    return true;
  }
  return /диалог/i.test(String(item.interactivity_mode || '').trim());
};

export const getPromptLabCaseModeLabel = (item) => {
  const mode = String(item?.interactivity_mode || '').trim();
  if (isPromptLabDialogCase(item)) {
    return 'Диалоговый';
  }
  return mode || '';
};

export const getPromptLabCaseModeTone = (item) => (isPromptLabDialogCase(item) ? 'dialog' : 'turn');

export const getPromptLabCaseOptionLabel = (item) => {
  const baseLabel = [item?.case_id_code, item?.type_code, item?.title].filter(Boolean).join(' · ');
  const modeLabel = getPromptLabCaseModeLabel(item);
  return modeLabel ? baseLabel + ' · ' + modeLabel : baseLabel;
};

export const syncPromptLabDialogCaseHint = () => {
  if (!adminPromptLabDialogCaseHint) {
    return;
  }
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const selectedCode = String(
    state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect?.value || '',
  ).trim();
  const selectedCase = cases.find((item) => String(item.case_id_code || '').trim() === selectedCode);
  const modeLabel = getPromptLabCaseModeLabel(selectedCase);
  if (!selectedCase || !modeLabel) {
    adminPromptLabDialogCaseHint.textContent = '';
    adminPromptLabDialogCaseHint.classList.add('hidden');
    adminPromptLabDialogCaseHint.classList.remove('is-dialog-case');
    adminPromptLabDialogCaseHint.classList.remove('is-turn-case');
    return;
  }
  adminPromptLabDialogCaseHint.textContent = isPromptLabDialogCase(selectedCase)
    ? 'Режим кейса: Диалоговый' +
      (String(selectedCase.interactivity_mode || '').trim()
        ? ' · ' + String(selectedCase.interactivity_mode || '').trim()
        : '')
    : 'Режим кейса: ' + modeLabel;
  adminPromptLabDialogCaseHint.classList.remove('hidden');
  adminPromptLabDialogCaseHint.classList.toggle('is-dialog-case', isPromptLabDialogCase(selectedCase));
  adminPromptLabDialogCaseHint.classList.toggle('is-turn-case', !!selectedCase && !isPromptLabDialogCase(selectedCase));
};

export const syncPromptLabDialogCasePickerSummary = () => {
  if (!adminPromptLabDialogCasePickerSummary) {
    return;
  }
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const selectedCode = String(
    state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect?.value || '',
  ).trim();
  const selectedCase = cases.find((item) => String(item.case_id_code || '').trim() === selectedCode);
  if (!selectedCase) {
    adminPromptLabDialogCasePickerSummary.textContent = 'Кейс не выбран';
    return;
  }
  adminPromptLabDialogCasePickerSummary.textContent = getPromptLabCaseOptionLabel(selectedCase);
};

export const getSelectedPromptLabDialogCase = () => {
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const selectedCode = String(
    state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect?.value || '',
  ).trim();
  return cases.find((item) => String(item.case_id_code || '').trim() === selectedCode) || null;
};

export const renderPromptLabDialogCaseDialog = () => {
  if (!adminPromptLabDialogCaseDialogList) {
    return;
  }
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const selectedCode = String(
    state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect?.value || '',
  ).trim();
  adminPromptLabDialogCaseDialogList.innerHTML = cases
    .map(
      (item) =>
        '<label class="admin-prompt-lab-case-option' +
        (isPromptLabDialogCase(item) ? ' is-dialog-case' : '') +
        '">' +
        '<input type="radio" name="admin-prompt-lab-dialog-case" value="' +
        escapeHtml(item.case_id_code) +
        '"' +
        (String(item.case_id_code || '').trim() === selectedCode ? ' checked' : '') +
        '>' +
        '<span class="admin-prompt-lab-case-option-copy">' +
        '<strong>' +
        escapeHtml(item.case_id_code || '') +
        ' · ' +
        escapeHtml(item.title || '') +
        '</strong>' +
        '<span class="admin-prompt-lab-case-option-meta">' +
        '<small>' +
        escapeHtml(item.type_code || '') +
        '</small>' +
        (getPromptLabCaseModeLabel(item)
          ? '<span class="admin-prompt-lab-case-badge ' +
            escapeHtml(getPromptLabCaseModeTone(item)) +
            '">' +
            escapeHtml(getPromptLabCaseModeLabel(item)) +
            '</span>'
          : '') +
        '</span>' +
        '</span>' +
        '</label>',
    )
    .join('');
};

export const syncPromptLabDialogCaseSelectionFromDialog = () => {
  if (!adminPromptLabDialogCaseDialogList || !adminPromptLabDialogCaseSelect) {
    return;
  }
  const selectedNode = adminPromptLabDialogCaseDialogList.querySelector('input[type="radio"]:checked');
  const selectedCode = String(selectedNode?.value || '').trim();
  if (!selectedCode) {
    return;
  }
  state.adminPromptLabDialogSelectedCaseCode = selectedCode;
  adminPromptLabDialogCaseSelect.value = selectedCode;
  syncPromptLabDialogCasePickerSummary();
  syncPromptLabDialogCaseHint();
};

export const renderPromptLabCaseDialog = () => {
  if (!adminPromptLabCaseDialogList) {
    return;
  }
  const cases = Array.isArray(state.adminPromptLab?.cases) ? state.adminPromptLab.cases : [];
  const selectedCodes = new Set(getSelectedPromptLabCaseCodes());
  adminPromptLabCaseDialogList.innerHTML =
    '<label class="admin-prompt-lab-case-option">' +
    '<input type="checkbox" value="__all__"' +
    (selectedCodes.has('__all__') ? ' checked' : '') +
    '>' +
    '<span class="admin-prompt-lab-case-option-copy">' +
    '<strong>Все шаблоны кейсов</strong>' +
    '<small>Сгенерировать кейсы по всему набору шаблонов, доступному в системе</small>' +
    '</span>' +
    '</label>' +
    cases
      .map(
        (item) =>
          '<label class="admin-prompt-lab-case-option' +
          (isPromptLabDialogCase(item) ? ' is-dialog-case' : '') +
          '">' +
          '<input type="checkbox" value="' +
          escapeHtml(item.case_id_code) +
          '"' +
          (selectedCodes.has(String(item.case_id_code || '').trim()) ? ' checked' : '') +
          '>' +
          '<span class="admin-prompt-lab-case-option-copy">' +
          '<strong>' +
          escapeHtml(item.case_id_code || '') +
          ' · ' +
          escapeHtml(item.title || '') +
          '</strong>' +
          '<span class="admin-prompt-lab-case-option-meta">' +
          '<small>' +
          escapeHtml(item.type_code || '') +
          '</small>' +
          (getPromptLabCaseModeLabel(item)
            ? '<span class="admin-prompt-lab-case-badge ' +
              escapeHtml(getPromptLabCaseModeTone(item)) +
              '">' +
              escapeHtml(getPromptLabCaseModeLabel(item)) +
              '</span>'
            : '') +
          '</span>' +
          '</span>' +
          '</label>',
      )
      .join('');
};

export const syncPromptLabCaseSelectionFromDialog = () => {
  if (!adminPromptLabCaseDialogList) {
    return;
  }
  let selectedCodes = Array.from(adminPromptLabCaseDialogList.querySelectorAll('input[type="checkbox"]:checked'))
    .map((node) => String(node.value || '').trim())
    .filter(Boolean);
  if (selectedCodes.includes('__all__')) {
    selectedCodes = ['__all__'];
    Array.from(adminPromptLabCaseDialogList.querySelectorAll('input[type="checkbox"]')).forEach((node) => {
      node.checked = String(node.value || '').trim() === '__all__';
    });
  }
  setSelectedPromptLabCaseCodes(selectedCodes);
  syncPromptLabCasePickerSummary();
};

export const getPromptLabProductionPromptText = () => String(state.adminPromptLab?.production_prompt_text || '').trim();

export const getPromptLabProductionPromptVersion = () => {
  const version = state.adminPromptLab?.production_instruction_version;
  if (version === null || version === undefined || version === '') {
    return '';
  }
  return 'v' + String(version);
};

let promptLabLastSourceMode = null;
let promptLabCustomPromptDirty = false;
let promptLabProfileDirty = false;
let promptLabLastUserId = null;
let promptLabDialogCasePromptDirty = false;
let promptLabDialogCasePromptSourceMode = null;
let promptLabDialogPromptDirty = false;

export const markPromptLabCustomPromptDirty = () => {
  promptLabCustomPromptDirty = true;
};

export const markPromptLabProfileDirty = () => {
  promptLabProfileDirty = true;
};

export const markPromptLabDialogCasePromptDirty = () => {
  promptLabDialogCasePromptDirty = true;
};

export const markPromptLabDialogPromptDirty = () => {
  promptLabDialogPromptDirty = true;
};

export const syncPromptLabDialogCasePromptSource = () => {
  const useSystemPrompt = (adminPromptLabDialogCaseSourceSelect?.value || 'system') === 'system';
  const currentSourceMode = useSystemPrompt ? 'system' : 'custom';
  const systemText = getPromptLabProductionPromptText();
  if (!adminPromptLabDialogCasePromptText) {
    return;
  }
  adminPromptLabDialogCasePromptText.readOnly = useSystemPrompt;
  adminPromptLabDialogCasePromptText.closest?.('.admin-prompt-lab-field')?.classList.toggle('muted', useSystemPrompt);
  if (useSystemPrompt) {
    adminPromptLabDialogCasePromptText.value = systemText;
    promptLabDialogCasePromptDirty = false;
    promptLabDialogCasePromptSourceMode = currentSourceMode;
    return;
  }
  const sourceChanged = promptLabDialogCasePromptSourceMode !== currentSourceMode;
  if (sourceChanged || !promptLabDialogCasePromptDirty) {
    adminPromptLabDialogCasePromptText.value = systemText;
    promptLabDialogCasePromptDirty = false;
  }
  promptLabDialogCasePromptSourceMode = currentSourceMode;
};

export const syncPromptLabDialogPromptSource = () => {
  const useSystemPrompt = (adminPromptLabDialogSourceSelect?.value || 'system') === 'system';
  const systemText = String(
    state.adminPromptLabDialogPreview?.interviewer_prompt_text || state.adminPromptLab?.interviewer_prompt_text || '',
  ).trim();
  if (!adminPromptLabDialogPromptText) {
    return;
  }
  adminPromptLabDialogPromptText.readOnly = useSystemPrompt;
  adminPromptLabDialogPromptText.closest?.('.admin-prompt-lab-field')?.classList.toggle('muted', useSystemPrompt);
  if (useSystemPrompt) {
    adminPromptLabDialogPromptText.value = systemText;
    promptLabDialogPromptDirty = false;
    return;
  }
  if (!promptLabDialogPromptDirty) {
    adminPromptLabDialogPromptText.value = systemText;
  }
};

export const setPromptLabTab = (tabKey) => {
  const nextTab = tabKey === 'dialog' ? 'dialog' : 'cases';
  state.adminPromptLabTab = nextTab;
  if (adminPromptLabTabCasesButton) {
    adminPromptLabTabCasesButton.classList.toggle('is-active', nextTab === 'cases');
    adminPromptLabTabCasesButton.setAttribute('aria-selected', nextTab === 'cases' ? 'true' : 'false');
  }
  if (adminPromptLabTabDialogButton) {
    adminPromptLabTabDialogButton.classList.toggle('is-active', nextTab === 'dialog');
    adminPromptLabTabDialogButton.setAttribute('aria-selected', nextTab === 'dialog' ? 'true' : 'false');
  }
  if (adminPromptLabPaneCases) {
    adminPromptLabPaneCases.classList.toggle('hidden', nextTab !== 'cases');
  }
  if (adminPromptLabPaneDialog) {
    adminPromptLabPaneDialog.classList.toggle('hidden', nextTab !== 'dialog');
  }
};

export const normalizePromptLabProfileValue = (value) => {
  if (Array.isArray(value)) {
    const seen = new Set();
    const normalizedItems = value
      .map((item) => (typeof item === 'string' ? item.trim() : item))
      .filter((item) => {
        if (item === null || item === undefined) {
          return false;
        }
        if (typeof item === 'string') {
          if (!item) {
            return false;
          }
          const key = item.toLowerCase();
          if (seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        }
        return true;
      });
    return normalizedItems.length ? normalizedItems : null;
  }
  if (value && typeof value === 'object') {
    const normalizedObject = Object.entries(value).reduce((accumulator, [key, nestedValue]) => {
      const normalizedNestedValue = normalizePromptLabProfileValue(nestedValue);
      if (
        normalizedNestedValue === null ||
        normalizedNestedValue === undefined ||
        normalizedNestedValue === '' ||
        (Array.isArray(normalizedNestedValue) && !normalizedNestedValue.length) ||
        (typeof normalizedNestedValue === 'object' &&
          !Array.isArray(normalizedNestedValue) &&
          !Object.keys(normalizedNestedValue).length)
      ) {
        return accumulator;
      }
      accumulator[key] = normalizedNestedValue;
      return accumulator;
    }, {});
    return Object.keys(normalizedObject).length ? normalizedObject : null;
  }
  if (typeof value === 'string') {
    const trimmedValue = value.trim();
    return trimmedValue || null;
  }
  return value ?? null;
};

export const buildPromptLabDutiesText = (user) => {
  if (!user) {
    return '';
  }
  const profileTasks = Array.isArray(user.user_profile?.user_tasks)
    ? user.user_profile.user_tasks.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  if (profileTasks.length) {
    return profileTasks.map((item) => '- ' + item).join('\n');
  }
  return String(user.duties || '').trim();
};

export const buildPromptLabProfileJson = (user) => {
  if (!user || !user.user_profile || typeof user.user_profile !== 'object') {
    return '{}';
  }
  const fullProfile = normalizePromptLabProfileValue(user.user_profile);
  return JSON.stringify(fullProfile || {}, null, 2);
};

export const fillPromptLabProfileFromUser = (user) => {
  if (!user) {
    return;
  }
  if (adminPromptLabUserName) {
    adminPromptLabUserName.value = user.full_name || '';
  }
  if (adminPromptLabRoleSelect) {
    adminPromptLabRoleSelect.value = user.role_id ? String(user.role_id) : '';
  }
  if (adminPromptLabPosition) {
    adminPromptLabPosition.value = user.position || '';
  }
  if (adminPromptLabCompanyIndustry) {
    adminPromptLabCompanyIndustry.value = user.company_industry || '';
  }
  if (adminPromptLabDuties) {
    adminPromptLabDuties.value = buildPromptLabDutiesText(user);
  }
  if (adminPromptLabProfileJson) {
    adminPromptLabProfileJson.value = buildPromptLabProfileJson(user);
  }
  promptLabProfileDirty = false;
  promptLabLastUserId = Number(user.id || 0) || null;
};

export const syncPromptLabPromptSource = () => {
  const useFilePrompt = (adminPromptLabSourceSelect?.value || 'file') === 'file';
  const currentSourceMode = useFilePrompt ? 'file' : 'custom';
  const productionPromptText = getPromptLabProductionPromptText();
  const productionPromptVersion = getPromptLabProductionPromptVersion();
  const promptNameField = adminPromptLabPromptName?.closest?.('.admin-prompt-lab-field') || null;
  const promptNameLabel = promptNameField?.querySelector?.('span') || null;
  const sourceChanged = promptLabLastSourceMode !== currentSourceMode;
  [adminPromptLabPromptName, adminPromptLabPromptText].forEach((node) => {
    if (!node) {
      return;
    }
    node.disabled = useFilePrompt;
    node.closest?.('.admin-prompt-lab-field')?.classList.toggle('muted', useFilePrompt);
  });
  if (useFilePrompt) {
    promptNameField?.classList.remove('hidden');
    if (promptNameLabel) {
      promptNameLabel.textContent = 'Версия промта';
    }
    if (adminPromptLabPromptName) {
      adminPromptLabPromptName.value = productionPromptVersion;
    }
    if (adminPromptLabPromptText) {
      adminPromptLabPromptText.value = productionPromptText;
    }
    promptLabCustomPromptDirty = false;
    promptLabLastSourceMode = currentSourceMode;
    return;
  }
  promptNameField?.classList.add('hidden');
  if (promptNameLabel) {
    promptNameLabel.textContent = 'Название версии';
  }
  const shouldHydrateCustomPrompt = sourceChanged || !promptLabCustomPromptDirty;
  if (shouldHydrateCustomPrompt) {
    if (adminPromptLabPromptName) {
      adminPromptLabPromptName.value = 'Пользовательский промт';
    }
    if (adminPromptLabPromptText && sourceChanged) {
      adminPromptLabPromptText.value = productionPromptText;
    }
    promptLabCustomPromptDirty = false;
  }
  promptLabLastSourceMode = currentSourceMode;
};

export const renderAdminPromptLab = () => {
  const data = state.adminPromptLab || {};
  const users = Array.isArray(data.users) ? data.users : [];
  const cases = Array.isArray(data.cases) ? data.cases : [];
  const roles = Array.isArray(data.role_options) ? data.role_options : [];

  if (adminPromptLabUserSelect) {
    const currentValue = adminPromptLabUserSelect.value;
    adminPromptLabUserSelect.innerHTML = users
      .map((item) => {
        const label = [item.full_name || 'User #' + item.id, item.role_name, item.position].filter(Boolean).join(' · ');
        return '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(label) + '</option>';
      })
      .join('');
    if (currentValue && users.some((item) => String(item.id) === currentValue)) {
      adminPromptLabUserSelect.value = currentValue;
    } else if (users.length) {
      adminPromptLabUserSelect.value = String(users[0].id);
    }
  }

  if (adminPromptLabRoleSelect) {
    const currentValue = adminPromptLabRoleSelect.value;
    adminPromptLabRoleSelect.innerHTML = roles
      .map((item) => '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(item.name) + '</option>')
      .join('');
    if (currentValue) {
      adminPromptLabRoleSelect.value = currentValue;
    }
  }

  const selectedUser = getSelectedPromptLabUser();
  const selectedUserId = selectedUser ? Number(selectedUser.id || 0) || null : null;
  if (selectedUser && (selectedUserId !== promptLabLastUserId || !promptLabProfileDirty)) {
    fillPromptLabProfileFromUser(selectedUser);
  }

  if (adminPromptLabCaseSelect) {
    adminPromptLabCaseSelect.innerHTML =
      '<option value="__all__">Все шаблоны кейсов</option>' +
      cases
        .map((item) => {
          const label = [item.case_id_code, item.type_code, item.title].filter(Boolean).join(' · ');
          return '<option value="' + escapeHtml(item.case_id_code) + '">' + escapeHtml(label) + '</option>';
        })
        .join('');
    if (!state.adminPromptLabSelectedCaseCodes.length && cases.length) {
      setSelectedPromptLabCaseCodes([String(cases[0].case_id_code || '').trim()]);
    } else {
      setSelectedPromptLabCaseCodes(getSelectedPromptLabCaseCodes());
    }
  }

  if (adminPromptLabDialogUserSelect) {
    const currentValue = adminPromptLabDialogUserSelect.value;
    adminPromptLabDialogUserSelect.innerHTML = users
      .map((item) => {
        const label = [item.full_name || 'User #' + item.id, item.role_name, item.position].filter(Boolean).join(' · ');
        return '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(label) + '</option>';
      })
      .join('');
    if (currentValue && users.some((item) => String(item.id) === currentValue)) {
      adminPromptLabDialogUserSelect.value = currentValue;
    } else if (users.length) {
      adminPromptLabDialogUserSelect.value = String(users[0].id);
    }
  }

  if (adminPromptLabDialogCaseSelect) {
    const currentValue = String(
      state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect.value || '',
    ).trim();
    adminPromptLabDialogCaseSelect.innerHTML = cases
      .map((item) => {
        const label = [item.case_id_code, item.type_code, item.title].filter(Boolean).join(' · ');
        return '<option value="' + escapeHtml(item.case_id_code) + '">' + escapeHtml(label) + '</option>';
      })
      .join('');
    if (currentValue && cases.some((item) => String(item.case_id_code) === currentValue)) {
      adminPromptLabDialogCaseSelect.value = currentValue;
      state.adminPromptLabDialogSelectedCaseCode = currentValue;
    } else if (cases.length) {
      adminPromptLabDialogCaseSelect.value = String(cases[0].case_id_code || '');
      state.adminPromptLabDialogSelectedCaseCode = String(cases[0].case_id_code || '');
    }
  }

  renderPromptLabCaseDialog();
  syncPromptLabCasePickerSummary();
  renderPromptLabDialogCaseDialog();
  syncPromptLabDialogCasePickerSummary();
  syncPromptLabDialogCaseHint();

  if (adminPromptLabRunButton) {
    adminPromptLabRunButton.disabled = state.adminPromptLabRunning || !users.length || !cases.length;
  }
  if (adminPromptLabDialogPrepareButton) {
    adminPromptLabDialogPrepareButton.disabled = state.adminPromptLabDialogRunning || !users.length || !cases.length;
  }
  if (adminPromptLabDialogSendButton) {
    adminPromptLabDialogSendButton.disabled = state.adminPromptLabDialogRunning || !state.adminPromptLabDialogPrepared;
  }
  if (adminPromptLabDialogUserMessage) {
    adminPromptLabDialogUserMessage.disabled = state.adminPromptLabDialogRunning || !state.adminPromptLabDialogPrepared;
  }
  syncPromptLabPromptSource();
  if (adminPromptLabDialogCasePromptText) {
    if (!promptLabDialogCasePromptDirty || (adminPromptLabDialogCaseSourceSelect?.value || 'system') === 'system') {
      adminPromptLabDialogCasePromptText.value = getPromptLabProductionPromptText();
    }
  }
  syncPromptLabDialogCasePromptSource();
  if (adminPromptLabDialogPromptText) {
    if (!promptLabDialogPromptDirty || (adminPromptLabDialogSourceSelect?.value || 'system') === 'system') {
      adminPromptLabDialogPromptText.value = String(data.interviewer_prompt_text || '').trim();
    }
  }
  syncPromptLabDialogPromptSource();
  setPromptLabTab(state.adminPromptLabTab);
  renderAdminPromptLabProgress();
  renderAdminPromptLabDialogResult();
};

export const setPromptLabDialogStatus = (message, tone = 'muted') => {
  if (!adminPromptLabDialogStatus) {
    return;
  }
  adminPromptLabDialogStatus.textContent = message || '';
  adminPromptLabDialogStatus.classList.toggle('hidden', !message);
  adminPromptLabDialogStatus.dataset.tone = tone;
};

export const getPromptLabDialogMethodicalSummary = (preview) => {
  const context = preview?.methodical_context || {};
  const rows = [
    ['Интерактивность', context.interactivity_mode],
    ['Контроль формата ответа', context.format_control_rules],
    ['Рекомендуемая длина ответа', context.recommended_answer_length],
    ['Ожидаемый артефакт', context.artifact_name],
  ].filter((item) => String(item[1] || '').trim());
  return rows.map(([label, value]) => label + ': ' + String(value || '').trim()).join('\n');
};

export const getPromptLabDialogPreviewCaseCode = (preview) => String(preview?.case?.case_id_code || '').trim();

export const isPromptLabDialogPreviewDialogCase = (preview) =>
  preview?.is_dialog_case === true ||
  isPromptLabDialogCase(preview?.case) ||
  /диалог/i.test(String(preview?.methodical_context?.interactivity_mode || '').trim());

export const getPromptLabDialogEffectiveCaseGenerationPromptText = (preview) => {
  const sourceMode = String(adminPromptLabDialogCaseSourceSelect?.value || 'system').trim();
  if (sourceMode === 'custom') {
    return String(adminPromptLabDialogCasePromptText?.value || '').trim();
  }
  return String(
    preview?.case_generation_prompt_text ||
      state.adminPromptLab?.production_prompt_text ||
      adminPromptLabDialogCasePromptText?.value ||
      '',
  ).trim();
};

export const getPromptLabDialogCaseGenerationPromptBlockTitle = () => {
  const sourceMode = String(adminPromptLabDialogCaseSourceSelect?.value || 'system').trim();
  return sourceMode === 'custom'
    ? 'Пользовательский промт персонализации кейса'
    : 'Системный промт персонализации кейса';
};

export const getPromptLabDialogEffectivePromptText = (preview) => {
  const sourceMode = String(adminPromptLabDialogSourceSelect?.value || 'system').trim();
  if (sourceMode === 'custom') {
    return String(adminPromptLabDialogPromptText?.value || '').trim();
  }
  return String(
    preview?.interviewer_prompt_text ||
      state.adminPromptLab?.interviewer_prompt_text ||
      adminPromptLabDialogPromptText?.value ||
      '',
  ).trim();
};

export const getPromptLabDialogPromptBlockTitle = () => {
  const sourceMode = String(adminPromptLabDialogSourceSelect?.value || 'system').trim();
  return sourceMode === 'custom' ? 'Пользовательский промт интервьюера' : 'Системный промт интервьюера';
};

export const getPromptLabDialogHistorySpeakerLabel = (item, preview) => {
  if (item?.kind === 'opening') {
    return 'Сценарий кейса';
  }
  if (item?.kind === 'counterpart_opening') {
    return 'Собеседник';
  }
  if (item?.role === 'user') {
    return 'Пользователь';
  }
  if (isPromptLabDialogPreviewDialogCase(preview)) {
    return 'Собеседник';
  }
  return 'Агент интервьюер';
};

export const renderPromptLabDialogueHistory = (history, preview) =>
  '<section class="admin-prompt-lab-output-block">' +
  '<h4>' +
  escapeHtml(isPromptLabDialogPreviewDialogCase(preview) ? 'Диалог' : 'Ответ пользователя') +
  '</h4>' +
  '<div class="admin-prompt-lab-dialog-history">' +
  history
    .map(
      (item) =>
        '<article class="admin-prompt-lab-dialog-message role-' +
        escapeHtml(item.role || 'assistant') +
        '">' +
        '<strong>' +
        escapeHtml(getPromptLabDialogHistorySpeakerLabel(item, preview)) +
        '</strong>' +
        '<pre>' +
        escapeHtml(item.content || '') +
        '</pre>' +
        '</article>',
    )
    .join('') +
  '</div>' +
  '</section>';

export const renderAdminPromptLabDialogResult = () => {
  if (!adminPromptLabDialogResult) {
    return;
  }
  const preview = state.adminPromptLabDialogPreview;
  const selectedCase = getSelectedPromptLabDialogCase();
  const selectedCaseCode = String(selectedCase?.case_id_code || '').trim();
  const previewCaseCode = getPromptLabDialogPreviewCaseCode(preview);
  if (!preview) {
    if (state.adminPromptLabDialogRunning) {
      adminPromptLabDialogResult.innerHTML =
        '<p class="report-empty-state">Готовим диалог для <strong>' +
        escapeHtml(selectedCaseCode || 'выбранного кейса') +
        '</strong>. Для диалоговых кейсов подготовка может занять до 20–30 секунд.</p>';
      return;
    }
    adminPromptLabDialogResult.innerHTML =
      '<p class="report-empty-state">Подготовьте диалог, чтобы увидеть персонализированный кейс и ответ агента.</p>';
    return;
  }
  if (selectedCaseCode && previewCaseCode && selectedCaseCode !== previewCaseCode) {
    adminPromptLabDialogResult.innerHTML =
      '<p class="report-empty-state">Выбран новый кейс <strong>' +
      escapeHtml(selectedCaseCode) +
      '</strong>. Нажмите «Подготовить диалог», чтобы обновить результат.</p>';
    if (adminPromptLabDialogSendButton) {
      adminPromptLabDialogSendButton.disabled = true;
    }
    if (adminPromptLabDialogUserMessage) {
      adminPromptLabDialogUserMessage.disabled = true;
    }
    return;
  }
  const history = Array.isArray(state.adminPromptLabDialogHistory) ? state.adminPromptLabDialogHistory : [];
  const isCompleted = history.some(
    (item) =>
      String(item.content || '').trim() ===
      'Лимит сообщений по этому кейсу достигнут. Мы фиксируем ваш ответ и завершаем кейс.',
  );
  const effectiveCaseGenerationPromptText = getPromptLabDialogEffectiveCaseGenerationPromptText(preview);
  const effectivePromptText = getPromptLabDialogEffectivePromptText(preview);
  adminPromptLabDialogResult.innerHTML =
    '<div class="admin-prompt-lab-result-summary">' +
    '<span>Подготовлен диалог для</span>' +
    '<strong>' +
    escapeHtml(previewCaseCode || 'неизвестного кейса') +
    '</strong>' +
    '<span>' +
    escapeHtml(preview?.case?.title || '') +
    '</span>' +
    '</div>' +
    renderPromptLabTextBlock(
      'Сгенерированный кейс',
      buildPromptLabCaseText(preview.personalized_context, preview.personalized_task),
    ) +
    renderPromptLabTextBlock(
      getPromptLabDialogCaseGenerationPromptBlockTitle(),
      effectiveCaseGenerationPromptText || 'Промт персонализации кейса не задан.',
    ) +
    renderPromptLabTextBlock(
      getPromptLabDialogPromptBlockTitle(),
      effectivePromptText || 'Промт интервьюера не задан.',
    ) +
    renderPromptLabTextBlock(
      'Требования к ответу',
      getPromptLabDialogMethodicalSummary(preview) || 'Методические требования не заданы.',
    ) +
    (history.length ? renderPromptLabDialogueHistory(history, preview) : '');
  if (adminPromptLabDialogSendButton) {
    adminPromptLabDialogSendButton.disabled =
      state.adminPromptLabDialogRunning || !state.adminPromptLabDialogPrepared || isCompleted;
  }
  if (adminPromptLabDialogUserMessage) {
    adminPromptLabDialogUserMessage.disabled =
      state.adminPromptLabDialogRunning || !state.adminPromptLabDialogPrepared || isCompleted;
  }
};

export const renderPromptLabTextBlock = (title, value) =>
  '<section class="admin-prompt-lab-output-block">' +
  '<h4>' +
  escapeHtml(title) +
  '</h4>' +
  '<pre>' +
  escapeHtml(typeof value === 'string' ? value : JSON.stringify(value || {}, null, 2)) +
  '</pre>' +
  '</section>';

export const renderPromptLabCaseQualityBlock = (quality) => {
  const data = quality && typeof quality === 'object' ? quality : null;
  if (!data || !Object.keys(data).length) {
    return '';
  }
  const metrics = [
    ['Общий балл', data.case_text_quality_score, 5],
    ['Точность к шаблону', data.template_fidelity_score, 5],
    ['Персонализация', data.personalization_score, 5],
    ['Конкретность', data.concreteness_score, 5],
    ['Читаемость', data.readability_score, 5],
    ['Разнообразие', data.diversity_score, 5],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '');
  const issues = Array.isArray(data.quality_issues) ? data.quality_issues : [];
  const strengths = Array.isArray(data.quality_strengths) ? data.quality_strengths : [];
  const metricsHtml = metrics.length
    ? '<div class="admin-prompt-lab-result-summary">' +
      metrics
        .map(
          ([label, value, maxValue]) =>
            '<span><strong>' +
            escapeHtml(label) +
            ':</strong> ' +
            escapeHtml(String(value)) +
            '/' +
            escapeHtml(String(maxValue)) +
            '</span>',
        )
        .join('') +
      '</div>'
    : '';
  return (
    '<section class="admin-prompt-lab-output-block">' + '<h4>Метрики качества кейса</h4>' + metricsHtml + '</section>'
  );
};

export const buildPromptLabCaseText = (context, task) => {
  const normalizedContext = String(context || '').trim();
  const normalizedTask = String(task || '').trim();
  if (!normalizedContext && !normalizedTask) {
    return 'Для этого пользователя по этому шаблону в системе пока нет сохраненного персонализированного кейса.';
  }
  return ['Ситуация', normalizedContext, 'Что нужно сделать', normalizedTask].filter(Boolean).join('\n\n');
};

export const renderAdminPromptLabResult = () => {
  const result = state.adminPromptLabResult || state.adminPromptLabPreviewResult;
  if (!adminPromptLabResult || !result) {
    return;
  }
  const caseItems = Array.isArray(result.case_items) && result.case_items.length ? result.case_items : [result];
  const taskBlocks = caseItems
    .map(
      (item, index) =>
        '<article class="card admin-prompt-lab-task-card">' +
        '<div class="admin-prompt-lab-task-head">' +
        '<span>Задача ' +
        escapeHtml(item.case_number || index + 1) +
        ' из ' +
        escapeHtml(result.total_cases || caseItems.length) +
        '</span>' +
        '<strong>' +
        escapeHtml(item.case?.case_id_code || '') +
        ' · ' +
        escapeHtml(item.case?.title || '') +
        '</strong>' +
        '</div>' +
        '<div class="admin-prompt-lab-case-compare">' +
        renderPromptLabTextBlock('Шаблон кейса', buildPromptLabCaseText(item.base_context, item.base_task)) +
        (item.personalized_context || item.personalized_task
          ? renderPromptLabTextBlock(
              'Сгенерированный кейс',
              buildPromptLabCaseText(item.personalized_context, item.personalized_task),
            )
          : '') +
        '</div>' +
        renderPromptLabCaseQualityBlock(item.case_quality) +
        '</article>',
    )
    .join('');
  adminPromptLabResult.innerHTML =
    '<div class="admin-prompt-lab-result-summary">' +
    '<span>Run #' +
    escapeHtml(result.id) +
    '</span>' +
    '<strong>' +
    escapeHtml(result.total_cases || caseItems.length) +
    ' кейсов</strong>' +
    '<span>' +
    escapeHtml(result.user?.full_name || 'Пользователь') +
    '</span>' +
    '</div>' +
    taskBlocks;
};

export const runAdminPromptLabCase = async () => {
  const userId = Number(adminPromptLabUserSelect?.value || 0);
  const selectedCaseCodes = getSelectedPromptLabCaseCodes();
  const promptSource = adminPromptLabSourceSelect?.value || 'file';
  const promptName = adminPromptLabPromptName?.value?.trim() || 'Case prompt experiment';
  const promptText = adminPromptLabPromptText?.value?.trim() || '';
  const fullName = adminPromptLabUserName?.value?.trim() || null;
  const roleId = Number(adminPromptLabRoleSelect?.value || 0) || null;
  const position = adminPromptLabPosition?.value?.trim() || null;
  const duties = adminPromptLabDuties?.value?.trim() || null;
  const companyIndustry = adminPromptLabCompanyIndustry?.value?.trim() || null;
  let userProfile = null;
  const rawProfileJson = adminPromptLabProfileJson?.value?.trim() || '';
  if (rawProfileJson) {
    try {
      userProfile = JSON.parse(rawProfileJson);
    } catch (_error) {
      setPromptLabStatus('Расширенный профиль должен быть корректным JSON.', 'error');
      return;
    }
  }
  if (!userId || !selectedCaseCodes.length || (promptSource === 'custom' && !promptText)) {
    setPromptLabStatus('Выберите пользователя, хотя бы один кейс и заполните промт.', 'error');
    return;
  }
  state.adminPromptLabRunning = true;
  const operationId = createOperationId();
  state.adminPromptLabOperationId = operationId;
  state.adminPromptLabProgressStatus = 'preparing';
  state.adminPromptLabProgressPercent = 2;
  state.adminPromptLabProgressTitle = 'Формируем кейсы';
  state.adminPromptLabProgressMessage = 'Подготавливаем генерацию кейсов.';
  setPromptLabStatus('Формируем кейсы...', 'muted');
  renderAdminPromptLab();
  startAdminPromptLabPolling(operationId);
  try {
    const response = await fetch('/users/admin/prompt-lab/case-runs', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Agent4K-Operation-Id': operationId,
      },
      body: JSON.stringify({
        user_id: userId,
        case_id_code: selectedCaseCodes[0] || null,
        case_id_codes: selectedCaseCodes,
        prompt_source: promptSource,
        prompt_id: null,
        prompt_name: promptName,
        prompt_text: promptSource === 'custom' ? promptText : null,
        full_name: fullName,
        role_id: roleId,
        position: position,
        duties: duties,
        company_industry: companyIndustry,
        user_profile: userProfile,
      }),
    });
    const result = await readApiResponse(response, 'Не удалось сформировать кейсы.');
    state.adminPromptLabResult = result;
    stopAdminPromptLabPolling();
    state.adminPromptLabProgressStatus = 'ready';
    state.adminPromptLabProgressPercent = 100;
    state.adminPromptLabProgressTitle = 'Кейсы готовы';
    state.adminPromptLabProgressMessage = 'Генерация кейсов завершена.';
    await loadAdminPromptLab();
    setPromptLabStatus('Кейсы сформированы.', 'success');
    renderAdminPromptLab();
    renderAdminPromptLabResult();
  } catch (error) {
    stopAdminPromptLabPolling();
    state.adminPromptLabProgressStatus = 'failed';
    state.adminPromptLabProgressPercent = 0;
    state.adminPromptLabProgressTitle = 'Не удалось сформировать кейсы';
    state.adminPromptLabProgressMessage = error.message || 'Попробуйте запустить генерацию еще раз.';
    setPromptLabStatus(error.message, 'error');
  } finally {
    state.adminPromptLabRunning = false;
    renderAdminPromptLab();
  }
};

export const resetAdminPromptLabDialog = () => {
  state.adminPromptLabDialogPreview = null;
  state.adminPromptLabDialogHistory = [];
  state.adminPromptLabDialogPrepared = false;
  if (adminPromptLabDialogUserMessage) {
    adminPromptLabDialogUserMessage.value = '';
  }
  const selectedCase = getSelectedPromptLabDialogCase();
  const selectedCode = String(selectedCase?.case_id_code || '').trim();
  setPromptLabDialogStatus(
    selectedCode
      ? 'Выбран кейс ' + selectedCode + '. Нажмите «Подготовить диалог», чтобы запустить новый сценарий.'
      : '',
    'muted',
  );
  renderAdminPromptLab();
  renderAdminPromptLabDialogResult();
};

export const prepareAdminPromptLabDialog = async () => {
  const userId = Number(adminPromptLabDialogUserSelect?.value || 0);
  const caseIdCode = String(
    state.adminPromptLabDialogSelectedCaseCode || adminPromptLabDialogCaseSelect?.value || '',
  ).trim();
  if (!userId || !caseIdCode) {
    setPromptLabDialogStatus('Выберите пользователя и кейс.', 'error');
    return;
  }
  state.adminPromptLabDialogRunning = true;
  state.adminPromptLabDialogPrepared = false;
  state.adminPromptLabDialogPreview = null;
  state.adminPromptLabDialogHistory = [];
  setPromptLabDialogStatus(
    'Готовим диалог для ' + caseIdCode + '. Для диалоговых кейсов это может занять до 20–30 секунд.',
    'muted',
  );
  renderAdminPromptLab();
  renderAdminPromptLabDialogResult();
  try {
    const caseGenerationPromptText = String(adminPromptLabDialogCasePromptText?.value || '').trim() || null;
    const response = await fetch('/users/admin/prompt-lab/dialog-preview', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        case_id_code: caseIdCode,
        case_generation_prompt_text: caseGenerationPromptText,
      }),
    });
    const result = await readApiResponse(response, 'Не удалось подготовить моделирование диалога.');
    state.adminPromptLabDialogPreview = result;
    state.adminPromptLabDialogHistory = isPromptLabDialogPreviewDialogCase(result)
      ? [
          {
            role: 'assistant',
            kind: 'opening',
            content: result.opening_message || '',
          },
          {
            role: 'assistant',
            kind: 'counterpart_opening',
            content: result.counterpart_opening_message || '',
          },
        ].filter((item) => String(item.content || '').trim())
      : [];
    state.adminPromptLabDialogPrepared = true;
    if (adminPromptLabDialogPromptText) {
      if ((adminPromptLabDialogSourceSelect?.value || 'system') === 'system' || !promptLabDialogPromptDirty) {
        adminPromptLabDialogPromptText.value = String(
          result.interviewer_prompt_text || state.adminPromptLab?.interviewer_prompt_text || '',
        ).trim();
      }
    }
    syncPromptLabDialogPromptSource();
    setPromptLabDialogStatus(
      'Диалог подготовлен для ' + String(result?.case?.case_id_code || caseIdCode || 'выбранного кейса') + '.',
      'success',
    );
    renderAdminPromptLabDialogResult();
  } catch (error) {
    setPromptLabDialogStatus(error.message, 'error');
  } finally {
    state.adminPromptLabDialogRunning = false;
    renderAdminPromptLab();
  }
};

export const sendAdminPromptLabDialogTurn = async () => {
  const preview = state.adminPromptLabDialogPreview;
  const userMessage = adminPromptLabDialogUserMessage?.value?.trim() || '';
  if (!preview || !userMessage) {
    setPromptLabDialogStatus('Сначала подготовьте диалог и введите ответ пользователя.', 'error');
    return;
  }
  state.adminPromptLabDialogRunning = true;
  setPromptLabDialogStatus('Моделируем следующий ход агента...', 'muted');
  renderAdminPromptLab();
  try {
    const response = await fetch('/users/admin/prompt-lab/dialog-turn', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        system_prompt: preview.system_prompt,
        case_title: preview.case?.title || '',
        case_skills: Array.isArray(preview.case?.skills) ? preview.case.skills : [],
        methodical_context: preview.methodical_context || {},
        dialogue: state.adminPromptLabDialogHistory,
        interviewer_prompt_text: adminPromptLabDialogPromptText?.value?.trim() || null,
        user_message: userMessage,
      }),
    });
    const result = await readApiResponse(response, 'Не удалось смоделировать ответ агента.');
    const nextHistory = [
      ...(Array.isArray(state.adminPromptLabDialogHistory) ? state.adminPromptLabDialogHistory : []),
      { role: 'user', content: userMessage },
    ];
    if (isPromptLabDialogPreviewDialogCase(preview)) {
      nextHistory.push({
        role: 'assistant',
        content: result.assistant_message || '',
      });
    }
    state.adminPromptLabDialogHistory = nextHistory;
    if (adminPromptLabDialogUserMessage) {
      adminPromptLabDialogUserMessage.value = '';
    }
    if (result.case_completed) {
      setPromptLabDialogStatus('Диалог завершен по правилам кейса.', 'success');
    } else {
      setPromptLabDialogStatus('Следующий ход агента смоделирован.', 'success');
    }
    renderAdminPromptLabDialogResult();
  } catch (error) {
    setPromptLabDialogStatus(error.message, 'error');
  } finally {
    state.adminPromptLabDialogRunning = false;
    renderAdminPromptLab();
  }
};


export const openAdminPromptLab = async () => {
  setCurrentScreen('admin-prompt-lab');
  persistAssessmentContext();
  syncUrlState('admin-prompt-lab');
  hideAllPanels();
  if (adminPromptLabPanel) {
    adminPromptLabPanel.classList.remove('hidden');
  }
  state.adminPromptLabResult = null;
  state.adminPromptLabPreviewResult = null;
  state.adminPromptLabDialogPreview = null;
  state.adminPromptLabDialogHistory = [];
  state.adminPromptLabDialogPrepared = false;
  if (adminPromptLabResult && !state.adminPromptLabResult) {
    adminPromptLabResult.innerHTML = '<p class="report-empty-state">Загружаем Prompt Lab...</p>';
  }
  if (adminPromptLabDialogResult) {
    adminPromptLabDialogResult.innerHTML = '<p class="report-empty-state">Загружаем Prompt Lab...</p>';
  }
  try {
    await loadAdminPromptLab();
    renderAdminPromptLab();
    await loadPromptLabSystemCasePreview();
    renderAdminPromptLabResult();
  } catch (error) {
    if (adminPromptLabResult) {
      adminPromptLabResult.innerHTML = '<p class="report-empty-state">' + escapeHtml(error.message) + '</p>';
    }
  }
};

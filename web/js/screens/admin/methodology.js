import { state, persistAssessmentContext, setCurrentScreen } from '../../state.js';
import {
  adminMethodologyPanel,
  adminMethodologyTitle,
  adminMethodologySubtitle,
  adminMethodologySearch,
  adminMethodologyMetrics,
  adminMethodologyTabPassports,
  adminMethodologyTabLibrary,
  adminMethodologyTabBranches,
  adminMethodologyPassportsView,
  adminMethodologyLibraryView,
  adminMethodologyBranchesView,
  adminMethodologyCases,
  adminMethodologyPageSummary,
  adminMethodologyPageIndicator,
  adminMethodologyPrevButton,
  adminMethodologyNextButton,
  adminMethodologyPassports,
  adminMethodologyBranches,
  adminMethodologyCoverageBody,
  adminMethodologySummary,
  adminMethodologySkillGaps,
  adminMethodologySinglePoints,
  adminMethodologyCaseQuality,
  adminMethodologyDrawer,
  adminMethodologyDrawerBackdrop,
  adminMethodologyDetailClose,
  adminMethodologyDetailEdit,
  adminMethodologyDetailCancel,
  adminMethodologyDetailSave,
  adminMethodologyDetailSaveStatus,
  adminMethodologyDetailTitle,
  adminMethodologyDetailSubtitle,
  adminMethodologyDetailCaseName,
  adminMethodologyDetailArtifact,
  adminMethodologyDetailStatus,
  adminMethodologyDetailTiming,
  adminMethodologyDetailIntro,
  adminMethodologyDetailFacts,
  adminMethodologyDetailTask,
  adminMethodologyDetailConstraints,
  adminMethodologyDetailScenario,
  adminMethodologyDetailEditFields,
  adminMethodologyScenarioTemplate,
  adminMethodologyScenarioPreview,
  adminMethodologyDetailRoles,
  adminMethodologyDetailSkills,
  adminMethodologyDetailPersonalization,
  adminMethodologyDetailPersonalizationTable,
  adminMethodologyDetailBlocks,
  adminMethodologyDetailRedflags,
  adminMethodologyDetailBlockers,
  adminMethodologyDetailChecks,
  adminMethodologyDetailSignals,
  adminMethodologyDetailHistory,
  adminMethodologyDetailStakeholders,
  adminMethodologyDetailParticipants,
  adminMethodologyDetailExpectedArtifact,
  adminMethodologyDetailAnswerStructure,
  adminMethodologyDetailInteractivity,
  adminMethodologyDetailAnswerLength,
  adminMethodologyDetailDialogTurns,
  adminMethodologyDetailPersonalizationOptions,
  adminMethodologyDetailDifficultyToggles,
  adminMethodologyDetailSelectionTags,
  adminMethodologyDetailRoleRules,
  adminMethodologyDetailFormatRules,
  adminMethodologyDetailScoringRules,
  adminMethodologyDetailBadCaseRisks,
  adminMethodologyDetailGenerationNotes,
  adminMethodologyDetailEvaluationNotes,
  adminMethodologyDetailAuthorName,
  adminMethodologyDetailReviewerName,
  adminMethodologyDetailMethodologistComment,
  adminMethodologyDrawerPanel,
  adminMethodologyBackButton,
} from '../../dom.js';
import { ADMIN_METHODOLOGY_RISK_PAGE_SIZE, ADMIN_METHODOLOGY_CASES_PAGE_SIZE } from '../../config.js';
import { escapeHtml, highlightAdminInsightFigures, sanitizeDisplayMetaText } from '../../utils/format.js';
import { readApiResponse } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
export const loadAdminMethodology = async () => {
  const response = await fetch('/users/admin/methodology', {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить раздел управления кейсами.');
  state.adminMethodology = data;
  persistAssessmentContext();
};

export const loadAdminMethodologyDetail = async (caseIdCode) => {
  const response = await fetch('/users/admin/methodology/cases/' + encodeURIComponent(caseIdCode), {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить карточку кейса.');
  state.adminMethodologyDetail = data;
  state.adminMethodologyDetailCode = caseIdCode;
  state.adminMethodologyEditMode = false;
  state.adminMethodologySaving = false;
  state.adminMethodologyDraft = null;
  persistAssessmentContext();
};

export const getAdminMethodologyCaseSummaryByCode = (caseIdCode) => {
  const items = Array.isArray(state.adminMethodology?.cases) ? state.adminMethodology.cases : [];
  return items.find((item) => item.case_id_code === caseIdCode) || null;
};

export const saveAdminMethodologyDetail = async () => {
  const caseIdCode = state.adminMethodologyDetailCode;
  const draft = state.adminMethodologyDraft;
  if (!caseIdCode || !draft) {
    throw new Error('Карточка кейса не готова к сохранению.');
  }
  syncAdminMethodologyPersonalizationVariables();
  const response = await fetch('/users/admin/methodology/cases/' + encodeURIComponent(caseIdCode), {
    method: 'PUT',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(draft),
  });
  const data = await readApiResponse(response, 'Не удалось сохранить изменения по кейсу.');
  state.adminMethodologyDetail = data;
  state.adminMethodologyEditMode = false;
  state.adminMethodologySaving = false;
  state.adminMethodologyDraft = null;
  persistAssessmentContext();
};

export const getFilteredAdminMethodologyCases = () => {
  const items = Array.isArray(state.adminMethodology?.cases) ? state.adminMethodology.cases : [];
  const query = String(state.adminMethodologySearch || '')
    .trim()
    .toLowerCase();
  if (!query) {
    return items;
  }
  return items.filter((item) => {
    const haystack = [
      item.title,
      item.case_id_code,
      item.type_code,
      item.stakeholders_text,
      item.interactivity_mode,
      item.recommended_answer_length,
      item.expected_artifact,
      ...(Array.isArray(item.roles) ? item.roles : []),
      ...(Array.isArray(item.skills) ? item.skills : []),
      ...(Array.isArray(item.selection_tags) ? item.selection_tags : []),
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
};

export const renderAdminMethodologyTab = () => {
  const activeTab = state.adminMethodologyTab || 'passports';
  if (adminMethodologyTabPassports) {
    adminMethodologyTabPassports.classList.toggle('active', activeTab === 'passports');
  }
  if (adminMethodologyTabLibrary) {
    adminMethodologyTabLibrary.classList.toggle('active', activeTab === 'library');
  }
  if (adminMethodologyTabBranches) {
    adminMethodologyTabBranches.classList.toggle('active', activeTab === 'branches');
  }
  if (adminMethodologyPassportsView) {
    adminMethodologyPassportsView.classList.toggle('hidden', activeTab !== 'passports');
  }
  if (adminMethodologyLibraryView) {
    adminMethodologyLibraryView.classList.toggle('hidden', activeTab !== 'library');
  }
  if (adminMethodologyBranchesView) {
    adminMethodologyBranchesView.classList.toggle('hidden', activeTab !== 'branches');
  }
};

export const closeAdminMethodologyDetail = () => {
  state.adminMethodologyDetail = null;
  state.adminMethodologyDetailCode = null;
  state.adminMethodologyEditMode = false;
  state.adminMethodologySaving = false;
  state.adminMethodologyDraft = null;
  persistAssessmentContext();
  if (adminMethodologyDrawer) {
    adminMethodologyDrawer.classList.add('hidden');
  }
};

export const renderMethodologyChips = (container, items, emptyLabel, tone = 'default') => {
  if (!container) {
    return;
  }
  container.innerHTML = '';
  const values = Array.isArray(items) && items.length ? items : [emptyLabel];
  values.forEach((item) => {
    const chip = document.createElement('span');
    chip.className = 'admin-methodology-chip ' + tone;
    chip.textContent = item;
    container.appendChild(chip);
  });
};

export const getAdminMethodologyDraftFromDetail = (detail) => ({
  title: detail?.title || '',
  difficulty_level: detail?.difficulty_level || 'base',
  passport_status: detail?.passport_status || 'draft',
  case_status: detail?.case_status || 'draft',
  case_text_status: detail?.case_text_status || 'draft',
  estimated_time_min: Number(detail?.estimated_time_min) || 0,
  stakeholders_text: detail?.stakeholders_text || '',
  interactivity_mode: detail?.interactivity_mode || '',
  recommended_answer_length: detail?.recommended_answer_length || '',
  selection_tags: Array.isArray(detail?.selection_tags) ? [...detail.selection_tags] : [],
  role_personalization_rules: detail?.role_personalization_rules || '',
  format_control_rules: detail?.format_control_rules || '',
  scoring_aggregation_rules: detail?.scoring_aggregation_rules || '',
  bad_case_risks: detail?.bad_case_risks || '',
  generation_notes: detail?.generation_notes || '',
  intro_context: detail?.intro_context || '',
  facts_data: detail?.facts_data || '',
  participants_roles: detail?.participants_roles || '',
  trigger_event: detail?.trigger_event || '',
  trigger_details: detail?.trigger_details || '',
  task_for_user: detail?.task_for_user || '',
  expected_artifact: detail?.expected_artifact || '',
  answer_structure_hint: detail?.answer_structure_hint || '',
  constraints_text: detail?.constraints_text || '',
  dialog_turns_hint: detail?.dialog_turns_hint || '',
  stakes_text: detail?.stakes_text || '',
  personalization_items: Array.isArray(detail?.personalization_items)
    ? detail.personalization_items.map((item, index) => ({
        field_code: normalizePersonalizationCode(item.field_code),
        field_label: item.field_label || '',
        field_value_template: item.field_value_template || '',
        description: item.description || '',
        source_type: item.source_type || 'static',
        is_required: Boolean(item.is_required),
        display_order: Number(item.display_order) || index + 1,
      }))
    : [],
  personalization_options_text: detail?.personalization_options_text || '',
  difficulty_toggles: detail?.difficulty_toggles || '',
  evaluation_notes: detail?.evaluation_notes || '',
  author_name: detail?.author_name || '',
  reviewer_name: detail?.reviewer_name || '',
  methodologist_comment: detail?.methodologist_comment || '',
  role_ids: Array.isArray(detail?.selected_role_ids) ? [...detail.selected_role_ids] : [],
  skill_ids: Array.isArray(detail?.selected_skill_ids) ? [...detail.selected_skill_ids] : [],
});

export const setDetailNodeText = (node, text, fallback = '—') => {
  if (!node) {
    return;
  }
  node.textContent = text || fallback;
};


export const setDetailNodeMultiline = (node, text, fallback, hiddenWhenEmpty = false) => {
  if (!node) {
    return;
  }
  const resolvedText = String(text || '').trim();
  node.textContent = resolvedText || fallback;
  node.classList.toggle('hidden', hiddenWhenEmpty && !resolvedText);
};

export const getMethodologyStatusLabel = (status) => (status === 'ready' ? 'Ready' : status === 'retired' ? 'Архив' : 'Draft');

export const normalizePersonalizationCode = (value) =>
  String(value || '')
    .trim()
    .replace(/[{}]/g, '')
    .toLowerCase();

export const buildAdminMethodologyPersonalizationDefaults = (code) => {
  const normalized = normalizePersonalizationCode(code);
  const defaults = new Map([
    [
      'роль_кратко',
      {
        value: 'менеджер команды сопровождения',
        source: 'из профиля пользователя',
      },
    ],
    [
      'job_title',
      {
        value: 'менеджер команды сопровождения',
        source: 'из профиля пользователя',
      },
    ],
    [
      'industry',
      {
        value: 'сервиса и клиентской поддержки',
        source: 'из профиля пользователя',
      },
    ],
    [
      'сфера_деятельности_компании',
      {
        value: 'сервиса и клиентской поддержки',
        source: 'из профиля пользователя',
      },
    ],
    [
      'контекст_обязанностей',
      {
        value: 'сопровождение клиентских обращений и контроль качества сервиса',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'процесс',
      {
        value: 'обработка обращений клиентов',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'процесс/сервис',
      {
        value: 'обработка обращений клиентов',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'процесс/задача',
      {
        value: 'обработка обращений клиентов',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'пример_поведения',
      {
        value: 'сотрудник повторно закрывает обращения без решения',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'влияние',
      {
        value: 'растет число повторных обращений',
        source: 'задано в шаблоне кейса',
      },
    ],
    ['срок', { value: '2 недели', source: 'задано в шаблоне кейса' }],
    [
      'ресурсы_развития',
      {
        value: 'наставничество и еженедельные 1:1',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'метрика',
      {
        value: 'доля повторных обращений',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'стейкхолдер',
      {
        value: 'руководитель направления',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'ограничение',
      {
        value: 'нельзя менять SLA без согласования',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'ограничения/полномочия',
      {
        value: 'нельзя обещать решение без подтверждения смежной команды',
        source: 'задано в шаблоне кейса',
      },
    ],
    ['система', { value: 'Service Desk', source: 'задано в шаблоне кейса' }],
    ['канал', { value: 'чат поддержки', source: 'задано в шаблоне кейса' }],
    ['тип_клиента', { value: 'внутренний заказчик', source: 'задано в шаблоне кейса' }],
    [
      'стейкхолдеры',
      {
        value: 'руководитель направления и смежная команда',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'описание_проблемы',
      {
        value: 'обращение закрыто без фактического решения',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'sla/срок',
      {
        value: 'до конца рабочего дня',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'критичное_действие_/_этап_процесса',
      {
        value: 'завершение клиентского запроса',
        source: 'задано в шаблоне кейса',
      },
    ],
    ['id_обращения', { value: 'INC-48217', source: 'задано в шаблоне кейса' }],
    ['время_жалобы', { value: '16:40', source: 'задано в шаблоне кейса' }],
    [
      'что_зафиксировано_в_системе',
      {
        value: 'обращение закрыто с пометкой выполнено',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'что_осталось_нерешённым',
      {
        value: 'клиент не получил ожидаемый результат',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'последствие_для_процесса',
      {
        value: 'сдвигается следующий этап работы клиента',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'ответственная_команда_/_специалист',
      {
        value: 'команда сопровождения второй линии',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'руководитель_/_дежурный_/_владелец_процесса',
      {
        value: 'дежурный руководитель смены',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'риск',
      {
        value: 'эскалация повторных обращений',
        source: 'задано в шаблоне кейса',
      },
    ],
    [
      'триггер',
      {
        value: 'жалоба на закрытие обращения без решения',
        source: 'задано в шаблоне кейса',
      },
    ],
  ]);
  if (defaults.has(normalized)) {
    return defaults.get(normalized);
  }
  return {
    value: '',
    source:
      normalized.includes('роль') || normalized.includes('industry')
        ? 'из профиля пользователя'
        : 'задано в шаблоне кейса',
  };
};

export const extractAdminMethodologyPlaceholders = (text) => {
  const matches = String(text || '').match(/\{[^}]+\}/g) || [];
  return Array.from(new Set(matches.map((item) => normalizePersonalizationCode(item)).filter(Boolean)));
};

export const collectAdminMethodologyScenarioText = (source) => {
  const parts = [source?.intro_context, source?.facts_data, source?.task_for_user, source?.constraints_text]
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  return parts.join('\n\n');
};

export const collectAdminMethodologyPersonalizationRows = (detail, scenarioText) => {
  const fromText = extractAdminMethodologyPlaceholders(scenarioText);
  const itemMap = new Map();
  (detail?.personalization_items || []).forEach((item, index) => {
    const code = normalizePersonalizationCode(item.field_code);
    if (!code || itemMap.has(code)) {
      return;
    }
    const fallback = buildAdminMethodologyPersonalizationDefaults(code);
    itemMap.set(code, {
      code,
      label: item.field_label || code,
      description: item.description || '',
      source:
        item.source_type === 'from_user_profile'
          ? 'из профиля пользователя'
          : item.source_type === 'hybrid'
            ? 'профиль + шаблон'
            : fallback.source,
      sourceType: item.source_type || 'static',
      isRequired: Boolean(item.is_required),
      inScenario: fromText.includes(code),
      displayOrder: Number(item.display_order) || index + 1,
    });
  });
  fromText.forEach((code) => {
    if (itemMap.has(code)) {
      const row = itemMap.get(code);
      row.inScenario = true;
      return;
    }
    const fallback = buildAdminMethodologyPersonalizationDefaults(code);
    itemMap.set(code, {
      code,
      label: code,
      description: '',
      source: fallback.source,
      sourceType: fallback.source === 'из профиля пользователя' ? 'from_user_profile' : 'static',
      isRequired: false,
      inScenario: true,
      displayOrder: itemMap.size + 1,
    });
  });
  return Array.from(itemMap.values()).sort((first, second) => {
    const orderDelta = (first.displayOrder || 0) - (second.displayOrder || 0);
    if (orderDelta !== 0) {
      return orderDelta;
    }
    return String(first.code || '').localeCompare(String(second.code || ''), 'ru');
  });
};

export const buildAdminMethodologyScenarioMarkup = (text, personalizationRows, mode) => {
  const safeText = escapeHtml(String(text || '').trim() || 'Текст кейса пока не заполнен.');
  if (mode !== 'preview') {
    return safeText.replace(/\n/g, '<br>');
  }
  const valueMap = new Map(personalizationRows.map((item) => [normalizePersonalizationCode(item.code), item.value]));
  return safeText
    .replace(/\{([^}]+)\}/g, (_, rawCode) => {
      const code = normalizePersonalizationCode(rawCode);
      return (
        '<span class="admin-methodology-inline-variable">' +
        escapeHtml(valueMap.get(code) || '{' + rawCode + '}') +
        '</span>'
      );
    })
    .replace(/\n/g, '<br>');
};

export const renderAdminMethodologyPersonalizationTable = (rows) => {
  if (!adminMethodologyDetailPersonalizationTable) {
    return;
  }
  if (!rows.length) {
    adminMethodologyDetailPersonalizationTable.innerHTML =
      '<p class="report-empty-state">Переменные персонализации пока не заданы.</p>';
    return;
  }
  adminMethodologyDetailPersonalizationTable.innerHTML =
    '<div class="admin-methodology-personalization-row admin-methodology-personalization-head">' +
    '<span>Переменная</span>' +
    '<span>Описание</span>' +
    '<span>Источник</span>' +
    '<span>В тексте</span>' +
    '</div>' +
    rows
      .map(
        (row) =>
          '<div class="admin-methodology-personalization-row">' +
          '<span class="admin-methodology-personalization-code">{' +
          escapeHtml(row.code) +
          '}</span>' +
          '<span>' +
          escapeHtml(row.description || row.label || 'Описание не задано') +
          '</span>' +
          '<span class="admin-methodology-personalization-source">' +
          escapeHtml(row.source) +
          '</span>' +
          '<span class="admin-methodology-personalization-usage">' +
          (row.inScenario ? 'Да' : 'Нет') +
          '</span>' +
          '</div>',
      )
      .join('');
};

export const syncAdminMethodologyPersonalizationVariables = () => {
  if (!state.adminMethodologyDraft) {
    return;
  }
  const detail = state.adminMethodologyDetail;
  if (!Array.isArray(state.adminMethodologyDraft.personalization_items)) {
    state.adminMethodologyDraft.personalization_items = [];
  }
  const existingCodes = new Set(
    state.adminMethodologyDraft.personalization_items
      .map((item) => normalizePersonalizationCode(item.field_code))
      .filter(Boolean),
  );
  const scenarioCodes = extractAdminMethodologyPlaceholders(
    collectAdminMethodologyScenarioText(state.adminMethodologyDraft),
  );
  scenarioCodes.forEach((code) => {
    if (existingCodes.has(code)) {
      return;
    }
    state.adminMethodologyDraft.personalization_items.push({
      ...buildAdminMethodologyPersonalizationItem(detail, code),
      display_order: state.adminMethodologyDraft.personalization_items.length + 1,
    });
    existingCodes.add(code);
  });
  const codes = Array.from(existingCodes);
  state.adminMethodologyDraft.personalization_variables = codes.length
    ? codes.map((code) => '{' + code + '}').join(', ')
    : '';
};

export const getAdminMethodologyPersonalizationOptionMap = (detail) => {
  const map = new Map();
  (detail?.personalization_options || []).forEach((option) => {
    const code = normalizePersonalizationCode(option.field_code);
    if (!code) {
      return;
    }
    map.set(code, option);
  });
  return map;
};

export const buildAdminMethodologyPersonalizationItem = (detail, fieldCode, overrides = {}) => {
  const code = normalizePersonalizationCode(fieldCode);
  const option = getAdminMethodologyPersonalizationOptionMap(detail).get(code);
  const fallback = buildAdminMethodologyPersonalizationDefaults(code);
  return {
    field_code: code,
    field_label: overrides.field_label || option?.field_name || fallback.label || code,
    field_value_template: overrides.field_value_template ?? fallback.value ?? '',
    description: overrides.description ?? option?.description ?? '',
    source_type:
      overrides.source_type ||
      option?.source_type ||
      (fallback.source === 'из профиля пользователя' ? 'from_user_profile' : 'static'),
    is_required: Boolean(overrides.is_required ?? option?.is_required),
    display_order: Number(overrides.display_order) || 1,
  };
};

export const refreshAdminMethodologyScenarioSection = (detail, source) => {
  const scenarioText = collectAdminMethodologyScenarioText(source);
  const personalizationRows = collectAdminMethodologyPersonalizationRows(source, scenarioText);
  const scenarioMode = state.adminMethodologyScenarioMode || 'template';
  if (adminMethodologyDetailScenario) {
    adminMethodologyDetailScenario.innerHTML = state.adminMethodologyEditMode
      ? '<div class="admin-methodology-edit-hint">Редактируйте текст шаблона в полях ниже. Здесь показывается только компактная область просмотра.</div>'
      : buildAdminMethodologyScenarioMarkup(scenarioText, personalizationRows, scenarioMode);
  }
  renderAdminMethodologyPersonalizationTable(personalizationRows);
};

export const renderAdminMethodologyEditorField = (node, kind, config) => {
  if (!node) {
    return;
  }
  node.innerHTML = '';
  let control;
  if (kind === 'textarea') {
    control = document.createElement('textarea');
    control.rows = config.rows || 4;
  } else if (kind === 'select') {
    control = document.createElement('select');
    (config.options || []).forEach((option) => {
      const item = document.createElement('option');
      item.value = option.value;
      item.textContent = option.label;
      item.selected = String(option.value) === String(config.value);
      control.appendChild(item);
    });
  } else {
    control = document.createElement('input');
    control.type = kind === 'number' ? 'number' : 'text';
  }
  control.className = 'admin-methodology-input';
  if (config.fieldKey) {
    control.dataset.fieldKey = config.fieldKey;
    control.addEventListener('focus', () => {
      state.adminMethodologyActiveTextField = config.fieldKey;
    });
  }
  control.value = config.value ?? '';
  if (config.placeholder) {
    control.placeholder = config.placeholder;
  }
  if (kind === 'number') {
    control.min = '0';
    control.step = '1';
  }
  control.addEventListener('input', (event) => {
    config.onChange(event.target.value);
  });
  node.appendChild(control);
};

export const renderAdminMethodologySelectionChips = (container, options, selectedIds, onToggle, emptyLabel) => {
  if (!container) {
    return;
  }
  container.innerHTML = '';
  if (!Array.isArray(options) || !options.length) {
    renderMethodologyChips(container, [], emptyLabel, 'muted');
    return;
  }
  options.forEach((option) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'admin-methodology-chip admin-methodology-chip-button';
    if (selectedIds.includes(option.id)) {
      button.classList.add('selected');
    } else {
      button.classList.add('muted');
    }
    button.textContent = option.name || option.skill_name;
    if (option.competency_name) {
      button.title = option.competency_name;
    }
    button.addEventListener('click', () => onToggle(option.id));
    container.appendChild(button);
  });
};

export const toggleAdminMethodologyRole = (roleId) => {
  if (!state.adminMethodologyDraft) {
    return;
  }
  const selectedIds = new Set(state.adminMethodologyDraft.role_ids || []);
  if (selectedIds.has(roleId)) {
    selectedIds.delete(roleId);
  } else {
    selectedIds.add(roleId);
  }
  state.adminMethodologyDraft.role_ids = Array.from(selectedIds);
  renderAdminMethodologyDetail();
};

export const toggleAdminMethodologySkill = (skillId) => {
  if (!state.adminMethodologyDraft) {
    return;
  }
  const selectedIds = new Set(state.adminMethodologyDraft.skill_ids || []);
  if (selectedIds.has(skillId)) {
    selectedIds.delete(skillId);
  } else {
    selectedIds.add(skillId);
  }
  state.adminMethodologyDraft.skill_ids = Array.from(selectedIds);
  renderAdminMethodologyDetail();
};

export const renderAdminMethodologyDetail = () => {
  const detail = state.adminMethodologyDetail;
  if (!detail || !adminMethodologyDrawer) {
    return;
  }
  const isEditing = Boolean(state.adminMethodologyEditMode);
  const draft = state.adminMethodologyDraft || getAdminMethodologyDraftFromDetail(detail);
  const scenarioSource = isEditing ? draft : detail;
  const scenarioMode = state.adminMethodologyScenarioMode || 'template';

  adminMethodologyDetailTitle.textContent = detail.title || 'Кейс';
  adminMethodologyDetailSubtitle.textContent = (detail.type_code || '—') + ' · ' + (detail.type_name || 'Тип кейса');
  if (adminMethodologyDetailEdit) {
    adminMethodologyDetailEdit.classList.toggle('hidden', isEditing);
  }
  if (adminMethodologyDetailCancel) {
    adminMethodologyDetailCancel.classList.toggle('hidden', !isEditing);
  }
  if (adminMethodologyDetailSave) {
    adminMethodologyDetailSave.classList.toggle('hidden', !isEditing);
    adminMethodologyDetailSave.disabled = state.adminMethodologySaving;
  }
  if (adminMethodologyDetailSaveStatus) {
    adminMethodologyDetailSaveStatus.classList.toggle('hidden', !state.adminMethodologySaving);
  }
  if (adminMethodologyDrawerPanel) {
    adminMethodologyDrawerPanel.classList.toggle('editing', isEditing);
  }
  if (adminMethodologyDetailEditFields) {
    adminMethodologyDetailEditFields.classList.toggle('hidden', !isEditing);
  }
  if (adminMethodologyScenarioTemplate) {
    adminMethodologyScenarioTemplate.classList.toggle('active', scenarioMode === 'template');
  }
  if (adminMethodologyScenarioPreview) {
    adminMethodologyScenarioPreview.classList.toggle('active', scenarioMode === 'preview');
  }
  refreshAdminMethodologyScenarioSection(detail, scenarioSource);

  if (isEditing) {
    renderAdminMethodologyEditorField(adminMethodologyDetailCaseName, 'text', {
      value: draft.title,
      placeholder: 'Введите название кейса',
      onChange: (value) => {
        state.adminMethodologyDraft.title = value;
      },
    });
    setDetailNodeText(adminMethodologyDetailArtifact, detail.artifact_name || '—');
    adminMethodologyDetailStatus.innerHTML = '';
    const statusWrap = document.createElement('div');
    statusWrap.className = 'admin-methodology-inline-controls admin-methodology-status-controls';
    [
      { key: 'passport_status', label: 'Тип' },
      { key: 'case_status', label: 'Кейс' },
      { key: 'case_text_status', label: 'Текст' },
    ].forEach((field) => {
      const fieldWrap = document.createElement('label');
      fieldWrap.className = 'admin-methodology-status-field';
      const caption = document.createElement('span');
      caption.textContent = field.label;
      const select = document.createElement('select');
      select.className = 'admin-methodology-input';
      [
        { value: 'draft', label: 'Draft' },
        { value: 'ready', label: 'Ready' },
        { value: 'retired', label: 'Архив' },
      ].forEach((item) => {
        const option = document.createElement('option');
        option.value = item.value;
        option.textContent = item.label;
        option.selected = item.value === draft[field.key];
        select.appendChild(option);
      });
      select.addEventListener('input', (event) => {
        state.adminMethodologyDraft[field.key] = event.target.value;
      });
      fieldWrap.appendChild(caption);
      fieldWrap.appendChild(select);
      statusWrap.appendChild(fieldWrap);
    });
    adminMethodologyDetailStatus.appendChild(statusWrap);
    adminMethodologyDetailTiming.innerHTML = '';
    const timingWrap = document.createElement('div');
    timingWrap.className = 'admin-methodology-inline-controls';
    const difficultySelect = document.createElement('select');
    difficultySelect.className = 'admin-methodology-input';
    [
      { value: 'base', label: 'Base' },
      { value: 'hard', label: 'Hard' },
    ].forEach((item) => {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      option.selected = item.value === draft.difficulty_level;
      difficultySelect.appendChild(option);
    });
    difficultySelect.addEventListener('input', (event) => {
      state.adminMethodologyDraft.difficulty_level = event.target.value;
    });
    const timingInput = document.createElement('input');
    timingInput.type = 'number';
    timingInput.min = '0';
    timingInput.step = '1';
    timingInput.className = 'admin-methodology-input';
    timingInput.placeholder = 'Минуты';
    timingInput.value = draft.estimated_time_min || '';
    timingInput.addEventListener('input', (event) => {
      state.adminMethodologyDraft.estimated_time_min = Number(event.target.value) || 0;
    });
    timingWrap.appendChild(difficultySelect);
    timingWrap.appendChild(timingInput);
    adminMethodologyDetailTiming.appendChild(timingWrap);
    renderAdminMethodologyEditorField(adminMethodologyDetailIntro, 'textarea', {
      fieldKey: 'intro_context',
      value: draft.intro_context,
      rows: 5,
      placeholder: 'Контекст кейса',
      onChange: (value) => {
        state.adminMethodologyDraft.intro_context = value;
        refreshAdminMethodologyScenarioSection(detail, state.adminMethodologyDraft);
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailFacts, 'textarea', {
      fieldKey: 'facts_data',
      value: draft.facts_data,
      rows: 4,
      placeholder: 'Дополнительные факты и данные',
      onChange: (value) => {
        state.adminMethodologyDraft.facts_data = value;
        refreshAdminMethodologyScenarioSection(detail, state.adminMethodologyDraft);
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailTask, 'textarea', {
      fieldKey: 'task_for_user',
      value: draft.task_for_user,
      rows: 5,
      placeholder: 'Задача для пользователя',
      onChange: (value) => {
        state.adminMethodologyDraft.task_for_user = value;
        refreshAdminMethodologyScenarioSection(detail, state.adminMethodologyDraft);
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailConstraints, 'textarea', {
      fieldKey: 'constraints_text',
      value: draft.constraints_text,
      rows: 4,
      placeholder: 'Ограничения и ставки',
      onChange: (value) => {
        state.adminMethodologyDraft.constraints_text = value;
        refreshAdminMethodologyScenarioSection(detail, state.adminMethodologyDraft);
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailStakeholders, 'textarea', {
      value: draft.stakeholders_text,
      rows: 3,
      placeholder: 'Стейкхолдеры кейса',
      onChange: (value) => {
        state.adminMethodologyDraft.stakeholders_text = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailParticipants, 'textarea', {
      value: draft.participants_roles,
      rows: 3,
      placeholder: 'Роли и участники',
      onChange: (value) => {
        state.adminMethodologyDraft.participants_roles = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailExpectedArtifact, 'textarea', {
      value: draft.expected_artifact,
      rows: 2,
      placeholder: 'Ожидаемый артефакт ответа',
      onChange: (value) => {
        state.adminMethodologyDraft.expected_artifact = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailAnswerStructure, 'textarea', {
      value: draft.answer_structure_hint,
      rows: 4,
      placeholder: 'Подсказка по структуре ответа',
      onChange: (value) => {
        state.adminMethodologyDraft.answer_structure_hint = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailInteractivity, 'text', {
      value: draft.interactivity_mode,
      placeholder: '1 ход / диалог / ...',
      onChange: (value) => {
        state.adminMethodologyDraft.interactivity_mode = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailAnswerLength, 'text', {
      value: draft.recommended_answer_length,
      placeholder: '5–7 предложений / 8–12 вопросов ...',
      onChange: (value) => {
        state.adminMethodologyDraft.recommended_answer_length = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailDialogTurns, 'textarea', {
      value: draft.dialog_turns_hint,
      rows: 3,
      placeholder: 'Уточняющие вопросы / диалоговые ходы',
      onChange: (value) => {
        state.adminMethodologyDraft.dialog_turns_hint = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailPersonalizationOptions, 'textarea', {
      value: draft.personalization_options_text,
      rows: 3,
      placeholder: 'Варианты персонализации',
      onChange: (value) => {
        state.adminMethodologyDraft.personalization_options_text = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailDifficultyToggles, 'textarea', {
      value: draft.difficulty_toggles,
      rows: 3,
      placeholder: 'Крутилки сложности',
      onChange: (value) => {
        state.adminMethodologyDraft.difficulty_toggles = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailSelectionTags, 'textarea', {
      value: Array.isArray(draft.selection_tags) ? draft.selection_tags.join(', ') : '',
      rows: 2,
      placeholder: 'тег1, тег2, тег3',
      onChange: (value) => {
        state.adminMethodologyDraft.selection_tags = String(value || '')
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean);
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailRoleRules, 'textarea', {
      value: draft.role_personalization_rules,
      rows: 4,
      placeholder: 'Ролевые правила персонализации',
      onChange: (value) => {
        state.adminMethodologyDraft.role_personalization_rules = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailFormatRules, 'textarea', {
      value: draft.format_control_rules,
      rows: 4,
      placeholder: 'Контроль формата ответа',
      onChange: (value) => {
        state.adminMethodologyDraft.format_control_rules = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailScoringRules, 'textarea', {
      value: draft.scoring_aggregation_rules,
      rows: 4,
      placeholder: 'Правила агрегации оценки',
      onChange: (value) => {
        state.adminMethodologyDraft.scoring_aggregation_rules = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailBadCaseRisks, 'textarea', {
      value: draft.bad_case_risks,
      rows: 4,
      placeholder: 'Ограничения и риски плохого кейса',
      onChange: (value) => {
        state.adminMethodologyDraft.bad_case_risks = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailGenerationNotes, 'textarea', {
      value: draft.generation_notes,
      rows: 4,
      placeholder: 'Примечания для генерации',
      onChange: (value) => {
        state.adminMethodologyDraft.generation_notes = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailEvaluationNotes, 'textarea', {
      value: draft.evaluation_notes,
      rows: 4,
      placeholder: 'Заметки для оценивания',
      onChange: (value) => {
        state.adminMethodologyDraft.evaluation_notes = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailAuthorName, 'text', {
      value: draft.author_name,
      placeholder: 'Автор',
      onChange: (value) => {
        state.adminMethodologyDraft.author_name = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailReviewerName, 'text', {
      value: draft.reviewer_name,
      placeholder: 'Проверяющий',
      onChange: (value) => {
        state.adminMethodologyDraft.reviewer_name = value;
      },
    });
    renderAdminMethodologyEditorField(adminMethodologyDetailMethodologistComment, 'textarea', {
      value: draft.methodologist_comment,
      rows: 3,
      placeholder: 'Комментарий методиста',
      onChange: (value) => {
        state.adminMethodologyDraft.methodologist_comment = value;
      },
    });
    adminMethodologyDetailFacts.classList.remove('hidden');
    adminMethodologyDetailConstraints.classList.remove('hidden');
    renderAdminMethodologySelectionChips(
      adminMethodologyDetailRoles,
      detail.role_options || [],
      draft.role_ids || [],
      toggleAdminMethodologyRole,
      'Роли не заданы',
    );
    renderAdminMethodologySelectionChips(
      adminMethodologyDetailSkills,
      (detail.skill_options || []).map((item) => ({
        id: item.id,
        name: item.skill_name,
        competency_name: item.competency_name,
      })),
      draft.skill_ids || [],
      toggleAdminMethodologySkill,
      'Навыки не заданы',
    );
  } else {
    setDetailNodeText(adminMethodologyDetailCaseName, detail.title || '—');
    setDetailNodeText(adminMethodologyDetailArtifact, detail.artifact_name || '—');
    setDetailNodeText(
      adminMethodologyDetailStatus,
      'Тип: ' +
        getMethodologyStatusLabel(detail.passport_status) +
        ' · Кейс: ' +
        getMethodologyStatusLabel(detail.case_status) +
        ' · Текст: ' +
        getMethodologyStatusLabel(detail.case_text_status) +
        ' · ' +
        (detail.difficulty_level === 'hard' ? 'Hard' : 'Base') +
        ' · кейс v' +
        (detail.case_registry_version || 1) +
        ' / текст v' +
        (detail.case_text_version || 1),
    );
    setDetailNodeText(
      adminMethodologyDetailTiming,
      detail.estimated_time_min ? detail.estimated_time_min + ' минут' : 'Время не задано',
    );
    setDetailNodeMultiline(adminMethodologyDetailIntro, detail.intro_context, 'Контекст кейса пока не заполнен.');
    setDetailNodeMultiline(adminMethodologyDetailFacts, detail.facts_data, 'Дополнительные факты не заданы.', true);
    setDetailNodeMultiline(adminMethodologyDetailTask, detail.task_for_user, 'Задача кейса пока не заполнена.');
    setDetailNodeMultiline(adminMethodologyDetailConstraints, detail.constraints_text, 'Ограничения не заданы.', true);
    setDetailNodeMultiline(
      adminMethodologyDetailStakeholders,
      detail.stakeholders_text,
      'Стейкхолдеры не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailParticipants,
      detail.participants_roles,
      'Роли и участники не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailExpectedArtifact,
      detail.expected_artifact,
      'Артефакт ответа не задан.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailAnswerStructure,
      detail.answer_structure_hint,
      'Подсказка по структуре ответа не задана.',
      true,
    );
    setDetailNodeText(adminMethodologyDetailInteractivity, detail.interactivity_mode, 'Интерактивность не задана');
    setDetailNodeText(adminMethodologyDetailAnswerLength, detail.recommended_answer_length, 'Длина ответа не задана');
    setDetailNodeMultiline(
      adminMethodologyDetailDialogTurns,
      detail.dialog_turns_hint,
      'Диалоговые ходы не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailPersonalizationOptions,
      detail.personalization_options_text,
      'Варианты персонализации не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailDifficultyToggles,
      detail.difficulty_toggles,
      'Крутилки сложности не заданы.',
      true,
    );
    setDetailNodeText(adminMethodologyDetailSelectionTags, (detail.selection_tags || []).join(', '), 'Теги не заданы');
    setDetailNodeMultiline(
      adminMethodologyDetailRoleRules,
      detail.role_personalization_rules,
      'Ролевые правила не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailFormatRules,
      detail.format_control_rules,
      'Правила формата не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailScoringRules,
      detail.scoring_aggregation_rules,
      'Правила агрегации не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailBadCaseRisks,
      detail.bad_case_risks,
      'Риски плохого кейса не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailGenerationNotes,
      detail.generation_notes,
      'Примечания для генерации не заданы.',
      true,
    );
    setDetailNodeMultiline(
      adminMethodologyDetailEvaluationNotes,
      detail.evaluation_notes,
      'Заметки для оценивания не заданы.',
      true,
    );
    setDetailNodeText(adminMethodologyDetailAuthorName, detail.author_name, 'Автор не указан');
    setDetailNodeText(adminMethodologyDetailReviewerName, detail.reviewer_name, 'Проверяющий не указан');
    setDetailNodeMultiline(
      adminMethodologyDetailMethodologistComment,
      detail.methodologist_comment,
      'Комментарий методиста не задан.',
      true,
    );
    renderMethodologyChips(adminMethodologyDetailRoles, detail.roles, 'Роли не заданы');
    renderMethodologyChips(adminMethodologyDetailSkills, detail.skills, 'Навыки не заданы');
  }

  adminMethodologyDetailBlocks.innerHTML = '';
  (detail.required_blocks && detail.required_blocks.length
    ? detail.required_blocks
    : ['Блоки ответа не заданы.']
  ).forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    adminMethodologyDetailBlocks.appendChild(item);
  });

  adminMethodologyDetailRedflags.innerHTML = '';
  (detail.red_flags && detail.red_flags.length ? detail.red_flags : ['Red flags не заданы.']).forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    adminMethodologyDetailRedflags.appendChild(item);
  });

  adminMethodologyDetailBlockers.innerHTML = '';
  (detail.qa_blockers && detail.qa_blockers.length ? detail.qa_blockers : ['Критических блокеров сейчас нет.']).forEach(
    (text) => {
      const item = document.createElement('li');
      item.textContent = text;
      adminMethodologyDetailBlockers.appendChild(item);
    },
  );

  adminMethodologyDetailChecks.innerHTML = '';
  (detail.quality_checks || []).forEach((check) => {
    const item = document.createElement('div');
    item.className = 'admin-methodology-check-item ' + (check.passed ? 'passed' : 'failed');
    item.innerHTML =
      '<strong>' +
      check.name +
      '</strong>' +
      '<span>' +
      (check.passed ? 'OK' : 'Проверить') +
      '</span>' +
      (check.comment ? '<small>' + check.comment + '</small>' : '');
    adminMethodologyDetailChecks.appendChild(item);
  });
  if (!detail.quality_checks || !detail.quality_checks.length) {
    adminMethodologyDetailChecks.innerHTML = '<p class="report-empty-state">QA-проверки пока не рассчитаны.</p>';
  }

  adminMethodologyDetailSignals.innerHTML = '';
  (detail.skill_signals && detail.skill_signals.length ? detail.skill_signals : []).forEach((signal) => {
    const card = document.createElement('article');
    card.className = 'card card--inset admin-methodology-signal-card';
    card.innerHTML =
      '<div class="admin-methodology-signal-head">' +
      '<strong>' +
      signal.skill_name +
      '</strong>' +
      '<span>' +
      signal.competency_name +
      '</span>' +
      '</div>' +
      '<p>' +
      signal.evidence_description +
      '</p>' +
      '<small>' +
      ((signal.related_response_block_code || 'response') +
        (signal.expected_signal ? ' · ' + signal.expected_signal : '')) +
      '</small>';
    adminMethodologyDetailSignals.appendChild(card);
  });
  if (!detail.skill_signals || !detail.skill_signals.length) {
    adminMethodologyDetailSignals.innerHTML = '<p class="report-empty-state">Сигналы по навыкам пока не заданы.</p>';
  }

  adminMethodologyDetailHistory.innerHTML = '';
  (detail.change_log && detail.change_log.length ? detail.change_log : []).forEach((entry) => {
    const item = document.createElement('article');
    item.className = 'admin-methodology-history-item';
    item.innerHTML =
      '<div class="admin-methodology-history-head">' +
      '<strong>' +
      entry.summary +
      '</strong>' +
      '<span>' +
      new Date(entry.changed_at).toLocaleString('ru-RU') +
      '</span>' +
      '</div>' +
      '<small>' +
      entry.entity_scope +
      ' · ' +
      entry.action +
      ' · ' +
      entry.changed_by +
      '</small>';
    adminMethodologyDetailHistory.appendChild(item);
  });
  if (!detail.change_log || !detail.change_log.length) {
    adminMethodologyDetailHistory.innerHTML = '<p class="report-empty-state">История изменений пока пуста.</p>';
  }

  adminMethodologyDrawer.classList.remove('hidden');
};

export const openAdminMethodologyDetail = async (caseIdCode) => {
  state.adminMethodologyEditMode = false;
  state.adminMethodologySaving = false;
  state.adminMethodologyDraft = null;
  state.adminMethodologyScenarioMode = 'template';
  if (adminMethodologyDrawer) {
    adminMethodologyDrawer.classList.remove('hidden');
  }
  adminMethodologyDetailTitle.textContent = 'Загружаем кейс...';
  adminMethodologyDetailSubtitle.textContent = '';
  adminMethodologyDetailCaseName.textContent = '—';
  adminMethodologyDetailArtifact.textContent = '—';
  adminMethodologyDetailStatus.textContent = 'Подготовка';
  adminMethodologyDetailTiming.textContent = '—';
  adminMethodologyDetailIntro.textContent = 'Загружаем контекст кейса...';
  adminMethodologyDetailTask.textContent = 'Подождите, пожалуйста.';
  try {
    await loadAdminMethodologyDetail(caseIdCode);
    renderAdminMethodologyDetail();
  } catch (error) {
    try {
      await loadAdminMethodologyDetail(caseIdCode);
      renderAdminMethodologyDetail();
      return;
    } catch (_retryError) {
      const summary = getAdminMethodologyCaseSummaryByCode(caseIdCode);
      adminMethodologyDetailSubtitle.textContent = summary
        ? (summary.type_code || '—') + ' · ' + (summary.status || 'draft')
        : '';
      setDetailNodeText(adminMethodologyDetailCaseName, summary?.title || '—');
      setDetailNodeText(adminMethodologyDetailArtifact, '—');
      setDetailNodeText(
        adminMethodologyDetailStatus,
        summary
          ? 'Кейс: ' +
              getMethodologyStatusLabel(summary.status) +
              ' · QA: ' +
              summary.passed_checks +
              '/' +
              summary.total_checks
          : 'Подготовка',
      );
      setDetailNodeText(
        adminMethodologyDetailTiming,
        summary?.estimated_time_min ? summary.estimated_time_min + ' минут' : 'Время не задано',
      );
      setDetailNodeMultiline(
        adminMethodologyDetailIntro,
        '',
        'Не удалось загрузить детальную карточку. ' + (error?.message || 'Попробуйте открыть кейс повторно.'),
      );
      setDetailNodeMultiline(
        adminMethodologyDetailTask,
        '',
        'Базовая информация о кейсе показана из списка. Детальные поля временно недоступны.',
      );
    }
    adminMethodologyDetailTitle.textContent = 'Не удалось загрузить кейс';
  }
};

export const getAdminMethodologyRiskUiState = (key) => {
  if (!state.adminMethodologyRiskUi[key]) {
    state.adminMethodologyRiskUi[key] = { collapsed: true, page: 1 };
  }
  return state.adminMethodologyRiskUi[key];
};

export const updateAdminMethodologyRiskPage = (key, nextPage, totalPages) => {
  const uiState = getAdminMethodologyRiskUiState(key);
  uiState.page = Math.max(1, Math.min(totalPages, nextPage));
  renderAdminMethodology();
};

export const toggleAdminMethodologyRiskCollapsed = (key) => {
  const uiState = getAdminMethodologyRiskUiState(key);
  uiState.collapsed = !uiState.collapsed;
  renderAdminMethodology();
};

export const renderAdminMethodologyPagedRiskList = (container, config) => {
  if (!container) {
    return;
  }
  container.innerHTML = '';
  const items = Array.isArray(config.items) ? config.items : [];
  if (!items.length) {
    container.innerHTML = '<p class="report-empty-state">' + config.emptyText + '</p>';
    return;
  }

  const uiState = getAdminMethodologyRiskUiState(config.key);
  const totalPages = Math.max(1, Math.ceil(items.length / ADMIN_METHODOLOGY_RISK_PAGE_SIZE));
  if (uiState.page > totalPages) {
    uiState.page = totalPages;
  }
  const startIndex = (uiState.page - 1) * ADMIN_METHODOLOGY_RISK_PAGE_SIZE;
  const pageItems = items.slice(startIndex, startIndex + ADMIN_METHODOLOGY_RISK_PAGE_SIZE);

  const shell = document.createElement('div');
  shell.className = 'admin-methodology-risk-shell';

  const toolbar = document.createElement('div');
  toolbar.className = 'admin-methodology-risk-toolbar';
  toolbar.innerHTML =
    '<div class="admin-methodology-risk-summary">' +
    '<strong>Показано ' +
    pageItems.length +
    ' из ' +
    items.length +
    '</strong>' +
    '<span>Страница ' +
    uiState.page +
    ' из ' +
    totalPages +
    '</span>' +
    '</div>';

  const controls = document.createElement('div');
  controls.className = 'admin-methodology-risk-toolbar-controls';

  const toggleButton = document.createElement('button');
  toggleButton.type = 'button';
  toggleButton.className = 'ghost-button compact-ghost';
  toggleButton.textContent = uiState.collapsed ? 'Показать список' : 'Скрыть список';
  toggleButton.addEventListener('click', () => {
    toggleAdminMethodologyRiskCollapsed(config.key);
  });
  controls.appendChild(toggleButton);

  toolbar.appendChild(controls);
  shell.appendChild(toolbar);

  const body = document.createElement('div');
  body.className = 'admin-methodology-risk-body' + (uiState.collapsed ? ' hidden' : '');
  pageItems.forEach((item) => {
    body.appendChild(config.renderItem(item));
  });

  if (totalPages > 1) {
    const pagination = document.createElement('div');
    pagination.className = 'admin-methodology-risk-pagination';

    const paginationSummary = document.createElement('span');
    paginationSummary.className = 'admin-methodology-risk-pagination-summary';
    paginationSummary.textContent = 'Страница ' + uiState.page + ' из ' + totalPages;
    pagination.appendChild(paginationSummary);

    const paginationControls = document.createElement('div');
    paginationControls.className = 'admin-methodology-risk-pagination-controls';

    const prevButton = document.createElement('button');
    prevButton.type = 'button';
    prevButton.className = 'ghost-button compact-ghost';
    prevButton.textContent = 'Назад';
    prevButton.disabled = uiState.page <= 1;
    prevButton.addEventListener('click', () => {
      updateAdminMethodologyRiskPage(config.key, uiState.page - 1, totalPages);
    });
    paginationControls.appendChild(prevButton);

    const nextButton = document.createElement('button');
    nextButton.type = 'button';
    nextButton.className = 'ghost-button compact-ghost';
    nextButton.textContent = 'Далее';
    nextButton.disabled = uiState.page >= totalPages;
    nextButton.addEventListener('click', () => {
      updateAdminMethodologyRiskPage(config.key, uiState.page + 1, totalPages);
    });
    paginationControls.appendChild(nextButton);

    pagination.appendChild(paginationControls);
    body.appendChild(pagination);
  }

  shell.appendChild(body);
  container.appendChild(shell);
};

export const startAdminMethodologyEditing = () => {
  if (!state.adminMethodologyDetail) {
    return;
  }
  state.adminMethodologyEditMode = true;
  state.adminMethodologyDraft = getAdminMethodologyDraftFromDetail(state.adminMethodologyDetail);
  persistAssessmentContext();
  renderAdminMethodologyDetail();
};

export const cancelAdminMethodologyEditing = () => {
  state.adminMethodologyEditMode = false;
  state.adminMethodologySaving = false;
  state.adminMethodologyDraft = null;
  persistAssessmentContext();
  renderAdminMethodologyDetail();
};

export const submitAdminMethodologyEditing = async () => {
  if (!state.adminMethodologyDetailCode || !state.adminMethodologyDraft) {
    return;
  }
  state.adminMethodologySaving = true;
  renderAdminMethodologyDetail();
  try {
    await saveAdminMethodologyDetail();
    await loadAdminMethodology();
    renderAdminMethodology();
    renderAdminMethodologyDetail();
  } catch (error) {
    state.adminMethodologySaving = false;
    renderAdminMethodologyDetail();
    window.alert(error.message || 'Не удалось сохранить изменения по кейсу.');
  }
};

export const renderAdminMethodology = () => {
  const data = state.adminMethodology;
  if (!data) {
    return;
  }

  if (adminMethodologyTitle) {
    adminMethodologyTitle.textContent = data.title || 'Управление кейсами';
  }
  if (adminMethodologySubtitle) {
    adminMethodologySubtitle.textContent = data.subtitle || 'Библиотека кейсов и ветки тестирования.';
  }
  if (adminMethodologySearch) {
    adminMethodologySearch.value = state.adminMethodologySearch || '';
  }

  adminMethodologyMetrics.innerHTML = '';
  (data.metrics || []).forEach((metric) => {
    const card = document.createElement('article');
    card.className = 'card admin-metric-card';
    card.innerHTML =
      '<span>' +
      metric.label +
      '</span>' +
      '<strong>' +
      metric.value +
      '</strong>' +
      '<small>' +
      (metric.delta || '') +
      '</small>';
    adminMethodologyMetrics.appendChild(card);
  });

  adminMethodologyCases.innerHTML = '';
  const filteredCases = getFilteredAdminMethodologyCases();
  const totalCases = filteredCases.length;
  const totalPages = Math.max(1, Math.ceil(totalCases / ADMIN_METHODOLOGY_CASES_PAGE_SIZE));
  if (state.adminMethodologyPage > totalPages) {
    state.adminMethodologyPage = totalPages;
  }
  const pageStart = (state.adminMethodologyPage - 1) * ADMIN_METHODOLOGY_CASES_PAGE_SIZE;
  const pageCases = filteredCases.slice(pageStart, pageStart + ADMIN_METHODOLOGY_CASES_PAGE_SIZE);
  if (!filteredCases.length) {
    adminMethodologyCases.innerHTML = '<p class="report-empty-state">По текущему запросу кейсы не найдены.</p>';
  } else {
    pageCases.forEach((item) => {
      const row = document.createElement('article');
      row.className = 'admin-report-row admin-methodology-row';
      row.tabIndex = 0;
      row.setAttribute('role', 'button');
      const statusLabel = item.status === 'ready' ? 'Активен' : item.status === 'retired' ? 'Архив' : 'Черновик';
      const qaLabel = item.qa_ready ? 'QA готов' : 'Нужна проверка';
      const metadataParts = [
        item.interactivity_mode ? 'Формат: ' + item.interactivity_mode : '',
        item.recommended_answer_length ? 'Длина: ' + item.recommended_answer_length : '',
        item.expected_artifact ? 'Артефакт: ' + item.expected_artifact : '',
      ].filter(Boolean);
      const tagsHtml =
        Array.isArray(item.selection_tags) && item.selection_tags.length
          ? '<div class="admin-methodology-inline-tags">' +
            item.selection_tags
              .slice(0, 3)
              .map((tag) => '<span class="admin-methodology-inline-tag">' + escapeHtml(tag) + '</span>')
              .join('') +
            '</div>'
          : '';
      const metaHtml = metadataParts.length
        ? '<small class="admin-methodology-row-meta">' + metadataParts.join(' · ') + '</small>'
        : '';
      const difficultyLabel = item.difficulty_level === 'hard' ? 'Hard' : 'Base';
      const timeLabel = item.estimated_time_min ? item.estimated_time_min + ' мин' : '—';
      row.innerHTML =
        '<div class="admin-report-cell admin-methodology-title-cell">' +
        '<strong>' +
        item.title +
        '</strong>' +
        '<small class="admin-methodology-row-id">' +
        item.case_id_code +
        '</small>' +
        metaHtml +
        tagsHtml +
        '</div>' +
        '<div class="admin-report-cell"><strong>' +
        ((item.roles || []).join(', ') || 'Не заданы') +
        '</strong></div>' +
        '<div class="admin-report-cell"><span>' +
        ((item.skills || []).slice(0, 3).join(', ') || 'Нет навыков') +
        '</span></div>' +
        '<div class="admin-report-cell admin-methodology-difficulty-cell">' +
        '<strong>' +
        difficultyLabel +
        '</strong>' +
        '<small>' +
        timeLabel +
        '</small>' +
        '</div>' +
        '<div class="admin-report-cell admin-methodology-status-cell">' +
        '<span class="admin-status-pill ' +
        (item.status === 'ready' ? 'done' : item.status === 'retired' ? 'draft' : 'active') +
        '">' +
        statusLabel +
        '</span>' +
        '<small>' +
        qaLabel +
        ' · ' +
        item.passed_checks +
        '/' +
        item.total_checks +
        '</small>' +
        '</div>';
      const openDetail = () => {
        void openAdminMethodologyDetail(item.case_id_code);
      };
      row.addEventListener('click', openDetail);
      row.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openDetail();
        }
      });
      adminMethodologyCases.appendChild(row);
    });
  }

  if (adminMethodologyPageSummary) {
    adminMethodologyPageSummary.textContent = 'Показано ' + pageCases.length + ' из ' + totalCases + ' кейсов';
  }
  if (adminMethodologyPageIndicator) {
    adminMethodologyPageIndicator.textContent = state.adminMethodologyPage + ' / ' + totalPages;
  }
  if (adminMethodologyPrevButton) {
    adminMethodologyPrevButton.disabled = state.adminMethodologyPage <= 1;
  }
  if (adminMethodologyNextButton) {
    adminMethodologyNextButton.disabled = state.adminMethodologyPage >= totalPages;
  }

  adminMethodologyPassports.innerHTML = '';
  (data.passports || []).forEach((item) => {
    const card = document.createElement('article');
    card.className = 'card admin-methodology-passport-card';
    const rolesText = Array.isArray(item.roles) && item.roles.length ? item.roles.join(', ') : 'Роли не заданы';
    const passportMeta = [
      item.interactivity_mode ? 'Формат: ' + item.interactivity_mode : '',
      item.recommended_answer_length ? 'Длина: ' + item.recommended_answer_length : '',
    ].filter(Boolean);
    const passportTagsHtml =
      Array.isArray(item.selection_tags) && item.selection_tags.length
        ? '<div class="admin-methodology-inline-tags">' +
          item.selection_tags
            .slice(0, 3)
            .map((tag) => '<span class="admin-methodology-inline-tag">' + escapeHtml(tag) + '</span>')
            .join('') +
          '</div>'
        : '';
    card.innerHTML =
      '<div class="admin-methodology-passport-head">' +
      '<strong>' +
      item.type_code +
      '</strong>' +
      '<span class="admin-status-pill ' +
      (item.status === 'ready' ? 'done' : item.status === 'retired' ? 'draft' : 'active') +
      '">' +
      (item.status === 'ready' ? 'Ready' : item.status === 'retired' ? 'Retired' : 'Draft') +
      '</span>' +
      '</div>' +
      '<h4>' +
      item.type_name +
      '</h4>' +
      '<p>' +
      item.artifact_name +
      '</p>' +
      (passportMeta.length
        ? '<small class="admin-methodology-row-meta">' + passportMeta.join(' · ') + '</small>'
        : '') +
      passportTagsHtml +
      '<div class="admin-methodology-passport-meta">' +
      '<span>' +
      item.ready_cases_count +
      ' кейсов ready</span>' +
      '<span>' +
      item.required_blocks_count +
      ' блока</span>' +
      '<span>' +
      item.red_flags_count +
      ' red flags</span>' +
      '</div>' +
      '<small>' +
      rolesText +
      '</small>';
    adminMethodologyPassports.appendChild(card);
  });
  adminMethodologyBranches.innerHTML = '';
  (data.branches || []).forEach((item) => {
    const coveragePercent = Math.max(0, Math.min(100, Number(item.skill_coverage_percent) || 0));
    const competencyPercent = Math.max(0, Math.min(100, Number(item.competency_coverage_percent) || 0));
    const card = document.createElement('article');
    card.className = 'card admin-methodology-branch-card';
    card.innerHTML =
      '<div class="admin-methodology-branch-head">' +
      '<strong>' +
      item.role_name +
      '</strong>' +
      '<span>' +
      item.ready_case_count +
      '/' +
      item.case_count +
      ' кейсов</span>' +
      '</div>' +
      '<div class="admin-methodology-branch-stat">' +
      '<span>Покрытие навыков</span><strong>' +
      coveragePercent +
      '%</strong>' +
      '</div>' +
      '<div class="admin-report-score-track"><span style="width:' +
      coveragePercent +
      '%"></span></div>' +
      '<div class="admin-methodology-branch-stat secondary">' +
      '<span>Покрытие компетенций</span><strong>' +
      competencyPercent +
      '%</strong>' +
      '</div>' +
      '<div class="admin-report-score-track warm"><span style="width:' +
      competencyPercent +
      '%"></span></div>';
    adminMethodologyBranches.appendChild(card);
  });

  adminMethodologyCoverageBody.innerHTML = '';
  (data.coverage || []).forEach((item) => {
    const row = document.createElement('div');
    row.className = 'admin-methodology-coverage-row';
    row.innerHTML =
      '<span>' +
      item.competency_name +
      '</span>' +
      '<span>' +
      item.linear_value +
      '</span>' +
      '<span>' +
      item.manager_value +
      '</span>' +
      '<span>' +
      item.leader_value +
      '</span>';
    adminMethodologyCoverageBody.appendChild(row);
  });

  if (adminMethodologySummary) {
    const totalCases = filteredCases.length;
    const qaReadyCount = filteredCases.filter((item) => item.qa_ready).length;
    const readyCount = filteredCases.filter((item) => item.status === 'ready').length;
    adminMethodologySummary.innerHTML =
      '<div><span>Кейсов в выборке</span><strong>' +
      totalCases +
      '</strong></div>' +
      '<div><span>Ready</span><strong>' +
      readyCount +
      '</strong></div>' +
      '<div><span>QA ready</span><strong>' +
      qaReadyCount +
      '</strong></div>';
  }

  if (adminMethodologySkillGaps) {
    const items = Array.isArray(data.skill_gaps) ? data.skill_gaps : [];
    renderAdminMethodologyPagedRiskList(adminMethodologySkillGaps, {
      key: 'skillGaps',
      items,
      emptyText: 'Критичных дефицитов покрытия не найдено.',
      renderItem: (item) => {
        const card = document.createElement('article');
        card.className = 'admin-methodology-risk-item ' + (item.severity === 'critical' ? 'critical' : 'warning');
        card.innerHTML =
          '<div class="admin-methodology-risk-head">' +
          '<strong>' +
          item.skill_name +
          '</strong>' +
          '<span>' +
          item.role_name +
          '</span>' +
          '</div>' +
          '<p>' +
          item.competency_name +
          '</p>' +
          '<small>' +
          (item.ready_case_count === 0 ? 'Нет ready-кейсов' : 'Только ' + item.ready_case_count + ' ready-кейс') +
          '</small>';
        return card;
      },
    });
  }

  if (adminMethodologySinglePoints) {
    const items = Array.isArray(data.single_point_skills) ? data.single_point_skills : [];
    renderAdminMethodologyPagedRiskList(adminMethodologySinglePoints, {
      key: 'singlePoints',
      items,
      emptyText: 'Навыки не завязаны на один тип кейса.',
      renderItem: (item) => {
        const card = document.createElement('article');
        card.className = 'admin-methodology-risk-item single-point';
        card.innerHTML =
          '<div class="admin-methodology-risk-head">' +
          '<strong>' +
          item.skill_name +
          '</strong>' +
          '<span>' +
          ((item.type_codes || []).join(', ') || '—') +
          '</span>' +
          '</div>' +
          '<p>' +
          item.competency_name +
          '</p>' +
          '<small>' +
          ((item.role_names || []).join(', ') || 'Роли не указаны') +
          ' · ' +
          item.ready_case_count +
          ' ready-кейс(ов)</small>';
        return card;
      },
    });
  }

  if (adminMethodologyCaseQuality) {
    const items = Array.isArray(data.case_quality_hotspots) ? data.case_quality_hotspots : [];
    renderAdminMethodologyPagedRiskList(adminMethodologyCaseQuality, {
      key: 'caseQuality',
      items,
      emptyText: 'Пока недостаточно данных прохождений для аналитики качества кейсов.',
      renderItem: (item) => {
        const coverageText =
          item.avg_block_coverage_percent == null
            ? 'покрытие структуры еще не накоплено'
            : 'среднее покрытие ' + Math.round(item.avg_block_coverage_percent) + '%';
        const card = document.createElement('article');
        card.className = 'admin-methodology-risk-item case-quality';
        card.innerHTML =
          '<div class="admin-methodology-risk-head">' +
          '<strong>' +
          item.title +
          '</strong>' +
          '<span>' +
          item.case_id_code +
          ' · ' +
          item.type_code +
          '</span>' +
          '</div>' +
          '<p>' +
          item.issue_label +
          '</p>' +
          '<small>' +
          item.assessments_count +
          ' оценок · ' +
          'red flags ' +
          item.avg_red_flag_count.toFixed(1) +
          ' · ' +
          'missing blocks ' +
          item.avg_missing_blocks_count.toFixed(1) +
          ' · ' +
          coverageText +
          ' · ' +
          'низкие уровни ' +
          item.low_level_rate_percent +
          '%' +
          '</small>';
        return card;
      },
    });
  }

  renderAdminMethodologyTab();
};

export const openAdminMethodology = async () => {
  setCurrentScreen('admin-methodology');
  persistAssessmentContext();
  syncUrlState('admin-methodology');
  hideAllPanels();
  adminMethodologyPanel.classList.remove('hidden');
  if (adminMethodologyCases) {
    adminMethodologyCases.innerHTML = '<p class="report-empty-state">Загружаем методическую модель...</p>';
  }
  try {
    if (!state.adminMethodology) {
      await loadAdminMethodology();
    }
    renderAdminMethodology();
    if (state.adminMethodologyDetailCode) {
      await openAdminMethodologyDetail(state.adminMethodologyDetailCode);
    }
  } catch (error) {
    if (adminMethodologyCases) {
      adminMethodologyCases.innerHTML = '<p class="report-empty-state">' + error.message + '</p>';
    }
  }
};


export const initAdminMethodology = () => {
  if (adminMethodologyScenarioTemplate) {
    adminMethodologyScenarioTemplate.addEventListener('click', () => {
      state.adminMethodologyScenarioMode = 'template';
      renderAdminMethodologyDetail();
    });
  }
  if (adminMethodologyScenarioPreview) {
    adminMethodologyScenarioPreview.addEventListener('click', () => {
      state.adminMethodologyScenarioMode = 'preview';
      renderAdminMethodologyDetail();
    });
  }
};

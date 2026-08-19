import { readApiResponse } from '../../api.js';

const byId = (id) => document.getElementById(id);

const templates = {
  methodology: {
    schema_version: 1,
    competencies: [
      { code: 'communication', evaluator: 'evaluation.communication', evaluator_version: 1 },
      { code: 'teamwork', evaluator: 'evaluation.teamwork', evaluator_version: 1 },
      { code: 'creativity', evaluator: 'evaluation.creativity', evaluator_version: 1 },
      { code: 'critical_thinking', evaluator: 'evaluation.critical_thinking', evaluator_version: 1 },
    ],
    aggregation: { component: 'evaluation.aggregate', component_version: 1 },
  },
  scenario: {
    schema_version: 1,
    initial_stage: 'prepare_profile',
    stages: [
      { id: 'prepare_profile', component: 'profile.prepare', component_version: 1, on_success: 'select_cases' },
      { id: 'select_cases', component: 'cases.select', component_version: 1, on_success: 'personalize_cases' },
      { id: 'personalize_cases', component: 'cases.personalize', component_version: 1, execution: 'parallel', on_success: 'interview' },
      { id: 'interview', component: 'interview.case_dialog', component_version: 1, on_success: 'evaluate_competencies' },
      { id: 'evaluate_competencies', component: 'evaluation.run_methodology_evaluators', component_version: 1, execution: 'parallel', on_success: 'aggregate' },
      { id: 'aggregate', component: 'evaluation.aggregate', component_version: 1, on_success: 'build_report' },
      { id: 'build_report', component: 'report.build', component_version: 1, on_success: 'complete_session' },
    ],
  },
};

const authoringState = {
  loaded: false,
  methodology: [],
  scenario: [],
  configurations: [],
  selected: null,
};

const request = async (url, options = {}, fallback = 'Операция authoring не выполнена.') => {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: options.body ? { 'Content-Type': 'application/json', ...(options.headers || {}) } : options.headers,
  });
  return readApiResponse(response, fallback);
};

const showStatus = (message, isError = false) => {
  const node = byId('admin-definition-status');
  if (!node) return;
  node.textContent = message;
  node.classList.remove('hidden');
  node.classList.toggle('failed', isError);
};

const parseDefinition = () => {
  try {
    return JSON.parse(byId('admin-definition-json').value || '{}');
  } catch (error) {
    throw new Error('Definition JSON содержит ошибку: ' + error.message);
  }
};

const setEditorMode = (selection = null) => {
  authoringState.selected = selection;
  const type = selection?.entityType || byId('admin-definition-type').value || 'methodology';
  byId('admin-definition-type').value = type;
  byId('admin-definition-type').disabled = Boolean(selection);
  byId('admin-definition-code').value = selection?.code || '';
  byId('admin-definition-code').disabled = Boolean(selection);
  byId('admin-definition-name').value = selection?.name || '';
  byId('admin-definition-name').disabled = Boolean(selection);
  byId('admin-definition-description').value = selection?.description || '';
  byId('admin-definition-json').value = JSON.stringify(selection?.definition_json || templates[type], null, 2);
  byId('admin-definition-editor-title').textContent = selection
    ? `${selection.name} · v${selection.version}`
    : `Новый ${type === 'scenario' ? 'сценарий' : 'методология'}`;
  byId('admin-definition-save').textContent = selection ? 'Сохранить draft' : 'Создать';
  byId('admin-definition-save').disabled = Boolean(selection && selection.status !== 'draft');
  byId('admin-definition-validate').disabled = !selection;
  byId('admin-definition-submit').disabled = !selection || selection.status !== 'draft';
  byId('admin-definition-publish').disabled = !selection || selection.status !== 'ready_for_review';
};

const makeAction = (label, handler, primary = false) => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = primary ? 'primary-button compact-primary' : 'ghost-button compact-ghost';
  button.textContent = label;
  button.addEventListener('click', handler);
  return button;
};

const renderVersionList = (entityType) => {
  const container = byId(entityType === 'scenario' ? 'admin-scenario-version-list' : 'admin-methodology-version-list');
  if (!container) return;
  container.innerHTML = '';
  const rows = authoringState[entityType] || [];
  if (!rows.length) {
    container.innerHTML = '<p class="report-empty-state">Версии недоступны или отсутствуют.</p>';
    return;
  }
  rows.forEach((row) => {
    const item = document.createElement('article');
    item.className = 'admin-definition-item';
    const summary = document.createElement('div');
    summary.innerHTML = `<strong></strong><span class="admin-definition-status-chip ${row.status}"></span><small></small>`;
    summary.querySelector('strong').textContent = `${row.name} · v${row.version}`;
    summary.querySelector('span').textContent = row.status;
    summary.querySelector('small').textContent = row.code;
    const actions = document.createElement('div');
    actions.className = 'admin-definition-item-actions';
    actions.appendChild(makeAction('Открыть', () => setEditorMode({ ...row, entityType })));
    actions.appendChild(makeAction('Клонировать', async () => {
      try {
        const created = await request(`/users/admin/assessment-definitions/${entityType}/${row.id}/clone`, {
          method: 'POST', body: JSON.stringify({ description: `Draft from v${row.version}` }),
        });
        await loadDefinitionAuthoring(true);
        setEditorMode({ ...created, code: row.code, name: row.name, entityType });
      } catch (error) { showStatus(error.message, true); }
    }));
    item.append(summary, actions);
    container.appendChild(item);
  });
};

const renderConfigurations = () => {
  const list = byId('admin-configuration-list');
  const methodologySelect = byId('admin-configuration-methodology');
  const scenarioSelect = byId('admin-configuration-scenario');
  if (!list || !methodologySelect || !scenarioSelect) return;
  methodologySelect.innerHTML = '';
  scenarioSelect.innerHTML = '';
  authoringState.methodology.filter((row) => row.status === 'published').forEach((row) => {
    const option = new Option(`${row.name} · v${row.version}`, row.id);
    methodologySelect.add(option);
  });
  authoringState.scenario.filter((row) => row.status === 'published').forEach((row) => {
    const option = new Option(`${row.name} · v${row.version}`, row.id);
    scenarioSelect.add(option);
  });
  list.innerHTML = '';
  if (!authoringState.configurations.length) {
    list.innerHTML = '<p class="report-empty-state">Конфигурации пока не созданы или недоступны для этой роли.</p>';
  }
  authoringState.configurations.forEach((row) => {
    const item = document.createElement('article');
    item.className = 'admin-definition-item';
    const summary = document.createElement('div');
    summary.innerHTML = '<strong></strong><span class="admin-definition-status-chip"></span><small></small>';
    summary.querySelector('strong').textContent = row.name;
    summary.querySelector('span').textContent = row.status + (row.is_default ? ' · default' : '');
    summary.querySelector('small').textContent = row.code;
    item.appendChild(summary);
    if (row.status === 'draft') {
      const actions = document.createElement('div');
      actions.className = 'admin-definition-item-actions';
      actions.appendChild(makeAction('Опубликовать', () => publishConfiguration(row.id, false)));
      actions.appendChild(makeAction('Опубликовать default', () => publishConfiguration(row.id, true), true));
      item.appendChild(actions);
    }
    list.appendChild(item);
  });
};

const renderDefinitionAuthoring = () => {
  renderVersionList('methodology');
  renderVersionList('scenario');
  renderConfigurations();
};

export const loadDefinitionAuthoring = async (force = false) => {
  if (authoringState.loaded && !force) return;
  const results = await Promise.allSettled([
    request('/users/admin/assessment-definitions/methodology', {}, 'Не удалось загрузить методологии.'),
    request('/users/admin/assessment-definitions/scenario', {}, 'Не удалось загрузить сценарии.'),
    request('/users/admin/assessment-configurations', {}, 'Не удалось загрузить конфигурации.'),
  ]);
  authoringState.methodology = results[0].status === 'fulfilled' ? results[0].value : [];
  authoringState.scenario = results[1].status === 'fulfilled' ? results[1].value : [];
  authoringState.configurations = results[2].status === 'fulfilled' ? results[2].value : [];
  authoringState.loaded = true;
  renderDefinitionAuthoring();
  const rejected = results.find((result) => result.status === 'rejected');
  if (rejected) showStatus(rejected.reason.message, true);
};

const saveDefinition = async () => {
  const selected = authoringState.selected;
  const entityType = selected?.entityType || byId('admin-definition-type').value;
  const definition = parseDefinition();
  const payload = {
    definition,
    description: byId('admin-definition-description').value.trim() || null,
    comment: selected ? 'Updated through methodologist UI' : 'Created through methodologist UI',
  };
  let result;
  if (selected) {
    result = await request(`/users/admin/assessment-definitions/${entityType}/${selected.id}`, {
      method: 'PUT', body: JSON.stringify(payload),
    });
  } else {
    result = await request(`/users/admin/assessment-definitions/${entityType}`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, code: byId('admin-definition-code').value.trim(), name: byId('admin-definition-name').value.trim() }),
    });
  }
  await loadDefinitionAuthoring(true);
  setEditorMode({ ...result, entityType, code: result.code || byId('admin-definition-code').value, name: result.name || byId('admin-definition-name').value });
  showStatus('Draft сохранён.');
};

const transitionDefinition = async (action) => {
  const selected = authoringState.selected;
  if (!selected) return;
  const options = action === 'validate'
    ? { method: 'POST' }
    : { method: 'POST', body: JSON.stringify({ comment: `${action} through methodologist UI` }) };
  const result = await request(`/users/admin/assessment-definitions/${selected.entityType}/${selected.id}/${action}`, options);
  await loadDefinitionAuthoring(true);
  const updated = action === 'validate' ? selected : { ...result, entityType: selected.entityType, code: selected.code, name: selected.name };
  setEditorMode(updated);
  showStatus(action === 'validate' ? 'Definition валиден, checksum совпадает.' : `Статус: ${updated.status}`);
};

const publishConfiguration = async (id, makeDefault) => {
  try {
    await request(`/users/admin/assessment-configurations/${id}/publish`, {
      method: 'POST', body: JSON.stringify({ make_default: makeDefault, comment: 'Published through methodologist UI' }),
    });
    await loadDefinitionAuthoring(true);
    showStatus(makeDefault ? 'Конфигурация опубликована и назначена default.' : 'Конфигурация опубликована.');
  } catch (error) { showStatus(error.message, true); }
};

const createConfiguration = async () => {
  await request('/users/admin/assessment-configurations', {
    method: 'POST',
    body: JSON.stringify({
      code: byId('admin-configuration-code').value.trim(),
      name: byId('admin-configuration-name').value.trim(),
      methodology_version_id: Number(byId('admin-configuration-methodology').value),
      scenario_version_id: Number(byId('admin-configuration-scenario').value),
      comment: 'Created through methodologist UI',
    }),
  });
  await loadDefinitionAuthoring(true);
  showStatus('Draft-конфигурация создана.');
};

export const initDefinitionAuthoring = () => {
  byId('admin-definition-type')?.addEventListener('change', () => setEditorMode());
  byId('admin-definition-new')?.addEventListener('click', () => setEditorMode());
  byId('admin-definition-refresh')?.addEventListener('click', () => void loadDefinitionAuthoring(true));
  byId('admin-definition-save')?.addEventListener('click', () => saveDefinition().catch((error) => showStatus(error.message, true)));
  byId('admin-definition-validate')?.addEventListener('click', () => transitionDefinition('validate').catch((error) => showStatus(error.message, true)));
  byId('admin-definition-submit')?.addEventListener('click', () => transitionDefinition('submit').catch((error) => showStatus(error.message, true)));
  byId('admin-definition-publish')?.addEventListener('click', () => transitionDefinition('publish').catch((error) => showStatus(error.message, true)));
  byId('admin-configuration-create')?.addEventListener('click', () => createConfiguration().catch((error) => showStatus(error.message, true)));
  setEditorMode();
};

import { readApiResponse } from '../../api.js';
import { escapeHtml } from '../../utils/format.js';

let initialized = false;

export const initializeM5Lab = async () => {
  const root = document.getElementById('m5-lab');
  if (!root || initialized) return;
  const status = root.querySelector('[data-m5-status]');
  try {
    const catalog = await readApiResponse(await fetch('/users/admin/m5-lab'), 'Не удалось загрузить M5.');
    const roles = root.querySelector('[data-m5-role]');
    const cases = root.querySelector('[data-m5-case]');
    roles.innerHTML = catalog.profiles.map((p) => `<option value="${p.id}" data-role="${escapeHtml(p.base_role || '')}">${escapeHtml(p.full_name || `Профиль ${p.id}`)} · ${escapeHtml(p.base_role || 'роль не определена')}</option>`).join('');
    const refreshCases = () => {
      const role = roles.selectedOptions[0]?.dataset.role;
      const available = catalog.cases.filter((c) => c.base_role === role);
      cases.innerHTML = available.map((c) => `<option value="${escapeHtml(c.case_id)}">${escapeHtml(c.case_id)} · ${escapeHtml(c.title)} · ${c.indicator_ids.length} целей</option>`).join('');
    };
    roles.addEventListener('change', refreshCases);
    refreshCases();
    status.textContent = catalog.profiles.length ? 'Готово. Выберите совместимый профиль и Case.' : 'Нет готовых M4 PersonalizedProfile для QA.';
    const publishRolesButton = document.createElement('button');
    publishRolesButton.type = 'button';
    publishRolesButton.className = 'ghost-button';
    publishRolesButton.textContent = 'Опубликовать проверенный M3 v1.1 на test';
    root.querySelector('[data-m5-migrate-profile]').before(publishRolesButton);
    publishRolesButton.addEventListener('click', async () => {
      try {
        status.textContent = 'Проверяем checksum и публикуем M3 BaseRoles…';
        const result = await readApiResponse(await fetch('/users/admin/m5-lab/publish-m3-base-roles', { method: 'POST' }), 'Не удалось опубликовать M3 BaseRoles.');
        status.textContent = `M3 publication ${result.publication_id}: опубликовано версий ${result.version_ids.length}.`;
      } catch (error) { status.textContent = error.message; }
    });
    root.querySelector('[data-m5-migrate-profile]').addEventListener('click', async () => {
      try {
        status.textContent = 'Фиксируем текущий test-профиль в M4…';
        const migrated = await readApiResponse(await fetch('/users/admin/m5-lab/migrate-current-profile', { method: 'POST' }), 'Не удалось создать M4 QA-профиль.');
        status.textContent = `M4 PersonalizedProfile ${migrated.personalized_profile_id} сохранён. Обновляем каталог…`;
        window.location.reload();
      } catch (error) { status.textContent = error.message; }
    });
    const result = root.querySelector('[data-m5-result]');
    const buttons = [...root.querySelectorAll('[data-m5-run]')];
    const show = (row) => {
      const card = document.createElement('article');
      card.className = 'card card--lg';
      const snapshot = row.snapshot_json;
      card.innerHTML = `<h3>${escapeHtml(snapshot.case_ref.id)} · ${escapeHtml(snapshot.base_role)}</h3>
        <p>${escapeHtml(row.as_status || row.status)} · run ${escapeHtml(row.run_id)} · AS ${escapeHtml(row.assessment_situation_id)}</p>
        <p>${escapeHtml(row.participant_payload?.initial_situation || snapshot.participant_payload?.initial_situation || '').replaceAll('\n', '<br>')}</p>
        <p>Целей: ${snapshot.indicator_targets.length}. Admission: ${escapeHtml(snapshot.admission.code)}. Технический QA не меняет решение допуска.</p>
        <label class="admin-prompt-lab-field">Реплика оцениваемого<textarea data-m5-turn rows="3"></textarea></label>
        <div class="admin-prompt-lab-actions">
          <button type="button" class="primary-button" data-m5-send>Сохранить Turn</button>
          <button type="button" class="ghost-button" data-m5-action="pause">Пауза</button>
          <button type="button" class="ghost-button" data-m5-action="resume">Продолжить</button>
          <button type="button" class="ghost-button" data-m5-action="scenario_end">Конец сценария</button>
          <button type="button" class="ghost-button" data-m5-action="terminate">Прекратить</button>
          <button type="button" class="ghost-button" data-m5-action="close">Закрыть AS</button>
        </div>
        <details><summary>Сохранённые входные данные, результат и проверки</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escapeHtml(JSON.stringify(row, null, 2))}</pre></details>`;
      const asId = row.assessment_situation_id;
      card.querySelector('[data-m5-send]').addEventListener('click', async () => {
        const content = card.querySelector('[data-m5-turn]').value.trim();
        if (!content) return;
        await readApiResponse(await fetch(`/users/admin/m5-runtime/situations/${encodeURIComponent(asId)}/turns`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ request_id: crypto.randomUUID(), turn_id: crypto.randomUUID(), content }),
        }), 'Не удалось сохранить Turn.');
        show(await readApiResponse(await fetch(`/users/admin/m5-lab/runs/${encodeURIComponent(row.run_id)}`), 'Не удалось перечитать trace.'));
      });
      card.querySelectorAll('[data-m5-action]').forEach((actionButton) => actionButton.addEventListener('click', async () => {
        await readApiResponse(await fetch(`/users/admin/m5-runtime/situations/${encodeURIComponent(asId)}/transitions`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ request_id: crypto.randomUUID(), action: actionButton.dataset.m5Action, reason: 'Prompt Lab QA' }),
        }), 'Не удалось изменить состояние AS.');
        show(await readApiResponse(await fetch(`/users/admin/m5-lab/runs/${encodeURIComponent(row.run_id)}`), 'Не удалось перечитать trace.'));
      }));
      result.prepend(card);
    };
    for (const button of buttons) {
      button.addEventListener('click', async () => {
        buttons.forEach((b) => { b.disabled = true; });
        const selectedProfileId = Number(roles.value);
        const selectedRole = roles.selectedOptions[0]?.dataset.role;
        const selected = button.dataset.m5Run === 'batch'
          ? catalog.cases.filter((c) => c.base_role === selectedRole).map((c) => c.case_id)
          : [cases.value];
        let failures = 0;
        try {
          for (let index = 0; index < selected.length; index += 1) {
            const runId = crypto.randomUUID();
            root.querySelector('[data-m5-run-id]').value = runId;
            status.textContent = `Подготовка QA AS ${index + 1} из ${selected.length}. ID: ${runId}`;
            const response = await fetch('/users/admin/m5-lab/runs', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ run_id: runId, case_id: selected[index], case_version: 'v0.1', personalized_profile_id: selectedProfileId }),
            });
            const row = await readApiResponse(response, 'Не удалось выполнить прогон M5.');
            show(row);
            if ((row.as_status || row.status) !== 'active') failures += 1;
          }
          status.textContent = `Завершено: ${selected.length}. Без успешного результата: ${failures}. Артефакты сохранены в БД.`;
        } catch (error) {
          status.textContent = `${error.message} Проверьте сохранённый прогон по ID перед повторным запуском.`;
        } finally {
          buttons.forEach((b) => { b.disabled = false; });
        }
      });
    }
    root.querySelector('[data-m5-open]').addEventListener('click', async () => {
      const runId = root.querySelector('[data-m5-run-id]').value.trim();
      try {
        const row = await readApiResponse(await fetch(`/users/admin/m5-lab/runs/${encodeURIComponent(runId)}`), 'Не удалось открыть прогон.');
        show(row);
        status.textContent = 'Прогон прочитан из БД.';
      } catch (error) { status.textContent = error.message; }
    });
    initialized = true;
  } catch (error) { status.textContent = error.message; }
};

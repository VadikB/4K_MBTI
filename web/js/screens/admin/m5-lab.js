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
    const mode = root.querySelector('[data-m5-mode]');
    roles.innerHTML = catalog.roles.map((r) => `<option value="${escapeHtml(r.code)}">${escapeHtml(r.name)}</option>`).join('');
    cases.innerHTML = catalog.cases.map((c) => `<option value="${escapeHtml(c.case_id)}">${escapeHtml(c.case_id)} · ${escapeHtml(c.title)}</option>`).join('');
    mode.querySelector('[value="llm"]').disabled = !catalog.llm_available;
    status.textContent = catalog.llm_available ? 'Готово. Доступны шаблонная сборка и LLM-генерация.' : 'Готово. LLM не настроен; доступна шаблонная сборка.';
    const result = root.querySelector('[data-m5-result]');
    const buttons = [...root.querySelectorAll('[data-m5-run]')];
    const show = (row) => {
      const card = document.createElement('article');
      card.className = 'card card--lg';
      const input = row.input_json;
      card.innerHTML = `<h3>${escapeHtml(input.case.case_id)} · ${escapeHtml(input.profile.role_name)}</h3>
        <p>${escapeHtml(row.status)} · ${escapeHtml(row.run_id)} · ${escapeHtml(input.mode)}</p>
        <p>${escapeHtml(row.output_json?.presentation || row.error_code || 'Генерация ещё выполняется. Откройте прогон позже по ID.').replaceAll('\n', '<br>')}</p>
        <p>Целей: ${input.observability.length}. Методический QA: NOT_RUN. Допуска к оценке нет.</p>
        <details><summary>Сохранённые входные данные, результат и проверки</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escapeHtml(JSON.stringify(row, null, 2))}</pre></details>`;
      result.prepend(card);
    };
    for (const button of buttons) {
      button.addEventListener('click', async () => {
        buttons.forEach((b) => { b.disabled = true; });
        const selectedRole = roles.value;
        const selectedMode = mode.value;
        const selected = button.dataset.m5Run === 'batch'
          ? catalog.cases.filter((c) => c.roles.includes(selectedRole)).map((c) => c.case_id)
          : [cases.value];
        let failures = 0;
        try {
          for (let index = 0; index < selected.length; index += 1) {
            const runId = crypto.randomUUID();
            root.querySelector('[data-m5-run-id]').value = runId;
            status.textContent = `Генерация ${index + 1} из ${selected.length}. ID: ${runId}`;
            const response = await fetch('/users/admin/m5-lab/runs', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ run_id: runId, case_id: selected[index], base_role: selectedRole, mode: selectedMode }),
            });
            const row = await readApiResponse(response, 'Не удалось выполнить прогон M5.');
            show(row);
            if (row.status !== 'completed') failures += 1;
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

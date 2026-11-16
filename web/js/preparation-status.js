// Participant-safe status. Durations use persisted server times and advance in whole minutes.
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
const kinds = { assessment: 'Подготовка оценки', next: 'Подготовка следующей ситуации', report: 'Подготовка отчёта' };
const date = (value) => value ? new Date(value).toLocaleString('ru-RU') : 'нет подтверждённых сведений';
const minutes = (value, now) => value ? `${Math.max(0, Math.floor((now - Date.parse(value)) / 60000))} мин.` : 'нет подтверждённых сведений';
export const preparationText = (model, { now = Date.now(), readError = false } = {}) => {
  if (!model) return '';
  const lines = [kinds[model.kind] || 'Подготовка', `Сейчас: ${model.stage_label}`, model.explanation];
  const active = ['queued', 'running', 'processing'].includes(model.status);
  if (readError) lines.push('Не удалось обновить состояние. Ниже — последние полученные сведения.');
  else if (active && model.read_at && now - Date.parse(model.read_at) > 90000) lines.push('Сведения могут быть устаревшими. Проверьте состояние.');
  if (active && model.freshness === 'unconfirmed') lines.push('Сейчас не можем подтвердить, что обработка продолжается.');
  const noticeStart = model.stage_started_at || model.started_at;
  if (active && (model.delayed || (noticeStart && now - Date.parse(noticeStart) >= model.delay_notice_seconds * 1000))) {
    lines.push(`Подготовка занимает больше времени. Текущий этап: ${model.stage_label}.`);
  }
  const measuredAt = active ? now : Date.parse(model.finished_at);
  lines.push(Number.isFinite(measuredAt) ? `С начала подготовки: ${minutes(model.started_at, measuredAt)} ${model.stage_started_at ? `Последняя смена этапа: ${minutes(model.stage_started_at, measuredAt)} назад.` : 'Время последней смены этапа неизвестно.'}` : 'Время завершения не зафиксировано.');
  return lines.filter(Boolean).join('\n');
};
export const preparationCopy = (model, options = {}) => [preparationText(model, options),
  `Начало подготовки: ${date(model.started_at)}`,
  `Последний подтверждённый этап: ${model.stage_label}. Время смены: ${date(model.last_progress_at)}`,
  `Последнее успешное чтение: ${date(model.read_at)}. Актуальность: ${options.readError ? 'не удалось обновить' : model.freshness === 'unconfirmed' ? 'работа не подтверждена' : 'состояние получено'}.`,
  `Код обращения: ${model.reference}`].join('\n');

export const preparationHtml = (model) => model ? `<section class="preparation-status" data-preparation-status data-preparation-reference-id="${escape(model.reference)}">
  <p data-preparation-stage><strong>${escape('Сейчас: ' + model.stage_label)}</strong></p>
  <p data-preparation-explanation>${escape(model.explanation)}</p>
  <p data-preparation-notice></p><p data-preparation-duration></p>
  <details><summary>Сведения о подготовке</summary>
    <p data-preparation-reference></p><p data-preparation-freshness></p>
    <button type="button" data-preparation-copy>Скопировать сведения</button>
    <span data-preparation-copied role="status"></span>
  </details></section>` : '';

const clocks = new Map();
let removalObserver;
const watchClock = (root, model, options) => {
  window.clearTimeout(clocks.get(root));
  if (!['queued','running','processing'].includes(model.status)) { clocks.delete(root); return; }
  const now = Date.now(), noticeAt = Date.parse(model.stage_started_at || model.started_at) + model.delay_notice_seconds * 1000;
  const delay = Math.min(60000 - now % 60000, noticeAt > now ? noticeAt - now : 60000);
  const timer = window.setTimeout(() => {
    if (root.isConnected) renderPreparation(root, model, options);
    else clocks.delete(root);
  }, delay);
  clocks.set(root, timer);
  if (!removalObserver) {
    removalObserver = new MutationObserver(() => {
      for (const [node, id] of clocks) if (!node.isConnected) { window.clearTimeout(id); clocks.delete(node); }
      if (!clocks.size) { removalObserver.disconnect(); removalObserver = null; }
    });
    removalObserver.observe(document.body, { childList: true, subtree: true });
  }
};

export const renderPreparation = (container, model, options = {}) => {
  if (!container || !model) return;
  let root = container.matches?.('[data-preparation-status]') ? container : container.querySelector('[data-preparation-status]');
  if (!root) { container.insertAdjacentHTML('beforeend', preparationHtml(model)); root = container.querySelector('[data-preparation-status]'); }
  const text = preparationText(model, options).split('\n');
  root.querySelector('[data-preparation-stage] strong').textContent = `Сейчас: ${model.stage_label}`;
  root.querySelector('[data-preparation-explanation]').textContent = model.explanation;
  root.querySelector('[data-preparation-notice]').textContent = text.slice(3, -1).join(' ');
  root.querySelector('[data-preparation-duration]').textContent = text.at(-1);
  root.querySelector('[data-preparation-reference]').textContent = `Код обращения: ${model.reference}`;
  root.querySelector('[data-preparation-freshness]').textContent = `Последнее успешное чтение: ${date(model.read_at)}`;
  watchClock(root, model, options);
  root.querySelector('[data-preparation-copy]').onclick = async () => {
    try {
      await navigator.clipboard.writeText(preparationCopy(model, options));
      root.querySelector('[data-preparation-copied]').textContent = 'Сведения скопированы.';
    } catch { root.querySelector('[data-preparation-copied]').textContent = 'Не удалось скопировать сведения. Попробуйте ещё раз.'; }
  };
};

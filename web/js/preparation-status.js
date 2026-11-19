// Public preparation facts: a read failure never changes an answer receipt.
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
const kinds = { assessment: 'Подготовка оценки', next: 'Подготовка следующей ситуации', report: 'Подготовка отчёта' };
const date = (value) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString('ru-RU') : 'нет подтверждённых сведений';
const minutes = (value, now) => value && Number.isFinite(Date.parse(value)) && Number.isFinite(now)
  ? `${Math.max(0, Math.floor((now - Date.parse(value)) / 60000))} мин` : 'неизвестно';
const activeStatus = (model) => ['queued', 'running', 'processing'].includes(model.status);
export const preparationPresentation = (model, { now = Date.now(), readError = false } = {}) => {
  const active = activeStatus(model);
  const stale = active && (!model.read_at || now - Date.parse(model.read_at) > 90000);
  const unconfirmed = active && model.freshness === 'unconfirmed';
  const uncertain = readError || stale || unconfirmed;
  const failed = model.status === 'failed';
  const notices = [];
  if (failed) notices.push('Не удалось завершить ' + ({ assessment: 'подготовку оценки', next: 'подготовку следующей ситуации', report: 'подготовку отчёта' }[model.kind] || 'подготовку') + '.');
  if (readError) notices.push('Не удалось обновить состояние. Показаны последние полученные сведения');
  else if (stale) notices.push('Сведения могут быть устаревшими. Проверьте состояние');
  if (unconfirmed && !readError && !stale) notices.push('Сейчас не можем подтвердить, что подготовка продолжается');
  const noticeStart = Date.parse(model.stage_started_at || model.started_at);
  if (active && !uncertain && (model.delayed || now - noticeStart >= model.delay_notice_seconds * 1000)) {
    notices.push('Подготовка занимает больше времени');
  }
  const measuredAt = active && !uncertain ? now : Date.parse(active ? model.read_at : model.finished_at || model.read_at);
  return {
    stage: `${uncertain ? 'Последний известный этап: ' : ''}${model.stage_label}`,
    notices, failed, uncertain,
    duration: `Подготовка: ${minutes(model.started_at, measuredAt)} · Этап без изменений: ${minutes(model.stage_started_at, measuredAt)}${active && uncertain ? ' (на момент обновления)' : ''}`,
  };
};
export const preparationText = (model, options = {}) => {
  if (!model) return '';
  const view = preparationPresentation(model, options);
  return [kinds[model.kind] || 'Подготовка', view.stage, model.explanation, ...view.notices, view.duration].filter(Boolean).join('\n');
};
export const preparationCopy = (model, options = {}) => [preparationText(model, options),
  `Начало подготовки: ${date(model.started_at)}`,
  `Последнее изменение этапа: ${date(model.last_progress_at || model.stage_started_at)}`,
  `Сведения обновлены: ${date(model.read_at)}`,
  `Номер подготовки: ${model.reference}`].join('\n');

export const preparationHtml = (model, { compact = false } = {}) => model ? `<section class="preparation-status${compact ? ' preparation-status--compact' : ''}" data-preparation-status data-preparation-reference-id="${escape(model.reference)}">
  <div class="preparation-summary"><p data-preparation-stage><strong>${escape(model.stage_label)}</strong></p>
    <p data-preparation-explanation>${escape(model.explanation)}</p>
    <div data-preparation-notice></div><p data-preparation-duration></p></div>
  <div data-preparation-time></div><div data-preparation-actions></div>
  <details${model.status === 'failed' ? ' open' : ''}><summary>Сведения о подготовке</summary><div class="preparation-details">
    <dl><div><dt>Вид подготовки</dt><dd data-preparation-kind></dd></div>
      <div><dt>Этап</dt><dd data-preparation-detail-stage></dd></div>
      <div><dt>Начало подготовки</dt><dd data-preparation-started></dd></div>
      <div><dt>Последнее изменение этапа</dt><dd data-preparation-changed></dd></div>
      <div><dt>Сведения обновлены</dt><dd data-preparation-freshness></dd></div>
      <div><dt>Номер подготовки</dt><dd data-preparation-reference></dd></div></dl>
    <p>Поможет найти эту подготовку при разборе задержки или ошибки</p>
    <button type="button" data-preparation-copy>Скопировать сведения</button>
    <span data-preparation-copied role="status"></span>
  </div></details></section>` : '';

const clocks = new Map();
let removalObserver;
const watchClock = (root, model, options) => {
  window.clearTimeout(clocks.get(root));
  if (!activeStatus(model)) { clocks.delete(root); return; }
  const now = Date.now(), noticeAt = Date.parse(model.stage_started_at || model.started_at) + model.delay_notice_seconds * 1000;
  const staleAt = Date.parse(model.read_at) + 90001;
  const boundaries = [60000 - now % 60000, noticeAt - now, staleAt - now].filter((n) => n > 0);
  const timer = window.setTimeout(() => {
    if (root.isConnected) renderPreparation(root, model, options);
    else clocks.delete(root);
  }, Math.min(...boundaries));
  clocks.set(root, timer);
  if (!removalObserver) {
    removalObserver = new MutationObserver(() => {
      for (const [node, id] of clocks) if (!node.isConnected) { window.clearTimeout(id); clocks.delete(node); }
      if (!clocks.size) { removalObserver.disconnect(); removalObserver = null; }
    });
    removalObserver.observe(document.body, { childList: true, subtree: true });
  }
};
const models = new WeakMap();
export const renderPreparation = (container, model, options = {}) => {
  if (!container || !model) return;
  let root = container.matches?.('[data-preparation-status]') ? container : container.querySelector('[data-preparation-status]');
  if (!root) { container.insertAdjacentHTML('beforeend', preparationHtml(model, options)); root = container.querySelector('[data-preparation-status]'); }
  const previous = models.get(root);
  // Timestamp ordering is per operation; old responses must not replace a newer read.
  if (previous?.reference === model.reference && Date.parse(previous.read_at) > Date.parse(model.read_at)) return;
  if (root.dataset.preparationReferenceId !== model.reference) {
    root.querySelector('details').open = false;
    root.querySelector('[data-preparation-copied]').textContent = '';
  }
  models.set(root, model);
  root.dataset.preparationReferenceId = model.reference;
  const view = preparationPresentation(model, options);
  root.classList.toggle('is-failed', view.failed);
  root.querySelector('[data-preparation-stage] strong').textContent = view.stage;
  root.querySelector('[data-preparation-explanation]').textContent = model.explanation || '';
  root.querySelector('[data-preparation-notice]').replaceChildren(...view.notices.map((line) => {
    const p = document.createElement('p'); p.textContent = line; return p;
  }));
  for (const [key, value] of Object.entries({ duration: view.duration, kind: kinds[model.kind] || 'Подготовка',
    'detail-stage': [model.stage_label, model.explanation].filter(Boolean).join('. '),
    reference: model.reference, freshness: date(model.read_at), started: date(model.started_at),
    changed: date(model.last_progress_at || model.stage_started_at) })) {
    const field = root.querySelector(`[data-preparation-${key}]`);
    // Preserve a selection in unchanged details while refreshing other facts.
    if (field.textContent !== value) field.textContent = value;
  }
  watchClock(root, model, options);
  root.querySelector('[data-preparation-copy]').onclick = async () => {
    try {
      await navigator.clipboard.writeText(preparationCopy(model, options));
      root.querySelector('[data-preparation-copied]').textContent = 'Сведения скопированы';
    } catch { root.querySelector('[data-preparation-copied]').textContent = 'Не удалось скопировать сведения. Попробуйте ещё раз'; }
  };
};

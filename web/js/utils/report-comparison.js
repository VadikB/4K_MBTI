import { escapeHtml } from './format.js';
import { bindReportPdf } from './report-download.js';

const number = (value, signed = false) => value == null ? '—' :
  `${signed && value > 0 ? '+' : ''}${Number(value).toFixed(2).replace('.', ',')}`;
const role = (ref) => ref?.name || ref?.title || ref?.role_name || 'Роль не указана';

// A view of the server projection only. Admission and differences never run here.
export const mountReportComparison = ({ node, comparison, isCurrent, buildRadar,
  fitLabels, formatDate, reasonLabels, outcomeLabels, initialState, onBack, onHistory }) => {
  const lifetime = new AbortController();
  const initial = initialState || new URLSearchParams();
  let direction = initial.get('cmp_direction') || 'all';
  let mode = initial.get('cmp_mode') || 'fill';
  if (!['fill', 'outline', 'bars'].includes(mode)) mode = 'fill';
  let selectedId = initial.get('cmp_skill');
  const expanded = new Set((initial.get('cmp_evidence') || '').split(',').filter(Boolean));
  const rows = comparison.skills;
  const groups = [...new Map(rows.map((row) => [String(row.competency_id), {
    id: String(row.competency_id), name: row.competency_name || 'Группа навыков',
  }])).values()];
  if (direction !== 'all' && !groups.some((group) => group.id === direction)) direction = 'all';
  const reason = (row) => reasonLabels[row.comparability.reason] || 'Сопоставимость не подтверждена.';
  const side = (row, key) => row[`${key}_result`];
  const label = (row, key) => side(row, key)?.label || outcomeLabels[side(row, key)?.outcome] || 'Полнота результата не сохранена';
  const limitations = (row, key, includeGlobal = false) => [...new Set([
    ...(side(row, key)?.reasons || []).map((item) => item.message).filter(Boolean),
    ...(side(row, key)?.limitations || []),
    ...(includeGlobal ? comparison[key].limitations || [] : []),
  ])];
  const status = (row, key) => `<strong>${number(row[key])}${row[key] == null ? '' : ' из 3'}</strong><small>${escapeHtml(label(row, key))}</small>`;
  const dates = Object.fromEntries(['previous', 'current'].map((key) => [key,
    formatDate(comparison[key].closed_at || comparison[key].created_at)]));
  const period = (key, heading) => `<div><dt>${heading}</dt><dd>${escapeHtml(comparison[key].program_name || 'Оценка 4К')}</dd><dd>${escapeHtml(dates[key])}</dd><dd>${escapeHtml(role(comparison[key].role_ref))}</dd></div>`;
  const save = () => {
    const url = new URL(window.location.href);
    url.searchParams.set('cmp_direction', direction);
    url.searchParams.set('cmp_mode', mode);
    if (selectedId) url.searchParams.set('cmp_skill', selectedId);
    if (expanded.size) url.searchParams.set('cmp_evidence', [...expanded].join(','));
    else url.searchParams.delete('cmp_evidence');
    window.history.replaceState({}, '', url.pathname + '?' + url.searchParams.toString());
  };
  const evidence = (row, key) => {
    const result = side(row, key);
    const claims = result?.claims || [];
    const ref = result?.skill_ref;
    const link = ref && result.present ? `/?${new URLSearchParams({ screen: 'report', report_id: ref.report_id,
      cycle_id: ref.cycle_id, skill_id: ref.skill_id })}` : null;
    return `<section class="m8-comparison-basis" data-result-side="${key}"><h5>${key === 'previous' ? 'Предыдущая' : 'Текущая'} · ${escapeHtml(dates[key])}</h5>${status(row, key)}
      ${limitations(row, key, true).map((text) => `<p class="m8-local-limitation">${escapeHtml(text)}</p>`).join('')}
      ${result?.completeness == null && row[key] != null ? '<p class="m8-local-limitation">Сведения о полноте отдельно не сохранены.</p>' : ''}
      <details data-comparison-evidence="${key}" ${expanded.has(key) ? 'open' : ''}><summary>Почему сделан такой вывод</summary>${claims.length ? claims.map((claim) => claim.kind === 'quote'
        ? `<p class="m8-evidence-caption">Ваш ответ в выбранной оценке</p><blockquote>${escapeHtml(claim.text)}</blockquote>`
        : `<p>${escapeHtml(claim.text)}</p>`).join('') : '<p>Дополнительные основания в этой публикации не сохранены.</p>'}
      ${claims.flatMap((claim) => claim.limitations || []).map((text) => `<p>${escapeHtml(text)}</p>`).join('')}</details>
      ${link ? `<a href="${escapeHtml(link)}">Открыть навык в отчёте</a>` : ''}</section>`;
  };
  const render = (focus = false) => {
    if (!isCurrent() || lifetime.signal.aborted) return;
    const active = document.activeElement;
    const restoreFocus = node.contains(active) ? ['data-comparison-mode', 'data-comparison-direction'].find((name) => active.hasAttribute(name)) : null;
    const restoreValue = restoreFocus ? active.getAttribute(restoreFocus) : null;
    const restoreSelect = node.contains(active) && active.matches('select');
    // A resize/mode change keeps the selected pair and its PDF error/retry state.
    const pdfAction = node.querySelector('.report-pdf-action');
    const filtered = rows.filter((row) => direction === 'all' || String(row.competency_id) === direction);
    if (!filtered.some((row) => String(row.skill_id) === String(selectedId))) selectedId = String(filtered[0]?.skill_id || '');
    const selected = filtered.find((row) => String(row.skill_id) === String(selectedId));
    const mobile = window.matchMedia('(max-width: 720px)').matches;
    const chartMode = mobile && direction === 'all' ? 'bars' : mode;
    const allowRadial = filtered.some((row) => row.comparability.status === 'allowed');
    const buttons = ['fill', 'outline', 'bars'].map((value, i) => `<button type="button" data-comparison-mode="${value}" aria-pressed="${value === chartMode}" ${mobile && direction === 'all' && value !== 'bars' ? 'disabled' : ''}>${['Заливка', 'Контур', 'Шкалы'][i]}</button>`).join('');
    const tableRows = filtered.map((row) => `<tr class="${String(row.skill_id) === selectedId ? 'is-selected' : ''}"><th scope="row"><button type="button" data-compare-skill="${escapeHtml(row.skill_id)}" id="cmp-skill-${escapeHtml(row.skill_id)}" aria-controls="m8-comparison-detail" aria-expanded="${String(row.skill_id) === selectedId}">${escapeHtml(row.skill_name)}</button></th><td>${status(row, 'previous')}${limitations(row, 'previous').slice(0, 1).map((text) => `<small>${escapeHtml(text)}</small>`).join('')}</td><td>${status(row, 'current')}${limitations(row, 'current').slice(0, 1).map((text) => `<small>${escapeHtml(text)}</small>`).join('')}</td><td>${row.comparability.status === 'allowed' ? number(row.difference, true) : `<small>Разность не выводится: ${escapeHtml(reason(row))}</small>`}</td></tr>`).join('');
    const scales = filtered.map((row) => `<article class="m8-comparison-scale"><button type="button" data-compare-skill="${escapeHtml(row.skill_id)}">${escapeHtml(row.skill_name)}</button>${['previous', 'current'].map((key) => `<div class="m8-comparison-scale-line"><span>${key === 'previous' ? 'Ранее' : 'Сейчас'}</span>${row[key] == null ? '<span>Без числа</span>' : `<span class="m8-comparison-track" role="img" aria-label="${escapeHtml(`${dates[key]}: ${number(row[key])} из 3. ${label(row, key)}`)}"><span class="m8-comparison-${key === 'previous' ? 'past' : 'now'}${side(row, key)?.outcome === 'partial_score' ? ' is-partial' : ''}" style="width:${Number(row[key]) / 3 * 100}%"></span></span>`}<strong>${number(row[key])}</strong></div><small>${escapeHtml(label(row, key))}</small>`).join('')}</article>`).join('');
    node.innerHTML = `<nav class="m8-comparison-links" aria-label="Возврат из сравнения"><button type="button" class="ghost-button compact-ghost" data-compare-back>← К отчёту</button><button type="button" class="ghost-button compact-ghost" data-compare-history>История оценок</button></nav>
      <dl class="m8-comparison-periods">${period('previous', 'Предыдущая оценка')}${period('current', 'Текущая оценка')}</dl>
      <p class="m8-comparison-note">Разность расчётных показателей не доказывает развитие навыка и не означает процент роста.</p>
      <div class="m8-chart-head"><p>Показатели навыков · шкала 0–3</p><div class="m8-chart-modes" role="group" aria-label="Вид сравнения">${buttons}</div></div>
      <div class="report-tabs" role="group" aria-label="Направление сравнения">${[{ id: 'all', name: 'Общий обзор' }, ...groups].map((group) => `<button type="button" class="report-tab-button${direction === group.id ? ' active' : ''}" data-comparison-direction="${escapeHtml(group.id)}" aria-pressed="${direction === group.id}">${escapeHtml(group.name)}</button>`).join('')}</div>
      <select class="report-tab-select" aria-label="Направление сравнения">${[{ id: 'all', name: 'Общий обзор' }, ...groups].map((group) => `<option value="${escapeHtml(group.id)}" ${direction === group.id ? 'selected' : ''}>${escapeHtml(group.name)}</option>`).join('')}</select>
      <div class="m8-comparison-legend"><span class="m8-legend-previous">□ Предыдущая · ${escapeHtml(dates.previous)}</span><span class="m8-legend-current">● Текущая · ${escapeHtml(dates.current)}</span><span>Полый маркер · частичный показатель</span></div>
      <div class="m8-chart-layout"><div class="m8-chart-column"><div class="m8-report-chart m8-comparison-chart"></div><p class="m8-chart-note">Несопоставимые оси и пропуски оставлены открытыми. Площадь фигуры не является общим баллом 4К.</p>
      <div class="m8-comparison-table-wrap"><table class="m8-comparison-table"><thead><tr><th>Навык</th><th>Предыдущая</th><th>Текущая</th><th>Разность</th></tr></thead><tbody>${tableRows}</tbody></table></div></div>
      <aside class="m8-skill-detail" id="m8-comparison-detail" tabindex="-1" aria-label="Разбор навыка в двух оценках">${selected ? `<button type="button" class="m8-skill-back">← К списку навыков</button><p class="section-label">${escapeHtml(selected.competency_name || 'Навык')}</p><h4>${escapeHtml(selected.skill_name)}</h4>${selected.comparability.status === 'allowed' ? `<p>Разность: <strong>${number(selected.difference, true)}</strong></p>` : `<p class="m8-local-limitation">Разность не выводится: ${escapeHtml(reason(selected))}</p>`}${evidence(selected, 'previous')}${evidence(selected, 'current')}` : '<p>В направлении нет сохранённых навыков.</p>'}</aside></div>
      <div class="report-pdf-action"><button type="button" class="primary-button compact-primary">Скачать сравнение PDF</button><span class="report-pdf-status" role="status"></span></div>`;
    const chart = node.querySelector('.m8-comparison-chart');
    if (chartMode === 'bars' || !allowRadial) {
      chart.innerHTML = `${!allowRadial ? '<p><strong>Числовое сравнение недоступно.</strong> Результаты показаны раздельно.</p>' : ''}<div class="m8-comparison-scales">${scales}</div>`;
    } else {
      const skillsFor = (key) => filtered.map((row) => ({ skill_id: row.skill_id, skill_name: row.skill_name,
        outcome: side(row, key)?.outcome, score: row.comparability.status === 'allowed' && row[key] != null ? { value: row[key] } : null }));
      chart.innerHTML = buildRadar(skillsFor('current'), chartMode, {
        compact: mobile || chart.clientWidth < 720, chartWidth: Math.max(200, chart.clientWidth - 32),
        selectedSkillId: selectedId,
        series: [{ skills: skillsFor('previous'), previous: true, label: `Предыдущая ${dates.previous}` },
          { skills: skillsFor('current'), label: `Текущая ${dates.current}` }],
      });
      chart.querySelectorAll('a').forEach((link) => link.setAttribute('href', '#m8-comparison-detail'));
      fitLabels(chart);
    }
    const choose = (id) => { selectedId = id; expanded.clear(); render(true); };
    node.querySelectorAll('[data-compare-skill], [data-m8-skill-id]').forEach((button) => button.onclick = (event) => {
      event.preventDefault(); choose(button.dataset.compareSkill || button.dataset.m8SkillId);
    });
    node.querySelector('[data-compare-back]').onclick = onBack;
    node.querySelector('[data-compare-history]').onclick = onHistory;
    node.querySelector('.m8-skill-back')?.addEventListener('click', () => node.querySelector(`#cmp-skill-${CSS.escape(selectedId)}`)?.focus());
    node.querySelectorAll('[data-comparison-mode]').forEach((button) => button.onclick = () => { mode = button.dataset.comparisonMode; render(); });
    node.querySelectorAll('[data-comparison-direction]').forEach((button) => button.onclick = () => { direction = button.dataset.comparisonDirection; render(); });
    node.querySelector('select').onchange = (event) => { direction = event.target.value; render(); };
    node.querySelectorAll('[data-comparison-evidence]').forEach((details) => details.addEventListener('toggle', () => {
      if (!details.isConnected) return;
      if (details.open) expanded.add(details.dataset.comparisonEvidence);
      else expanded.delete(details.dataset.comparisonEvidence);
      save();
    }));
    if (pdfAction) node.querySelector('.report-pdf-action').replaceWith(pdfAction);
    else bindReportPdf(node.querySelector('.report-pdf-action button'), {
        status: node.querySelector('.report-pdf-status'), isCurrent: () => isCurrent() && !lifetime.signal.aborted,
        url: `/users/assessment/m8/reports/${encodeURIComponent(comparison.current.report_id)}/comparison.pdf?previous_report_id=${encodeURIComponent(comparison.previous.report_id)}`,
        filename: `4k-report-comparison-${comparison.current.report_id}.pdf`,
      });
    save();
    if (focus) node.querySelector('#m8-comparison-detail')?.focus({ preventScroll: true });
    else if (restoreFocus) node.querySelector(`[${restoreFocus}="${CSS.escape(restoreValue)}"]`)?.focus({ preventScroll: true });
    else if (restoreSelect) node.querySelector('select')?.focus({ preventScroll: true });
  };
  window.addEventListener('resize', () => render(), { signal: lifetime.signal });
  render();
  return () => lifetime.abort();
};

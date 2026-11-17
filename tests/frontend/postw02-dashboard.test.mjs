import test from 'node:test';
import assert from 'node:assert/strict';
import { assessmentPositionText, assessmentMetadata, formatAssessmentDate } from '../../web/js/dashboard-presentation.js';
import { dashboardHarness } from './helpers/dashboard-harness.mjs';
const active = { status: 'active', journey_state: 'active', planned_total: 8, current_position_no: 3 };
test('POSTW02 shows saved current position even when completed is unknown', () => {
  for (const completed_cases of [undefined, null, 0, 2, '0']) {
    assert.equal(assessmentPositionText({ ...active, completed_cases, total_cases: 3 }), '3 ситуация из 8');
  }
});
test('POSTW02 never infers a current position or total from materialized/completed counts', () => {
  for (const current_position_no of [undefined, null, '3', 0, 9]) {
    assert.equal(assessmentPositionText({ ...active, current_position_no, completed_cases: 2 }), '8 ситуаций в плане');
  }
  assert.equal(assessmentPositionText({ ...active, planned_total: null, total_cases: 9 }), '');
  assert.equal(assessmentPositionText({ ...active, status: 'prepared' }), '8 ситуаций в плане');
});
test('POSTW02 between screen stays on last presented closed position', () => {
  assert.equal(assessmentPositionText({ ...active, journey_state: 'between_situations', last_completed_position_no: 3 }), 'Ситуация 3 завершена');
  assert.equal(assessmentPositionText({ ...active, journey_state: 'between_situations', last_completed_position_no: null }), '');
});
test('POSTW02 metadata retains organization and not-started state before a saved plan exists', () => {
  assert.deepEqual(assessmentMetadata({ journey_state: 'preparing', organization_name: 'Synthetic', planned_total: null }), [
    { label: 'Организация', value: 'Synthetic' }, { label: 'Начало оценки', value: 'Оценка ещё не начата' },
  ]);
});
test('POSTW02 metadata follows ready, presented, return, between and result states', () => {
  const card = { ...active, organization_name: 'Synthetic', calendar_deadline: '2026-11-19T12:00:00Z' };
  const org = { label: 'Организация', value: 'Synthetic' };
  assert.deepEqual(assessmentMetadata({ ...card, status: 'prepared', journey_state: 'ready' }), [org, { label: 'План оценки', value: '8 ситуаций' }]);
  for (const journey_state of ['active', 'return_required']) {
    assert.deepEqual(assessmentMetadata({ ...card, journey_state }), [org, { label: 'Текущая ситуация', value: '3 ситуация из 8' }]);
  }
  assert.deepEqual(assessmentMetadata({ ...card, journey_state: 'between_situations', last_completed_position_no: 3 }), [org, { label: 'Текущая ситуация', value: 'Ситуация 3 завершена' }]);
  assert.deepEqual(assessmentMetadata({ ...card, status: 'report_ready', journey_state: 'report_ready', closed_at: '2026-10-17T12:00:00Z' }), [org, { label: 'Дата завершения', value: '17 октября 2026' }]);
});
test('POSTW02 missing position and completion date never invent metadata', () => {
  const org = { label: 'Организация', value: 'Synthetic' };
  assert.deepEqual(assessmentMetadata({ ...active, organization_name: 'Synthetic', current_position_no: null }), [org, { label: 'План оценки', value: '8 ситуаций в плане' }]);
  assert.deepEqual(assessmentMetadata({ status: 'report_ready', planned_total: 8, organization_name: 'Synthetic' }), [org]);
  assert.equal(formatAssessmentDate('invalid'), '');
  assert.equal(formatAssessmentDate(null), '');
  assert.equal(formatAssessmentDate('2026-10-17T22:00:00Z'), '18 октября 2026');
});

const preparation = { reference: 'P4K-SYNTHETIC-OPERATION', operation_id: 'op-1', kind: 'assessment', status: 'completed',
  stage_label: 'Подготовка завершена', read_at: '2026-11-17T12:00:00Z' };
const card = (id, prep = preparation) => ({ cycle_id: id, title: id, status: 'prepared', preparation: prep,
  action: 'open_readiness', button_label: 'Посмотреть состояние' });
const setup = () => {
  const h = dashboardHarness(); h.state.dashboard = { current_assessments: [card('one'), card('two')] }; h.render(); return h;
};
const details = (h, id = 'one') => h.card(id).querySelector('details');

test('QA B1 real refreshDashboard keeps disclosure and updates the same operation', async () => {
  const h = setup(); const original = details(h); original.open = true;
  h.context.response = { dashboard: { current_assessments: [card('one', { ...preparation, stage_label: 'Новый этап', read_at: '2026-11-17T12:01:00Z' })] } };
  await h.refresh(); assert.equal(details(h), original); assert.equal(original.open, true);
  assert.match(h.card('one').textContent, /Новый этап/);
});

for (const open of [false, true]) test(`QA B2 latest disclosure action during pending refresh: ${open}`, async () => {
  const h = setup(); details(h).open = !open;
  let resolve; h.context.fetch = () => new Promise(r => { resolve = r; });
  const pending = h.refresh(); details(h).open = open;
  resolve({ dashboard: h.state.dashboard }); await pending;
  assert.equal(details(h).open, open);
});

test('QA B3 reorder, stage, operation, removal, owner and identity isolate disclosure', async () => {
  const h = setup(); const original = details(h); original.open = true;
  h.state.dashboard.current_assessments = [card('two'), card('one')]; h.render();
  assert.equal(details(h), original); assert.equal(details(h, 'two').open, false);
  h.state.dashboard.current_assessments = [card('one', { ...preparation, reference: 'P4K-NEW', operation_id: 'new' })]; h.render();
  assert.equal(details(h).open, false); details(h).open = true;
  h.state.dashboard.current_assessments = [card('one', null)]; h.render(); assert.equal(details(h), null);
  h.state.dashboard.current_assessments = [card('one')]; h.render(); assert.equal(details(h).open, false);
  details(h).open = true; h.state.pendingUser = { id: '9' }; h.render(); assert.equal(details(h).open, false);
  details(h).open = true; h.state.identityEpoch++; h.render(); assert.equal(details(h).open, false);
});

test('QA B4 focus stays on copy; removed control falls back within its card; external focus wins', async () => {
  const h = setup(); details(h).open = true;
  const copy = h.card('one').querySelector('[data-preparation-copy]'); copy.focus(); h.render();
  assert.equal(h.document.activeElement, copy); assert.equal(copy.isConnected, true);
  h.state.dashboard.current_assessments[0] = card('one', null); h.render();
  assert.equal(h.document.activeElement, h.card('one').querySelector('[data-dashboard-action]'));
  const external = h.context.dashboardRefreshButton; external.focus(); h.render(); assert.equal(h.document.activeElement, external);
  let resolve; h.context.fetch = () => new Promise(r => { resolve = r; });
  h.card('one').querySelector('[data-dashboard-action]').focus(); const pending = h.refresh(); external.focus();
  resolve({ dashboard: h.state.dashboard }); await pending; assert.equal(h.document.activeElement, external);
});

test('QA B3 same Cycle crosses current/history with fresh composition and retains its operation', () => {
  const h = setup(); const original = details(h); original.open = true;
  h.state.dashboard = { current_assessments: [card('two')], completed_assessments: [card('one')] }; h.render();
  assert.equal(details(h), original); assert.equal(original.open, true);
  assert.equal(h.card('one').querySelector('.participant-assessment-title').tagName, 'H3');
  h.state.dashboard = { current_assessments: [card('one')], completed_assessments: [] }; h.render();
  assert.equal(details(h), original); assert.equal(original.open, true);
  assert.equal(h.card('one').querySelector('.participant-assessment-title').tagName, 'H2');
});

test('QA B3 late response after identity/screen change never changes dashboard', async () => {
  for (const change of ['identityEpoch', 'pendingUser', 'currentScreen']) {
    const h = setup(); let resolve; h.context.fetch = () => new Promise(r => { resolve = r; });
    const pending = h.refresh(); const before = h.state.dashboard;
    if (change === 'identityEpoch') h.state.identityEpoch++; else h.state[change] = change === 'pendingUser' ? { id: '9' } : 'interview';
    resolve({ dashboard: { current_assessments: [] } }); await pending;
    assert.equal(h.state.dashboard, before);
  }
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const dashboard = await readFile(new URL('../../web/js/screens/dashboard.js', import.meta.url), 'utf8');
const markup = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web/styles/screens/dashboard.css', import.meta.url), 'utf8');

test('LK01 renders server-owned current and completed Cycle cards', () => {
  assert.match(markup, /Мои оценки/);
  assert.match(markup, /id="current-assessments"/);
  assert.match(markup, /id="completed-assessments"/);
  assert.match(dashboard, /dashboard\.current_assessments/);
  assert.match(dashboard, /dashboard\.completed_assessments/);
  assert.match(dashboard, /Завершено ситуаций:.*из/);
  assert.match(dashboard, /Europe\/Moscow/);
});

test('LK01 has explicit Cycle actions and no catalogue or repeat action', () => {
  assert.match(dashboard, /card\.action === 'open_processing'/);
  assert.match(dashboard, /card\.action === 'open_report'/);
  assert.match(dashboard, /card\.action === 'acquaintance'/);
  assert.match(dashboard, /if \(primaryEntry\) button\.id = 'assessment-action-button'/);
  assert.doesNotMatch(dashboard, /staticAssessments|Скоро|Пройти ассессмент снова|Перейти к кейсам|К кейсам/);
  assert.match(dashboard, /DASHBOARD_REFRESH_INTERVAL_MS/);
  assert.match(dashboard, /focus\(\{ preventScroll: true \}\)/);
  assert.match(markup, /Не удалось обновить сведения/);
});

test('LK01 keeps accessible mobile actions and accepted visual tokens', () => {
  assert.match(styles, /min-height:\s*48px/);
  assert.match(styles, /background:\s*#18b8c6/);
  assert.match(styles, /outline:\s*3px solid #007d89/);
  assert.match(styles, /@media \(max-width: 640px\)/);
  assert.match(styles, /width:\s*100%/);
});

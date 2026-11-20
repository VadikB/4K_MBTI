import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync('web/index.html', 'utf8');
const processing = fs.readFileSync('web/js/screens/processing.js', 'utf8');
const main = fs.readFileSync('web/js/main.js', 'utf8');
const report = fs.readFileSync('web/js/screens/report.js', 'utf8');
const styles = fs.readFileSync('web/styles/screens/processing.css', 'utf8');
const routes = fs.readFileSync('Api/routes.py', 'utf8');

test('E02 exposes the accepted completion, waiting, ready and failure copy', () => {
  assert.match(html, /Проверяем завершение оценки/);
  assert.match(processing, /Спасибо за ваши ответы/);
  assert.match(processing, /Время оценки закончилось/);
  assert.match(processing, /Ваш результат готов/);
  assert.match(processing, /Не удалось подготовить результат/);
  assert.match(processing, /Не удалось проверить готовность/);
});

test('E02 does not expose pipeline stages, invented percentages or participant recovery', () => {
  const cycleBranch = processing.slice(processing.indexOf('const pollCycleStatus'), processing.indexOf('const applyServerAnalysisProgress'));
  assert.doesNotMatch(cycleBranch, /stageProgress|pipeline_stage|analysis-retry/);
  assert.match(processing, /openReport\(\{ m8CycleId: view\.cycleId, m8ReportId: reportId \}\)/);
  assert.match(processing, /Посмотреть результат/);
});

test('E02 keeps calculated results waiting until an owned assessee report is ready', () => {
  assert.match(routes, /'calculated':'results_ready'/);
  assert.match(routes, /r\.audience='assessee'/);
  assert.match(routes, /pipeline\['status'\] == 'failed'/);
  assert.match(routes, /report_status = 'ready'/);
});

test('E02 restores an explicit M8 report after URL identifiers become strings', () => {
  assert.match(report, /Number\(report\.owner_user_id\) !== Number\(ownerId\)/);
  assert.match(report, /String\(report\.cycle_id\) !== String\(cycleId\)/);
  assert.match(report, /String\(report\.id\) !== String\(reportId\)/);
});

test('E02 addresses the selected Cycle and never reads journey readiness while polling', () => {
  assert.match(main, /openProcessingScreen\(\{ cycleId: outcomeCycleId \}\)/);
  assert.match(processing, /visibilitychange/);
  assert.match(processing, /view\.request === request/);
  assert.match(processing, /state\.currentScreen === 'processing'/);
  assert.match(processing, /CYCLE_POLL_INTERVAL_MS = 5000/);
  assert.match(processing, /encodeURIComponent\(view\.cycleId\) \+ '\/status'/);
  assert.doesNotMatch(processing, /journey-state|initialCycleSnapshot/);
});

test('E02 uses accepted visual tokens and mobile actions', () => {
  assert.match(styles, /background: var\(--palette-outcome-canvas\)/);
  assert.match(styles, /width: min\(100%, 640px\)/);
  assert.match(styles, /color: var\(--palette-outcome-link\)/);
  assert.match(styles, /outline: 3px solid var\(--accent\)/);
  assert.match(styles, /@media \(max-width: 650px\)[\s\S]*padding: 16px 16px 4px/);
});

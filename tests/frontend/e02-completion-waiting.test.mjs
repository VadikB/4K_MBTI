import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync('web/index.html', 'utf8');
const processing = fs.readFileSync('web/js/screens/processing.js', 'utf8');
const styles = fs.readFileSync('web/styles/screens/processing.css', 'utf8');
const routes = fs.readFileSync('Api/routes.py', 'utf8');

test('E02 exposes the accepted completion, waiting, ready and failure copy', () => {
  assert.match(html, /Проверяем завершение оценки…/);
  assert.match(processing, /Спасибо за ваши ответы/);
  assert.match(processing, /Время оценки закончилось/);
  assert.match(processing, /Ваш результат готов/);
  assert.match(processing, /Не удалось подготовить результат/);
  assert.match(processing, /Не удалось проверить готовность/);
});

test('E02 does not expose pipeline stages, invented percentages or participant recovery', () => {
  const pollStart = processing.indexOf('export const pollAnalysisStatus');
  const cycleBranch = processing.slice(pollStart, processing.indexOf("if (!state.pendingUser?.id", pollStart));
  assert.doesNotMatch(cycleBranch, /stageProgress/);
  assert.doesNotMatch(cycleBranch, /pipeline_stage \|\|/);
  assert.doesNotMatch(cycleBranch, /analysis-retry/);
  assert.doesNotMatch(cycleBranch, /openReport\(\{ m8CycleId: state\.productCycleId \}\)/);
  assert.match(processing, /Посмотреть результат/);
});

test('E02 keeps calculated results waiting until an owned assessee report is ready', () => {
  assert.match(routes, /'calculated':'results_ready'/);
  assert.match(routes, /r\.audience='assessee'/);
  assert.match(routes, /pipeline\['status'\] == 'failed'/);
  assert.match(routes, /report_status = 'ready'/);
});

test('E02 polling is cancellable, visibility-aware and ignores stale responses', () => {
  assert.match(processing, /visibilitychange/);
  assert.match(processing, /requestEpoch !== cycleRequestEpoch/);
  assert.match(processing, /state\.currentScreen !== 'processing'/);
  assert.match(processing, /CYCLE_POLL_INTERVAL_MS = 5000/);
});

test('E02 uses accepted visual tokens and mobile actions', () => {
  assert.match(styles, /background: #eef2f3/);
  assert.match(styles, /width: min\(100%, 680px\)/);
  assert.match(styles, /background: #18b8c6/);
  assert.match(styles, /outline: 3px solid #007d89/);
  assert.match(styles, /@media \(max-width: 600px\)[\s\S]*width: 100%/);
});

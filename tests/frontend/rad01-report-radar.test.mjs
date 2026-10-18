import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { getReportScoreValue, splitRadarRuns, summarizeReportScores } from '../../web/js/utils/report-radar.js';

const report = await readFile(new URL('../../web/js/screens/report.js', import.meta.url), 'utf8');
const markup = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web/styles/screens/report.css', import.meta.url), 'utf8');

test('RAD01 preserves real zero and keeps null out of the chart', () => {
  assert.equal(getReportScoreValue({ score: { value: 0 } }), 0);
  assert.equal(getReportScoreValue({ score: { value: null } }), null);
  assert.deepEqual(summarizeReportScores([{ score: { value: 0 } }, { outcome: 'no_result' }]), {
    values: [0, null], hasScores: true, allZero: false, missingCount: 1,
  });
  assert.equal(summarizeReportScores([{ score: { value: 0 } }, { score: { value: 0 } }]).allZero, true);
});

test('RAD01 never joins a radar line across missing values', () => {
  assert.deepEqual(splitRadarRuns([2.25, null, 1, 0]), [
    { indexes: [2, 3, 0], closed: false },
  ]);
  assert.deepEqual(splitRadarRuns([2.25, null, 1, null]), [
    { indexes: [2], closed: false },
    { indexes: [0], closed: false },
  ]);
  assert.deepEqual(splitRadarRuns([0, 0, 0]), [{ indexes: [0, 1, 2], closed: true }]);
  assert.deepEqual(splitRadarRuns([null, null]), []);
});

test('RAD01 exposes fill, outline and bars with a permanent text list', () => {
  assert.match(markup, /data-chart-mode="fill"/);
  assert.match(markup, /data-chart-mode="outline"/);
  assert.match(markup, /data-chart-mode="bars"/);
  assert.match(markup, /id="m8-report-skills"/);
  assert.match(report, /competency_id: 'all', competency_name: 'Общий обзор'/);
  assert.match(styles, /m8-report-chart\.is-overview/);
  assert.match(report, /Площадь фигуры не является общим баллом/);
  assert.match(report, /Пропуски оставлены открытыми/);
  assert.match(styles, /fill-opacity:\s*0\.18/);
  assert.match(styles, /m8-radar-fill[\s\S]*fill:\s*var\(--accent\)/);
});

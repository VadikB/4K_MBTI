import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { getReportScoreValue, projectReportRadar, radarPoint, splitRadarRuns, summarizeReportScores } from '../../web/js/utils/report-radar.js';

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
  assert.deepEqual(splitRadarRuns([null, 1, 2, null, 0]), [
    { indexes: [1, 2], closed: false }, { indexes: [4], closed: false },
  ]);
  assert.deepEqual(splitRadarRuns([2, null, null, 1]), [
    { indexes: [3, 0], closed: false },
  ]);
  assert.deepEqual(splitRadarRuns([null, 1, null]), [{ indexes: [1], closed: false }]);
});

test('REPORT-05 projection preserves saved identity, exact score and limitations', () => {
  const source = [
    { skill_id: 'K2-S9', skill_name: 'Длинное название', competency_id: 'K2', outcome: 'partial_score',
      score: { value: '1.7500' }, presentation: { label: 'Частичный показатель', reasons: [{ message: 'Часть состава' }] } },
    { skill_id: 'K2-S2', skill_name: 'Другой навык', competency_id: 'K2', score: null },
    { skill_id: 'K4-S8', skill_name: 'Третий навык', competency_id: 'K4', score: { value: 0 } },
  ];
  const projection = projectReportRadar(source);
  assert.deepEqual(projection.axes.map((axis) => axis.skillId), ['K2-S9', 'K2-S2', 'K4-S8']);
  assert.deepEqual(projection.axes.map((axis) => axis.value), [1.75, null, 0]);
  assert.equal(projection.axes[0].displayValue, '1.7500');
  assert.equal(projection.axes[0].partial, true);
  assert.deepEqual(projection.axes[0].limitations, ['Часть состава']);
  assert.deepEqual(projection.runs, [{ indexes: [2, 0], closed: false }]);
  assert.deepEqual(radarPoint(0, 3, 4, 100, 100, 60), { x: 100, y: 40 });
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

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const report = await readFile(new URL('../../web/js/screens/report.js', import.meta.url), 'utf8');
const markup = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const comparison = await readFile(new URL('../../web/js/utils/report-comparison.js', import.meta.url), 'utf8');

test('CMP01 has an explicit comparison entry and exact columns', () => {
  assert.match(markup, /id="m8-comparison-open"[^>]*>Сравнить оценки/);
  assert.match(markup, /id="m8-comparison-select"/);
  assert.match(comparison, /<th>Навык<\/th><th>Предыдущая<\/th><th>Текущая<\/th><th>Разность<\/th>/);
});

test('CMP01 renders non-comparable values as separate slices without delta', () => {
  assert.match(comparison, /row\.comparability\.status === 'allowed'/);
  assert.match(comparison, /Числовое сравнение недоступно/);
  assert.match(comparison, /Разность не выводится/);
  assert.match(report, /Предыдущей завершённой оценки пока нет/);
});

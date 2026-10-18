import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const report = await readFile(new URL('../../web/js/screens/report.js', import.meta.url), 'utf8');
const wiring = await readFile(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');
const markup = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web/styles/screens/report.css', import.meta.url), 'utf8');

test('REP01 presents the four M8 outcomes without derived levels or competency scores', () => {
  assert.match(report, /Результат по полному составу навыка/);
  assert.match(report, /Результат по части навыка/);
  assert.match(report, /Есть наблюдения без общего балла по навыку/);
  assert.match(report, /Недостаточно оснований для результата/);
  assert.match(report, /общий уровень навыка не присваивается/);
  assert.doesNotMatch(report, /Полный результат со Score|Частный результат со Score|Нет Skill Result/);
});

test('REP01 groups saved skills and hides technical trace identifiers from participant markup', () => {
  assert.match(markup, /id="m8-report-tabs"/);
  assert.match(markup, /id="m8-report-tab-select"/);
  assert.match(report, /skill\.competency_id/);
  assert.match(report, /Почему сделан такой вывод/);
  assert.doesNotMatch(report, /Indicator:|IA:|Turn:|Fragment:/);
  assert.match(report, /Неизвестный формат результата/);
});

test('REP02 presents saved descriptions and explicit non-blocking states without advice', () => {
  assert.match(markup, /Главное из вашей оценки/);
  assert.match(markup, /Ваши результаты по 4К/);
  assert.match(markup, /Что удалось оценить и где данных недостаточно/);
  assert.match(report, /Пояснение готовится/);
  assert.match(report, /Пояснение временно недоступно/);
  assert.match(report, /descriptive\.claims/);
  assert.doesNotMatch(markup, /Что можно развивать|Рекомендации по развитию/);
});

test('REP01 keeps exact report binding and handles PDF failure locally', () => {
  assert.match(report, /reportId \? `\/users\/assessment\/m8\/reports/);
  assert.match(report, /String\(report\.id\) !== String\(reportId\)/);
  assert.match(wiring, /fetch\('\/users\/assessment\/m8\/reports\/'/);
  assert.match(wiring, /Не удалось скачать PDF\. Попробуйте ещё раз\./);
  assert.match(styles, /@media \(max-width: 720px\)[\s\S]*report-tab-select/);
  assert.match(styles, /min-height:\s*48px/);
});

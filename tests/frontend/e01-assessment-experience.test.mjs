import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync('web/index.html', 'utf8');
const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const interviewEntry = fs.readFileSync('web/js/entries/interview.js', 'utf8');
const styles = fs.readFileSync('web/styles/screens/interview.css', 'utf8');

test('E01 names assessment positions as situations and separates sending from completion', () => {
  assert.match(html, /4К Ассистент/);
  assert.match(html, /Прогресс уточняется/);
  assert.match(html, /После отправки ответ нельзя изменить/);
  assert.match(html, />Завершить ситуацию</);
  assert.match(html, /id="interview-submit-label">Отправить</);
  assert.match(interview, /Уточнение к вашему ответу/);
  assert.match(interview, /Приступить к следующей ситуации/);
});

test('E01 keeps the absolute deadline outside assessment and marks only server-confirmed pauses', () => {
  assert.doesNotMatch(interview, /Календарный срок:/);
  // Pause behavior (including authorized_pause + false) is exercised by qa03-runtime.test.mjs.
  assert.match(interview, /Пауза · /);
});

test('E01 scopes editable drafts to cycle and assessment situation', () => {
  assert.match(interview, /agent4k\.assessmentDraft:\$\{scope\.cycleId\}:\$\{scope\.situationId\}/);
  assert.match(interview, /window\.sessionStorage\.setItem\(key, interviewTextarea\.value\)/);
  assert.match(wiring, /interviewModule\.clearInterviewDraft\(\)/);
  assert.match(interviewEntry, /clearInterviewDraft/);
});

test('E01 protects supplied materials and silently blocks transferred answers', () => {
  assert.match(wiring, /protectedSelection/);
  assert.match(wiring, /\.interview-message:not\(\.own\)/);
  assert.match(wiring, /interviewTextarea\.addEventListener\('paste'/);
  assert.match(wiring, /insertFromPaste/);
  assert.match(wiring, /event\.shiftKey && key === 'insert'/);
  assert.doesNotMatch(wiring, /Копирование условия, материалов и реплик собеседника ограничено/);
  assert.match(styles, /\.interview-message\.own[\s\S]*user-select: text/);
});

test('E01 applies accepted conversation tokens and mobile layout', () => {
  assert.match(styles, /background: var\(--palette-graphite-050\)/);
  assert.match(styles, /background: #b3ebef/);
  assert.match(styles, /background: #18b8c6/);
  assert.match(styles, /font-family: "Onest", sans-serif/);
  assert.match(styles, /min-height: 100dvh/);
  assert.match(styles, /@media \(max-width: 900px\)[\s\S]*grid-template-columns: 1fr/);
});

test('E01 ADD01 presents the admitted situation once inside the chat without raw JSON or a route column', () => {
  assert.doesNotMatch(html, /class="case-sidebar"/);
  assert.match(interview, /addProductSituationMessage\(current\.participant_payload, materialsOpen\)/);
  assert.match(interview, /bubble\.dataset\.speakerLabel = '4К Ассистент'/);
  assert.match(interview, /'assessee_position'[\s\S]*'introduction'[\s\S]*'initial_situation'[\s\S]*'trigger'[\s\S]*'Ваша задача'[\s\S]*'conditions_and_constraints'/);
  assert.match(interview, /\['initial_materials', 'available_materials', 'materials', 'attachments'\]/);
  assert.doesNotMatch(interview, /JSON\.stringify\(payload/);
  assert.match(interview, /previousCaseKey !== current\.assessment_situation_id \? 0 : previousScrollTop/);
  assert.match(styles, /\.interview-main[\s\S]*width: min\(960px, 100%\)/);
});

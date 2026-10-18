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
  assert.match(html, /Ситуация 1 из 5/);
  assert.match(html, /После отправки ответ нельзя изменить/);
  assert.match(html, />Завершить ситуацию</);
  assert.match(html, /id="interview-submit-label">Отправить</);
  assert.match(interview, /Уточнение к вашему ответу/);
  assert.match(interview, /Приступить к следующей ситуации/);
});

test('E01 keeps the absolute deadline outside assessment and marks only server-confirmed pauses', () => {
  assert.doesNotMatch(interview, /Календарный срок:/);
  assert.match(interview, /snapshot\.between_situations[\s\S]*classList\.add\('is-paused'\)/);
  assert.match(interview, /classList\.toggle\('is-paused', suspended\)/);
  assert.match(interview, /Пауза · /);
});

test('E01 scopes editable drafts to cycle and assessment situation', () => {
  assert.match(interview, /agent4k\.assessmentDraft:\$\{state\.productCycleId\}:\$\{state\.productAssessmentSituationId\}/);
  assert.match(interview, /window\.sessionStorage\.setItem\(key, interviewTextarea\.value\)/);
  assert.match(wiring, /interviewModule\.clearInterviewDraft\(\)/);
  assert.match(interviewEntry, /clearInterviewDraft/);
});

test('E01 protects supplied materials without blocking own text or pasted answers', () => {
  assert.match(wiring, /protectedSelection/);
  assert.match(wiring, /\.interview-message:not\(\.own\)/);
  assert.doesNotMatch(wiring, /interviewTextarea\.addEventListener\('paste'/);
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
  assert.match(interview, /addProductSituationMessage\(current\.participant_payload\)/);
  assert.match(interview, /bubble\.dataset\.speakerLabel = '4К Ассистент'/);
  assert.match(interview, /\['Ситуация',[\s\S]*\['Ваша роль',[\s\S]*\['Задача',[\s\S]*\['Условия'/);
  assert.doesNotMatch(interview, /JSON\.stringify\(payload/);
  assert.match(interview, /previousCaseKey !== current\.assessment_situation_id \? 0 : previousScrollTop/);
  assert.match(styles, /\.interview-main[\s\S]*width: min\(960px, 100%\)/);
});

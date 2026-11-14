import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { acquaintanceErrorMessage } from '../../web/js/acquaintance-errors.js';

const source = fs.readFileSync('web/js/screens/onboarding.js', 'utf8');
const advance = source.slice(source.indexOf('const advance = async () => {'), source.indexOf('\nexport const initOnboarding'));
for (const action of ['answer', 'consent', 'progress']) {
  for (const name of ['TypeError', 'AbortError', 'RequestDeadlineError', 'opaque409']) {
    test(`actual acquaintance handler retains answer/step after ${action} ${name}`, async () => {
      const error = Object.assign(new Error(name === 'opaque409' ? 'b3200c41-6000-4000-8000-bc2254ce62ab' : 'Failed to fetch'),
        name === 'opaque409' ? { status: 409, requestId: 'reference-only' } : { name });
      const context = vm.createContext({
        loading: false, busy: false, reviewMode: false, loadFailed: false, generation: 1,
        answers: { answer_1: 'Unsaved synthetic answer' }, savedAnswers: {},
        errorMessage: '', notice: '', model: { mandatory_complete: false, readiness: { briefing: { consent_version: 1 } } },
        state: { identityEpoch: 1, onboardingIndex: 2, currentScreen: 'onboarding' },
        steps: () => Array(3).fill(action === 'answer' ? { answerKey: 'answer_1' } : { action }),
        identity: () => '99', isCurrent: () => true, captureInput: () => {}, renderOnboarding: () => {},
        api: async () => { throw error; }, saveProgress: async () => { throw error; },
        persistAssessmentContext: () => {}, acquaintanceErrorMessage,
      });
      vm.runInContext(`${advance}\nglobalThis.run = advance;`, context);
      await context.run();
      assert.equal(context.answers.answer_1, 'Unsaved synthetic answer');
      assert.equal(context.state.onboardingIndex, 2);
      assert.equal(context.busy, false);
      assert.doesNotMatch(context.errorMessage, /Failed to fetch|b3200c41/);
      assert.match(context.errorMessage, /Проверьте|Обновите/);
    });
  }
}

test('safe renderer preserves known cancellation/admission reasons and separates reference', () => {
  for (const [code, expected] of [['ASSIGNMENT_CANCELLED', /отменено/], ['AS_NOT_ADMITTED', /обязательную проверку/]]) {
    const message = acquaintanceErrorMessage({ status: 409, code, requestId: 'synthetic-ref', message: 'opaque' });
    assert.match(message, expected);
    assert.match(message, /Код обращения: synthetic-ref/);
    assert.doesNotMatch(message, /opaque/);
  }
  assert.doesNotMatch(acquaintanceErrorMessage(new TypeError('Failed to fetch')), /всё сохранено|текст сохранён/i);
});

test('actual start refusal codes and opaque UUID keep safe reasons', () => {
  assert.match(acquaintanceErrorMessage({ status: 409, message: 'M7_START_NOT_ADMITTED:AS_NOT_ADMITTED' }), /не допущен/);
  assert.match(acquaintanceErrorMessage({ status: 409, message: 'W02_ANSWERS_FROZEN:internal detail' }), /уже подтверждены/);
  const opaque = acquaintanceErrorMessage({ status: 409, message: 'b3200c41-6000-4000-8000-bc2254ce62ab' });
  assert.match(opaque, /Состояние оценки изменилось/);
  assert.match(opaque, /Код обращения: b3200c41/);
  assert.match(acquaintanceErrorMessage({ name: 'AssessmentStartUnknown', message: 'Состояние не подтверждено.',
    operationId: 'same-key', cause: { status: 409, message: 'ASSIGNMENT_CANCELLED' } }), /отменено.*не подтверждено/);
});

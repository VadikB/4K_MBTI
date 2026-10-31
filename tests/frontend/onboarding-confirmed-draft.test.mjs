import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const onboarding = readFileSync('web/js/screens/onboarding.js', 'utf8');

test('confirmed server answers discard the scoped local draft', () => {
  assert.match(onboarding, /if \(next\.mandatory_complete\)[\s\S]*sessionStorage\.removeItem\(key\)[\s\S]*answers = \{ \.\.\.savedAnswers \}/);
  assert.match(onboarding, /else \{[\s\S]*answers = \{ \.\.\.savedAnswers, \.\.\.readDraft\(\), \.\.\.dirty \}/);
});

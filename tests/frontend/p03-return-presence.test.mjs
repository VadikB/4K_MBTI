import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const interview = fs.readFileSync('web/js/screens/interview.js', 'utf8');

test('P03 confirms server presence independently of typing and requires explicit continue', () => {
  assert.match(interview, /setInterval\(\(\) => \{ void heartbeatProductPresence\(\); \}, 10000\)/);
  assert.match(interview, /\/presence/);
  assert.match(interview, /return-state/);
  assert.match(interview, /return-continue/);
  assert.match(interview, /Продолжить/);
});

test('P03 blocks stopped AS input and uses admitted equivalent candidate for replacement', () => {
  assert.match(interview, /interviewTextarea\.disabled = true/);
  assert.match(interview, /equivalent-candidate/);
  assert.match(interview, /provider_config_ref/);
  assert.match(interview, /Частичный диалог не переносится/);
});

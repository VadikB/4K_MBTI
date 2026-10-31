import assert from 'node:assert/strict';
import test from 'node:test';

import { isReleaseVersion, resolveReleaseVersion, renderReleaseVersion } from '../../web/js/release-version.js';

test('release format accepts three numeric parts only', () => {
  assert.equal(isReleaseVersion('2.0.10'), true);
  for (const value of ['', '2.0', '2.0.1.0', '02.0.1', null, undefined]) {
    assert.equal(isReleaseVersion(value), false);
  }
});

test('backend outage or mismatch keeps frontend build version', () => {
  assert.equal(resolveReleaseVersion(null, '2.0.1'), '2.0.1');
  assert.equal(resolveReleaseVersion('invalid', '2.0.1'), '2.0.1');
  const oldError = console.error;
  const errors = [];
  console.error = (message) => errors.push(message);
  try {
    assert.equal(resolveReleaseVersion('2.0.2', '2.0.1'), '2.0.1');
  } finally {
    console.error = oldError;
  }
  assert.match(errors[0], /Release mismatch/);
});

test('all visible release targets update together as text', () => {
  const targets = [{ textContent: '' }, { textContent: '' }];
  const badges = [{ classList: { toggle: (_name, invalid) => { badges[0].invalid = invalid; } } }];
  const root = {
    querySelectorAll: (selector) => selector === '[data-app-release-badge]' ? badges : targets,
  };
  renderReleaseVersion(root, '2.0.1');
  assert.deepEqual(targets.map((target) => target.textContent), ['2.0.1', '2.0.1']);
  assert.equal(badges[0].invalid, false);
  renderReleaseVersion(root, 'invalid');
  assert.deepEqual(targets.map((target) => target.textContent), ['2.0.1', '2.0.1']);
  assert.equal(badges[0].invalid, true);
});

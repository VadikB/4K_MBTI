import test from 'node:test';
import assert from 'node:assert/strict';
// format.js reads the existing browser config; keep that dependency synthetic.
globalThis.window = {};
const { appHeaderIdentity } = await import('../../web/js/components/app-header.js');

test('shared header displays the available name without guessing its word order', () => {
  assert.deepEqual(appHeaderIdentity({ full_name: 'Марина Тестова', job_description: 'Аналитик' }), { name: 'Марина Тестова', initials: 'МТ', role: 'Аналитик' });
  assert.deepEqual(appHeaderIdentity({ full_name: 'Тестова Марина Викторовна' }), { name: 'Тестова Марина Викторовна', initials: 'ТМ', role: '' });
});
test('shared header normalizes name whitespace and supports a single name', () => {
  assert.deepEqual(appHeaderIdentity({ full_name: '  Марина \t Тестова  ' }), { name: 'Марина Тестова', initials: 'МТ', role: '' });
  assert.deepEqual(appHeaderIdentity({ full_name: 'Марина' }), { name: 'Марина', initials: 'М', role: '' });
});
test('shared header uses participant fallback only when user name is absent', () => {
  for (const user of [null, {}, { full_name: null }, { full_name: '' }, { full_name: '   ' }]) {
    assert.deepEqual(appHeaderIdentity(user), { name: 'Участник', initials: 'У', role: '' });
  }
});

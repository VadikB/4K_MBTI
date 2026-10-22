import assert from 'node:assert/strict';
import test from 'node:test';

const status = { textContent: '', classList: { toggle() {} }, dataset: {} };
globalThis.document = {
  activeElement: null,
  getElementById(id) { return id === 'admin-organizations-status' ? status : null; },
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
globalThis.window = {
  addEventListener() {},
  dispatchEvent() {},
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  location: { pathname: '/', search: '', hash: '' },
  history: { replaceState() {}, pushState() {} },
};
globalThis.CustomEvent = class CustomEvent { constructor(type) { this.type = type; } };

const { state } = await import('../../web/js/state.js');
const { importAdminOrganizationMembers } = await import('../../web/js/screens/admin/organizations.js');

test('F22-01 ignores a late members import after identity changes', async () => {
  let resolveFetch;
  globalThis.fetch = () => new Promise((resolve) => { resolveFetch = resolve; });
  state.identityEpoch = 10;
  state.pendingUser = { id: 18 };
  state.adminOrganizations = { items: [{ id: 3, name: 'A' }] };
  status.textContent = 'Статус B';

  const pending = importAdminOrganizationMembers(3, 'email\nprivate-a@example.test');
  state.identityEpoch = 11;
  state.pendingUser = { id: 19 };
  state.adminOrganizations = { items: [{ id: 4, name: 'B' }] };
  status.textContent = 'Статус B';
  resolveFetch(new Response(JSON.stringify({
    imported_count: 1, skipped_count: 0,
    organizations: { items: [{ id: 3, name: 'A', email: 'private-a@example.test' }] },
  }), { status: 200, headers: { 'content-type': 'application/json' } }));

  assert.equal(await pending, null);
  assert.deepEqual(state.adminOrganizations, { items: [{ id: 4, name: 'B' }] });
  assert.equal(status.textContent, 'Статус B');
});

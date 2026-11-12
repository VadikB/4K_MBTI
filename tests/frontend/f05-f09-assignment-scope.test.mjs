import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const start = source.indexOf('export const assignAdminOrganizationAssessment =');
const end = source.indexOf('\nexport const cancelAdminOrganizationAssessment =', start);
const handler = source.slice(start, end).replace('export const ', 'const ');

const deferred = () => {
  let resolve;
  const promise = new Promise((yes) => { resolve = yes; });
  return { promise, resolve };
};

const harness = () => {
  const response = deferred();
  const messages = [];
  const state = { pendingUser: { id: 11 }, identityEpoch: 1, currentScreen: 'admin',
    adminOrganizations: { items: [{ id: 3, assessment_program: { program_definition_id: 7 } }] } };
  let loads = 0;
  const context = vm.createContext({
    state, assignmentOperationIds: new Map(), assignmentSourceRequests: new Map(),
    selectedOrganizationId: 3, assignmentViewGeneration: 0,
    currentIdentityKey: () => String(state.pendingUser?.id || ''),
    organizationById: (id) => state.adminOrganizations.items.find((item) => item.id === id),
    getSelectedAdminOrganizationAssessment: () => 'assessment-a',
    assessmentKey: (id, ref) => `${state.pendingUser.id}:${id}:${ref}`,
    requireOrganizationProgramScope: () => true,
    createOperationId: () => 'synthetic-operation',
    participantLabel: (_id, item) => `Участник ${item.user_id}`,
    exactBatch: () => true,
    offerAssessmentDataNavigation: () => messages.push('navigation'),
    setStatus: (message) => messages.push(message),
    fetch: () => response.promise,
    readApiResponse: async (value) => {
      if (value.error) throw value.error;
      return value;
    },
    loadAdminOrganizations: async ({ isCurrent } = {}) => { if (isCurrent?.()) loads += 1; },
  });
  vm.runInContext(`${handler}\nglobalThis.assign = assignAdminOrganizationAssessment;`, context);
  return { state, context, messages, response, assign: context.assign, loads: () => loads };
};

const success = { items: [{ user_id: 21, status: 'assigned' }] };

test('F06 old success cannot redraw another login or navigate it', async () => {
  const h = harness();
  const pending = h.assign(3, [21], 'assessment-a');
  h.state.pendingUser = { id: 12 };
  h.state.identityEpoch += 1;
  h.messages.length = 0;
  h.response.resolve(success);
  assert.equal(await pending, false);
  assert.deepEqual(h.messages, []);
  assert.equal(h.loads(), 0);
});

test('F06 A→B→A rejects late success and 409 from the previous screen generation', async () => {
  for (const reply of [success, { error: Object.assign(new Error('stale'), { status: 409 }) }]) {
    const h = harness();
    const pending = h.assign(3, [21], 'assessment-a');
    h.context.selectedOrganizationId = 4;
    h.context.assignmentViewGeneration += 1;
    h.context.selectedOrganizationId = 3;
    h.context.assignmentViewGeneration += 1;
    h.messages.length = 0;
    h.response.resolve(reply);
    assert.equal(await pending, false);
    assert.deepEqual(h.messages, []);
    assert.equal(h.loads(), 0);
  }
});

test('F06 current success and known error preserve feedback', async () => {
  const accepted = harness();
  const successPending = accepted.assign(3, [21], 'assessment-a');
  accepted.response.resolve(success);
  assert.equal(await successPending, true);
  assert.equal(accepted.loads(), 1);
  assert.match(accepted.messages.at(-1), /оценка назначена/);

  const refused = harness();
  const errorPending = refused.assign(3, [21], 'assessment-a');
  refused.response.resolve({ error: Object.assign(new Error('PROGRAM_ROLE_NOT_AVAILABLE'), { status: 409 }) });
  assert.equal(await errorPending, false);
  assert.match(refused.messages.at(-2), /Выберите доступную роль/);
  assert.equal(refused.messages.at(-1), 'navigation');
});

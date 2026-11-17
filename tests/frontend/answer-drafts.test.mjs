import assert from 'node:assert/strict';
import test from 'node:test';
import { createAnswerDrafts, draftSlot, clearOwnerDrafts, hasUnconfirmedDrafts } from '../../web/js/answer-drafts.js';
const tick = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const scope = { ownerId: '8', cycleId: 'cycle', situationId: 'as', slotId: 'dialogue:q1', identityEpoch: 1,
  expiresAt: new Date(Date.now() + 3600000).toISOString() };
const makeStorage = () => {
  const s = {}; Object.defineProperties(s, {
    getItem: { value: (k) => s[k] ?? null }, setItem: { value: (k, v) => { s[k] = v; } }, removeItem: { value: (k) => { delete s[k]; } },
  }); return s;
};
const element = () => ({ value: '', dataset: {}, textContent: '', children: [],
  replaceChildren() { this.children = []; }, append(b) { this.children.push(b); }, addEventListener(_name, cb) { this.click = cb; } });
globalThis.document = { createElement: element };
const fixture = ({ storage = makeStorage(), remote = null, request = null, owner = '8' } = {}) => {
  let seq = 0; const timers = new Map(); let id = 0; const calls = [];
  const input = element(), status = element(), actions = element(); let allowed = true;
  const server = remote || { owner_id: owner, cycle_id: 'cycle', assessment_situation_id: 'as', slot_id: scope.slotId,
    version: 0, revision: '', text: '', expires_at: scope.expiresAt };
  const ask = async (_scope, data) => {
    calls.push(data);
    if (request) return request(data);
    if (data) {
      if (data.expected_version !== server.version) { const e = new Error('conflict'); e.status = 409; throw e; }
      Object.assign(server, { text: data.text, version: server.version + 1, revision: data.revision });
    }
    return { ...server };
  };
  const draft = createAnswerDrafts({ input, status, actions, storage, request: ask,
    current: () => allowed, newRevision: () => `edit-${++seq}`,
    timers: { setTimeout(cb, delay) { timers.set(++id, { cb, delay }); return id; }, clearTimeout(i) { timers.delete(i); } } });
  draft.bind({ ...scope, ownerId: owner });
  return { draft, input, status, actions, server, calls, storage, timers,
    edit(text) { input.value = text; draft.edit(); }, invalidate() { allowed = false; } };
};

test('05B immediate durable input survives a new tab before debounce and syncs exact raw text', async () => {
  const one = fixture(); await tick(); one.edit('  raw\nsecond line\n  ');
  assert.equal(one.calls.filter(Boolean).length, 0);
  assert.equal(hasUnconfirmedDrafts('8', one.storage), true);
  const two = fixture({ storage: one.storage, remote: one.server }); await tick();
  assert.equal(two.input.value, '  raw\nsecond line\n  ');
  assert.equal(two.server.text, two.input.value);
  assert.equal(two.status.textContent, 'Черновик сохранён');
});

test('05A server restoration in a separate browser storage after login', async () => {
  const one = fixture(); await tick(); one.edit('server\nexact'); await one.draft.flush();
  const two = fixture({ remote: one.server }); await tick();
  assert.equal(two.input.value, 'server\nexact');
  assert.match(two.status.textContent, /восстановлен.*не отправлен/);
  assert.equal(two.calls.filter(Boolean).length, 0);
});

test('05B network and disabled storage show honest failure, preserving DOM', async () => {
  const broken = { getItem() { throw Error(); }, setItem() { throw Error(); } };
  const one = fixture({ storage: broken, request: async () => { throw Error('offline'); } }); await tick();
  one.edit('keep these characters'); await one.draft.flush();
  assert.equal(one.input.value, 'keep these characters'); assert.match(one.status.textContent, /Не удалось сохранить/);
  const two = fixture({ request: async () => { throw Error('offline'); } }); await tick(); two.edit('local');
  await two.draft.flush(); assert.match(two.status.textContent, /на этом устройстве/);
});

test('05B continuous typing keeps a fixed maxWait and one debounce, not requests per character', async () => {
  const one = fixture(); await tick();
  for (let i = 0; i < 100; i++) one.edit('text' + i);
  assert.equal(one.timers.size, 2); assert.equal(one.calls.filter(Boolean).length, 0);
  assert.deepEqual([...one.timers.values()].map(t => t.delay).sort((a, b) => a - b), [750, 3000]);
  const max = [...one.timers.values()].find(t => t.delay === 3000); max.cb(); await tick();
  assert.equal(one.calls.filter(Boolean).length, 1); assert.equal(one.server.text, 'text99');
});

test('05C divergent remote version conflicts without replacing local text; explicit choice uses CAS', async () => {
  const one = fixture(); await tick(); one.edit('my text');
  Object.assign(one.server, { text: 'other device', version: 1, revision: 'other' });
  await one.draft.flush(); assert.match(one.status.textContent, /другой вкладке/); assert.equal(one.input.value, 'my text');
  assert.equal(one.actions.children.length, 2);
  assert.equal(one.draft.conflicted(), true);
  assert.deepEqual(one.actions.children.map(b => b.textContent), ['Оставить текст из этой вкладки', 'Использовать другой сохранённый вариант']);
  await one.actions.children[0].click(); await tick(); assert.equal(one.server.text, 'my text');
  assert.equal(one.draft.conflicted(), false);
});

test('05C explicit empty text is versioned, never restores an older server edit', async () => {
  const one = fixture(); await tick(); one.edit('old'); await one.draft.flush();
  one.edit(''); await one.draft.flush();
  const two = fixture({ storage: one.storage, remote: one.server }); await tick(); assert.equal(two.input.value, '');
  assert.equal(two.server.version, 2);
});

test('05C slot and owner isolate drafts; heartbeat revisions do not rotate the question', async () => {
  const snapshot = { trace: { turns: [{ turn_id: 'q1', sequence_no: 1 }] } };
  assert.equal(draftSlot(snapshot), draftSlot({ ...snapshot, revision: 500, heartbeat: 99 }));
  assert.notEqual(draftSlot(snapshot), draftSlot({ clarification: { id: 'ask', status: 'ASK', question_turn_id: 'question' } }));
  const one = fixture(); await tick(); one.edit('owner8');
  const two = fixture({ storage: one.storage, owner: '9' }); await tick(); assert.equal(two.input.value, '');
  one.draft.bind({ ...scope, slotId: 'dialogue:q2' }); assert.equal(one.input.value, '');
});

test('05D late ACK and acceptance do not clear newer raw edit, even with the same text', async () => {
  let resolve; const one = fixture(); await tick(); one.edit('same');
  const revision = one.draft.revision();
  one.edit('same'); one.draft.clearAccepted({ ownerId: '8', cycleId: 'cycle', situationId: 'as', draftSlotId: scope.slotId,
    draftRevision: revision, accepted: false });
  assert.equal(one.input.value, 'same'); assert.equal(hasUnconfirmedDrafts('8', one.storage), true);
  const remote = { ...one.server }; let calls = 0;
  const delayed = fixture({ request: (data) => { if (!data) return { ...remote }; calls++; return new Promise(r => { resolve = () => r({ ...remote, ...data, version: 1 }); }); } });
  await tick(); delayed.edit('first'); const pending = delayed.draft.flush(); delayed.edit('second');
  resolve(); await pending; assert.equal(calls, 1); assert.equal(delayed.input.value, 'second');
  assert.notEqual(delayed.status.textContent, 'Черновик сохранён');
});

test('05E identity change ignores late GET and explicit logout removes only owner local copies', async () => {
  let resolve; const one = fixture({ request: () => new Promise(r => { resolve = r; }) });
  one.invalidate(); resolve({ ...one.server, text: 'late foreign input' }); await tick(); assert.equal(one.input.value, '');
  const two = fixture(); await tick(); two.edit('owner8');
  const other = fixture({ storage: two.storage, owner: '9' }); await tick(); other.edit('owner9');
  clearOwnerDrafts('8', two.storage); assert.equal(hasUnconfirmedDrafts('8', two.storage), false);
  assert.equal(hasUnconfirmedDrafts('9', two.storage), true);
});


test('05C divergent offline tabs retain both branches across closing and reopening', async () => {
  const one = fixture(); await tick();
  const two = fixture({ storage: one.storage, remote: one.server }); await tick();
  one.edit('unsynchronized first branch'); two.edit('unsynchronized second branch');
  const record = JSON.parse(two.storage[Object.keys(two.storage)[0]]);
  assert.equal(record.text, 'unsynchronized second branch');
  assert.ok(record.alternatives.some(a => a.text === 'unsynchronized first branch'));
  const restored = fixture({ storage: two.storage, remote: one.server }); await tick();
  assert.equal(restored.input.value, 'unsynchronized second branch');
  assert.match(restored.status.textContent, /другой вкладке/);
  const choose = restored.actions.children.find(b => b.textContent === 'Восстановить текст другой вкладки');
  choose.click(); assert.equal(restored.input.value, 'unsynchronized first branch');
});

test('05D unknown pending restores its exact prior text read-only and performs no draft GET/PUT', async () => {
  const one = fixture(); await tick(); const before = one.calls.length;
  one.draft.restorePending({ ...scope, draftSlotId: 'dialogue:earlier-question', draftValue: 'pending raw\ntext',
    draftRevision: 'sent-revision', requestId: 'original-request' });
  assert.equal(one.input.value, 'pending raw\ntext');
  assert.match(one.status.textContent, /Исход отправки пока не подтверждён/);
  await one.draft.flush(); assert.equal(one.calls.length, before);
});


test('05B reconnect with both local storage and network failed never clears the only DOM copy', async () => {
  const broken = { getItem() { throw Error(); }, setItem() { throw Error(); } };
  const one = fixture({ storage: broken, request: async () => { throw Error('offline'); } }); await tick();
  one.edit('the only current raw\ncopy'); one.draft.retry(); await tick();
  assert.equal(one.input.value, 'the only current raw\ncopy');
  assert.match(one.status.textContent, /Не удалось сохранить/);
});


test('05E sibling logout removal fences a late autosave ACK from recreating local text', async () => {
  let resolve; const remote = { owner_id: '8', cycle_id: 'cycle', assessment_situation_id: 'as', slot_id: scope.slotId,
    version: 0, revision: '', text: '', expires_at: scope.expiresAt };
  const one = fixture({ request: async data => data ? new Promise(r => { resolve = () => r({ ...remote,
    version: 1, revision: data.revision, text: data.text }); }) : remote });
  await tick(); one.edit('private text'); const pending = one.draft.flush();
  const key = Object.keys(one.storage)[0]; one.storage.removeItem(key);
  one.draft.storageChanged({ key, newValue: null }); resolve(); await pending;
  assert.equal(one.storage.getItem(key), null);
});


test('05C focus/reconnect never silently picks a remote revision while a conflict is unresolved', async () => {
  const one = fixture(); await tick(); one.edit('my confirmed version'); await one.draft.flush();
  one.server.text = 'other tab version'; one.server.version++; one.server.revision = 'foreign';
  const key = Object.keys(one.storage)[0];
  one.draft.storageChanged({ key, newValue: JSON.stringify({revision:'foreign',text:'other tab version'}) });
  const before = one.calls.length; one.draft.retry(); await tick();
  assert.equal(one.input.value, 'my confirmed version'); assert.equal(one.calls.length, before);
  assert.match(one.status.textContent, /другой вкладке/);
});


test('05 UI explicit remote choice changes only the draft and reports conflict resolution', async () => {
  const one = fixture(); await tick(); one.edit('local retained until choice');
  Object.assign(one.server, {text:'remote version',version:1,revision:'other'});
  await one.draft.flush(); assert.equal(one.draft.conflicted(),true);
  assert.equal(one.input.value,'local retained until choice');
  const writes=one.calls.filter(Boolean).length;
  await one.actions.children[1].click(); await tick();
  assert.equal(one.input.value,'remote version'); assert.equal(one.draft.conflicted(),false);
  assert.equal(one.calls.filter(Boolean).length,writes);
  assert.match(one.status.textContent,/Ответ ещё не отправлен/);
});

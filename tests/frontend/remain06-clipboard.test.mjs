import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

test('F21 actual clipboard handlers silently block transfers and protected selections in assessment scope', () => {
  const source = fs.readFileSync('web/js/wiring.js', 'utf8');
  const listeners = new Map();
  const target = (name) => ({ classList: { add() {}, contains: () => false },
    addEventListener(type, fn) { listeners.set(`${name}:${type}`, fn); },
    querySelectorAll: () => ['protected'] });
  let selected = true;
  const state = { currentScreen: 'interview' };
  const context = vm.createContext({ ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED: false,
    interviewPanel: target('panel'), interviewMessages: target('messages'), interviewTextarea: target('answer'),
    document: target('document'), state,
    window: { getSelection: () => ({ isCollapsed: !selected, containsNode: () => selected }) },
  });
  const start = source.indexOf('if (!ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED)');
  vm.runInContext(source.slice(start, source.indexOf("\ninterviewSubmitButton.addEventListener", start)), context);
  const dispatch = (name, fields = {}) => {
    let prevented = false;
    const event = { preventDefault() { prevented = true; }, stopImmediatePropagation() {},
      clipboardData: { getData() { assert.fail('clipboard must not be read'); } }, ...fields };
    listeners.get(name)(event); return prevented;
  };
  for (const type of ['paste', 'drop']) assert.equal(dispatch(`answer:${type}`), true);
  for (const inputType of ['insertFromPaste', 'insertFromDrop']) assert.equal(dispatch('answer:beforeinput', { inputType }), true);
  for (const fields of [{ key: 'v', ctrlKey: true }, { key: 'V', metaKey: true }, { key: 'Insert', shiftKey: true }]) {
    assert.equal(dispatch('answer:keydown', fields), true);
  }
  for (const inputType of ['insertText', 'insertCompositionText', 'deleteContentBackward']) assert.equal(dispatch('answer:beforeinput', { inputType }), false);
  for (const type of ['copy', 'cut']) {
    assert.equal(dispatch(`document:${type}`), true);
    selected = false; assert.equal(dispatch(`document:${type}`), false); selected = true;
    for (const screen of ['auth', 'admin', 'onboarding']) {
      state.currentScreen = screen; assert.equal(dispatch(`document:${type}`), false);
    }
    state.currentScreen = 'interview';
  }
});

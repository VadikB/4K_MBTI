import assert from 'node:assert/strict';
import test from 'node:test';
import { questionnaireAssignmentState } from '../../web/js/screens/admin/questionnaire-assignment-state.js';

for (const status of [undefined, 'loading', 'error']) {
  for (const confirmed of [false, true]) {
    test(`questionnaire ${status}, cached confirmed=${confirmed}: unknown is not unconfirmed`, () => {
      const value = questionnaireAssignmentState(status ? { status } : undefined, confirmed);
      assert.equal(value.canAssign, false);
      assert.doesNotMatch(value.label, /не подтверждена/);
      assert.doesNotMatch(value.blocker, /Анкета для выбранной оценки не подтверждена/);
      if (confirmed) assert.match(value.label, /по сохранённой редакции/);
    });
  }
}
for (const status of ['ready', 'empty']) {
  test(`questionnaire successful ${status} read: retain actual confirmation`, () => {
    assert.equal(questionnaireAssignmentState({ status }, true).canAssign, true);
    assert.equal(questionnaireAssignmentState({ status }, false).canAssign, false);
    assert.equal(questionnaireAssignmentState({ status }, false).label, 'не подтверждена');
  });
}

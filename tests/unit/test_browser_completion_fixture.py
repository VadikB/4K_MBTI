from copy import deepcopy
from uuid import uuid4

import pytest
from Api import m7_completion
from scripts.browser_completion_fixture import prepare


class Connection:
    def __init__(self, row): self.row=row
    def execute(self, sql, params):
        assert sql.lstrip().startswith('SELECT')
        return self
    def fetchone(self): return deepcopy(self.row)


@pytest.mark.parametrize('action', ['pause','interrupt_for_continuation'])
def test_saved_fixture_uses_internal_completion_on_qa_owner(monkeypatch, action):
    row={'owner_user_id':7,'usage_scope':'qa','status':'active','email':'participant@example.test'}
    calls=[]
    def command(connection, **kwargs):
        calls.append(kwargs)
        return {'action': kwargs['action']}
    monkeypatch.setattr(m7_completion,'control',command)
    monkeypatch.setattr(m7_completion,'complete',command)
    assert prepare(Connection(row),cycle_id=str(uuid4()),action=action)=={'action':action}
    assert calls[0]['initiated_by']==7
    assert 'participant_command' not in calls[0]  # internal seam, no public permission bypass


@pytest.mark.parametrize('defect', ['missing','product','other_owner','closed'])
def test_saved_fixture_rejects_an_inapplicable_target(monkeypatch, defect):
    row={'owner_user_id':7,'usage_scope':'qa','status':'active','email':'participant@example.test'}
    if defect=='missing': row=None
    if defect=='product': row['usage_scope']='assessment'
    if defect=='other_owner': row['email']='other@example.test'
    if defect=='closed': row['status']='collection_closed'
    def forbidden(*a,**k): raise AssertionError('must reject before mutation')
    monkeypatch.setattr(m7_completion,'control',forbidden)
    with pytest.raises(ValueError,match='BROWSER_SAVED_STATE_TARGET_INVALID'):
        prepare(Connection(row),cycle_id=str(uuid4()),action='pause')

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from Api import m7_completion


class Row:
    def __init__(self, value): self.value=value
    def fetchone(self): return deepcopy(self.value)


class Connection:
    def __init__(self): self.commands={}
    def execute(self, sql, params):
        if 'SELECT * FROM m7_completion_commands' in sql:
            return Row(self.commands.get(params[1]))
        assert 'INSERT INTO m7_completion_commands' in sql
        self.commands[params[1]]={'request_checksum':params[2],'result_json':json.loads(params[3])}
        return Row(None)


@pytest.mark.parametrize('participant', [True,False])
@pytest.mark.parametrize('limit', ['time_budget','calendar_deadline'])
def test_control_resume_preserves_automatic_expiry_and_original_command_readback(monkeypatch, participant, limit):
    c=Connection();cycle_id=str(uuid4())
    cycle={'id':1,'cycle_id':cycle_id,'status':'active'}
    monkeypatch.setattr(m7_completion,'_cycle',lambda *a,**k:deepcopy(cycle))
    monkeypatch.setattr(m7_completion,'_effective_limit',lambda *a:(limit,'boundary'))
    calls=[]
    def close(connection, **kwargs):
        calls.append(kwargs);cycle['status']='collection_closed'
        return {'reason':limit,'states':{'cycle':'collection_closed'}}
    monkeypatch.setattr(m7_completion,'complete',close)
    def forbidden(*a,**k): raise AssertionError('expiry must never enter resume admission')
    monkeypatch.setattr(m7_completion,'assert_participant_resume',forbidden)
    command=dict(cycle_id=cycle_id,key='resume',action='resume',reason='continue',initiated_by=7,
                 participant_command=participant)
    result=m7_completion.control(c,**command)
    assert result['states']['cycle']=='collection_closed'
    assert m7_completion.control(c,**command)==result
    with pytest.raises(ValueError,match='IDEMPOTENCY_CONFLICT'):
        m7_completion.control(c,**{**command,'reason':'changed'})
    assert len(calls)==1
    assert calls[0]['action']=='time_limit' and calls[0]['key']=='resume:expiry'

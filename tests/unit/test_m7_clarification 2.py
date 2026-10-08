import json

import pytest

from Api.m7_clarification_package import load_mechanism
from Api.m7_clarification_service import generate

pytestmark=pytest.mark.unit


def _input():
    return {'c54_revision_id':'00000000-0000-0000-0000-000000000001',
        'indicator_ids':['K1.1'],'uncertainties':[],'turns':[]}


class Gateway:
    enabled=True
    def __init__(self,value):self.value=value
    def chat(self,*args,**kwargs):return json.dumps(self.value,ensure_ascii=False)


def test_package_is_bound_to_registered_m7_source_and_snapshot():
    mechanism=load_mechanism()
    assert mechanism['ref']=='m7_assessment_clarification/1.0.0'
    assert mechanism['operation']['prompt_ref']['version']=='1.0.0'
    assert len(mechanism['snapshot_checksum'])==64


def test_question_is_limited_to_existing_uncertainty(monkeypatch):
    value={'schema_version':1,'admissible':True,'text':'Что вы имели в виду под основным доводом?',
        'purpose':'clarify_meaning','indicator_ids':['K1.1'],'resolving_information':['смысл'],'refusal_reason':None}
    monkeypatch.setattr('Api.m7_clarification_service._call_with_trace',
        lambda *args,**kwargs:(json.dumps(value,ensure_ascii=False),{'identity_status':'sent_matches_snapshot'}))
    result,trace=generate(_input(),load_mechanism(),gateway=Gateway(value))
    assert result['text']==value['text'] and trace['identity_status']=='sent_matches_snapshot'


@pytest.mark.parametrize('text',['Какой правильный ответ вы выберете?','Какой уровень оценки вам подходит?','Выполните новое действие?'])
def test_question_cannot_hint_at_result_or_new_action(monkeypatch,text):
    value={'schema_version':1,'admissible':True,'text':text,'purpose':'clarify_basis',
        'indicator_ids':['K1.1'],'resolving_information':['основание'],'refusal_reason':None}
    monkeypatch.setattr('Api.m7_clarification_service._call_with_trace',
        lambda *args,**kwargs:(json.dumps(value,ensure_ascii=False),{'identity_status':'sent_matches_snapshot'}))
    with pytest.raises(ValueError,match='M7_QUESTION_NOT_NEUTRAL'):
        generate(_input(),load_mechanism(),gateway=Gateway(value))

from Api.m10_product_flow import participant_trace, participant_presentation
from Api.m10_product_flow import participant_plan


def test_owner_trace_excludes_hidden_scenario_and_ai_payloads():
    def event(kind):
        return dict(event_id=kind,event_type=kind,sequence_no=1,material_id='m',payload_json={'content':'delivered'})
    value=participant_trace({'assessment_situation_id':'as','status':'active',
        'turns':[dict(turn_id='t',sequence_no=2,speaker_type='character',speaker_id='c',speaker_name='Нина, новый сотрудник',content_text='reply',request_id='internal')],
        'events':[event(k) for k in ('scenario_started','material_disclosed','mandatory_update','character_response','semantic_decision')]})
    assert [e['event_type'] for e in value['events']]==['material_disclosed','mandatory_update']
    assert value['turns'][0]['speaker_type']=='character'
    assert value['turns'][0]['speaker_name']=='Нина, новый сотрудник'
    assert 'request_id' not in value['turns'][0]


def test_owner_start_excludes_execution_envelope_without_mutating_saved_source():
    value={'plan':{'cycle_id':'cycle'},'presentation':{'status':'active','participant_payload':{'title':'case'},
        'execution_envelope':{'hidden':'secret'},'event':{'payload_json':{'execution_envelope':'secret'}}}}
    projected=participant_presentation(value)
    assert projected['presentation']=={'status':'active','participant_payload':{'title':'case'}}
    assert 'execution_envelope' in value['presentation']


def test_owner_trace_before_presentation_exposes_no_case_content():
    value = participant_trace({'assessment_situation_id': 'as-prepared', 'status': 'admitted',
        'turns': [{'content_text': 'hidden dialogue'}],
        'events': [{'event_type': 'material_disclosed', 'payload_json': {'content': 'hidden material'}}]})
    assert value == {'assessment_situation_id': 'as-prepared', 'status': 'admitted',
                     'turns': [], 'events': []}


def test_pilot_source_conditions_and_owner_records_are_not_participant_material():
    from tests.unit.test_pilot_plan_admission import snapshot
    s = snapshot()
    internal = {'cycle_id': 'synthetic-cycle', 'plan': {
        'full_target_set': [{}] * 61, 'planned_target_set': [{}] * 39,
        'pilot_plan_binding': {'binding_checksum': 'a' * 64, 'admission_snapshot': s}}}
    public = participant_plan(internal)
    assert 'pilot_plan_binding' not in public['plan']
    assert 'pilot_plan_binding' in internal['plan']
    assert public['plan']['pilot_plan_ref']['planned_target_count'] == 39
    assert public['plan']['participant_notice'] == s['participant_notice']
    assert participant_presentation({'plan': internal, 'presentation': None})['plan'] == public
    assert 'observation_occurrences' not in str(public)
    assert 'human_owner' not in str(public)

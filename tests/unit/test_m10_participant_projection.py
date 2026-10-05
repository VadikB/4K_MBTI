from Api.m10_product_flow import participant_trace, participant_presentation


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

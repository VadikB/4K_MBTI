from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api.m5_equivalent_generation import (ControlledEquivalentProvider, begin_generation,
    claim_generation, complete_generation, load_variability_package, run_provider)
from Api.m5_storage import import_package
from Api.m5_storage import prepare_assessment_situation
from Api.m5_scenario_runtime import build_c45,transition
from Api.m7_cycle_planner import _facts,choose_next,create_plan,present,read_plan
from Api.m7_completion import complete,create_additional_session,read_c46,reconcile_c46,expire_due_cycles
from Api.m7_route_replacement import (FixedCaseReplacementProvider,GeneratedCandidateReplacementProvider,
    replace_current,replacement_metadata)
from Api.m7_return_integration import continue_return,read_return_state,record_controlled_absence
from Api.m5_cycle_runtime import begin_blocking_wait,end_blocking_wait,read_cycle
from scripts.build_m5_case_package import OUTPUT

pytestmark=pytest.mark.integration


def setup(connection, admitted=False):
    package=json.loads((OUTPUT/'case-package.json').read_text());manifest=json.loads((OUTPUT/'manifest.json').read_text())
    rules=json.loads((OUTPUT/'execution-rules.json').read_text());case=package['cases'][0]
    if admitted:
        case['status']='FROZEN'
    connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)');connection.execute('INSERT INTO users VALUES(99)')
    connection.execute('''CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY,status TEXT,
        content_json JSONB,provenance_json JSONB,checksum TEXT)''')
    ensure_m5_runtime_schema(connection);import_package(connection,package=package,manifest=manifest,execution_rules=rules)
    connection.execute("INSERT INTO assessment_personalized_profiles VALUES(7,'ready',%s::jsonb,'{}',%s)",
        (json.dumps({'role_profile':{'code':case['base_role']}}),'c'*64))
    return case


def admit_case(connection,case):
    row=connection.execute("SELECT id FROM m5_case_versions WHERE case_id=%s",(case['case_id'],)).fetchone()
    for scope in ('case_format','case_dialogue','assessment_situation'):
        evidence={'eligibility':'user_admission','scope':scope,'synthetic':True}
        connection.execute("INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum) VALUES(%s,%s,'PASS',%s::jsonb,%s)",
            (row['id'],scope,json.dumps(evidence),checksum(evidence)))


@pytest.fixture
def db(test_database_url):
    schema='m7_plan_pytest_'+uuid4().hex
    with psycopg.connect(test_database_url,row_factory=dict_row) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    def connect():
        c=psycopg.connect(test_database_url,row_factory=dict_row)
        c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)));c.commit();return c
    try:yield connect
    finally:
        with psycopg.connect(test_database_url) as c:c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_plan_keeps_full_goal_and_explains_unadmitted_pool(db):
    with db() as c:
        setup(c);result=create_plan(c,personalized_profile_id=7,selected_skills=['K1','K2','K3','K4'],created_by=99,key='plan');c.commit()
        assert result['plan']['status']=='NO_ROUTE'
        assert result['plan']['uncovered_target_ids']
        assert all(not x['eligible'] for x in result['plan']['catalog'])
        assert result['cycle_status']=='prepared'


def test_same_latest_fail_blocks_planner_and_direct_as(db):
    with db() as c:
        case = setup(c, admitted=True)
        admit_case(c, case)
        case_row = c.execute("SELECT id FROM m5_case_versions WHERE case_id=%s",
                             (case['case_id'],)).fetchone()
        failed = {'eligibility':'user_admission','scope':'case_dialogue','result':'FAIL','synthetic':True}
        c.execute("""INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                     VALUES(%s,'case_dialogue','FAIL',%s::jsonb,%s)""",
                  (case_row['id'], json.dumps(failed), checksum(failed)))
        plan = create_plan(c, personalized_profile_id=7,
                           selected_skills=['K1','K2','K3','K4'], created_by=99, key='denied')
        assert plan['plan']['status'] == 'NO_ROUTE'
        denied = next(item for item in plan['plan']['catalog'] if item['case_id'] == case['case_id'])
        assert 'QA_EVIDENCE_MISSING_OR_FAIL:case_dialogue' in denied['reasons']
        cycle = c.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s",
                          (plan['cycle_id'],)).fetchone()
        session = c.execute("SELECT id FROM m5_cycle_sessions WHERE cycle_db_id=%s",
                            (cycle['id'],)).fetchone()
        policy = json.loads((OUTPUT/'admission-policy.json').read_text())
        with pytest.raises(ValueError, match='M5_CASE_NOT_ADMITTED'):
            prepare_assessment_situation(
                c, assessment_situation_id=str(uuid4()), case_id=case['case_id'],
                case_version=case['version'], personalized_profile_id=7,
                cycle_db_id=cycle['id'], session_db_id=session['id'], substitutions=[],
                policy=policy, usage_scope='assessment',
            )


def test_selected_case_is_prepared_presented_once_and_low_level_does_not_drive_repeat(db):
    with db() as c:
        case=setup(c,admitted=True);admit_case(c,case)
        plan=create_plan(c,personalized_profile_id=7,selected_skills=['K1','K2','K3','K4'],created_by=99,key='plan');c.commit()
        # The M4 row is mutable only in this adversarial fixture. The already-created
        # Cycle must keep the frozen selected role when direct AS preparation runs.
        c.execute("UPDATE assessment_personalized_profiles SET content_json=%s::jsonb WHERE id=7",
                  (json.dumps({'role_profile': {'code': 'changed-organization-role'}}),))
        c.commit()
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        decision=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='next',created_by=99,policy=policy)
        replay=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='next',created_by=99,policy=policy)
        assert decision['id']==replay['id'] and decision['status']=='SELECTED', (decision['considered_json'],plan['plan']['route'],plan['plan']['catalog'][0])
        assert decision['assessment_situation_status']=='admitted';c.commit()
    with db() as c:
        result=present(c,decision_id=str(decision['id']),expected_revision=1);c.commit()
        assert result['presentation']['status']=='active'
        saved=read_plan(c,str(plan['cycle_id']))
        assert saved['cycle_status']=='active' and len(saved['decisions'])==1
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==1
        waiting=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='while-active',created_by=99,policy=policy)
        assert waiting['status']=='WAITING_CURRENT_AS'
        as_id=str(result['decision']['assessment_situation_id'])
        transition(c,assessment_situation_id=as_id,action='scenario_end',reason='synthetic',request_id='end')
        transition(c,assessment_situation_id=as_id,action='close',reason='synthetic',request_id='close')
        handoff=build_c45(c,as_id,mode='final')
        as_db=c.execute('SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s',(as_id,)).fetchone()['id']
        for target in case['indicator_targets']:
            payload={'target':{'indicator_id':target['indicator_id'],'status':'ASSESSED','outcome':'L0','opportunity':'PRESENT'}}
            c.execute('''INSERT INTO m5_c54_receipts(assessment_situation_db_id,handoff_id,receipt_id,mode,indicator_id,m2_version,
                boundary_sequence,status,payload_json,validation_json,controlled_test) VALUES(%s,%s,%s,'final',%s,%s,%s,'accepted',%s::jsonb,'{}',TRUE)''',
                (as_db,handoff['handoff_id'],uuid4(),target['indicator_id'],target['m2_version'],handoff['boundary_sequence'],json.dumps(payload)))
        after_l0=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='after-l0',created_by=99,policy=policy)
        assert after_l0['status']=='NO_ADMISSIBLE_CASE'
        assert set(after_l0['facts_json']['final_ia_target_ids'])=={x['indicator_id'] for x in case['indicator_targets']}


def test_active_route_position_is_replaced_once_without_counting_archived_as(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id'])
        old_as=str(shown['decision']['assessment_situation_id'])
        old_row=c.execute('SELECT id,snapshot_json FROM m5_assessment_situations WHERE assessment_situation_id=%s',(old_as,)).fetchone()
        late_target=old_row['snapshot_json']['indicator_targets'][0]
        route=replacement_metadata(c, c.execute('SELECT id FROM m5_cycles').fetchone()['id'])
        assert route['progress']=={'total_positions':1,'completed_positions':0}
        request=dict(cycle_id=cycle_id,position_no=1,expected_assessment_situation_id=old_as,
            expected_state='active',key='replace-position-1',reason='authorized_return',
            policy_ref={'id':'P01','version':'2.0','checksum':'a'*64},requested_by=99,
            provider=FixedCaseReplacementProvider(policy))
        result=replace_current(c,**request)
        replay=replace_current(c,**request)
        assert replay==result and result['new_assessment_situation_id']!=old_as
        rows=c.execute('SELECT assessment_situation_id,status FROM m5_assessment_situations ORDER BY id').fetchall()
        assert [(str(x['assessment_situation_id']),x['status']) for x in rows]==[
            (old_as,'terminated'),(result['new_assessment_situation_id'],'admitted')]
        route=replacement_metadata(c, c.execute('SELECT id FROM m5_cycles').fetchone()['id'])
        assert len(route['positions'])==1 and len(route['positions'][0]['history'])==2
        assert [x['disposition'] for x in route['positions'][0]['history']]==['replaced','current']
        # Simulate a late worker result already in flight. It remains auditable but
        # cannot contribute to current facts or final calculation.
        c.execute("UPDATE m5_assessment_situations SET status='closed',closed_at=NOW() WHERE id=%s",(old_row['id'],))
        late_handoff=build_c45(c,old_as,mode='final')
        c.execute("UPDATE m5_assessment_situations SET status='terminated',closed_at=NULL WHERE id=%s",(old_row['id'],))
        late_payload={'target':{'indicator_id':late_target['indicator_id'],'status':'ASSESSED',
            'outcome':'L3','opportunity':'PRESENT'}}
        c.execute('''INSERT INTO m5_c54_receipts(assessment_situation_db_id,handoff_id,receipt_id,mode,indicator_id,m2_version,
            boundary_sequence,status,payload_json,validation_json,controlled_test)
            VALUES(%s,%s,%s,'final',%s,%s,%s,'accepted',%s::jsonb,'{}',TRUE)''',
            (old_row['id'],late_handoff['handoff_id'],uuid4(),late_target['indicator_id'],late_target['m2_version'],
             late_handoff['boundary_sequence'],json.dumps(late_payload)))
        assert _facts(c,c.execute('SELECT id FROM m5_cycles').fetchone()['id'],{late_target['indicator_id']})['final_ia_target_ids']==[]
        with pytest.raises(ValueError,match='M7_REPLACEMENT_STALE_CURRENT_AS'):
            replace_current(c,**{**request,'key':'stale-replace'})
        completed=complete(c,cycle_id=cycle_id,key='finish-after-replacement',action='complete',
            reason='plan_finished',initiated_by=99)
        assert completed['final_handoff_ids']==[]
        assert c.execute('SELECT count(*) AS n FROM m7_finalization_outbox').fetchone()['n']==0
        c46=read_c46(c,cycle_id)['payload_json']
        assert len(c46['route']['positions'])==1
        assert {x['route_disposition'] for x in c46['assessment_situations']}=={'replaced','current'}
        from Api.m6_cycle_aggregation_repository import _inputs
        _,_,material=_inputs(c,cycle_id,c46['composition_checksum'])
        assert material['observations']==[]
        assert {x['status'] for x in material['processing']}=={'excluded_replaced','not_presented'}


def test_equivalent_generation_is_persisted_validated_and_handed_to_p01(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    package=load_variability_package()
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id'])
        old_as=str(shown['decision']['assessment_situation_id'])
        operation=begin_generation(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,
            request_key='p02-generate-1',requested_by=99,package=package,
            provider_config={'id':'controlled','version':'1','checksum':'a'*64})
        replay=begin_generation(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,
            request_key='p02-generate-1',requested_by=99,package=package,
            provider_config={'id':'controlled','version':'1','checksum':'a'*64})
        assert replay['id']==operation['id']
        claimed=claim_generation(c,str(operation['id']));c.commit()
    source=claimed['input_json']['old_content']
    candidate={'case_id':'CASE-TDISC-01','case_version':'v0.1',
        'base_role':claimed['input_json']['base_role'],'indicator_targets':claimed['input_json']['indicator_targets'],
        'participant_payload':deepcopy(source['participant_payload']),
        'execution_payload':deepcopy(source['execution_payload'])}
    candidate['participant_payload']['initial_situation']='Согласованная новая вводная QA.'
    candidate['participant_payload']['trigger']='Новый содержательный триггер QA.'
    candidate['execution_payload']['materials'][0]['participant_payload']='Согласованная новая вводная QA.'
    output=run_provider(ControlledEquivalentProvider(candidate),claimed)
    with db() as c:
        completed=complete_generation(c,operation_id=str(operation['id']),lease_token=str(claimed['lease_token']),
            candidate=output,policy=policy)
        assert completed['status']=='completed' and completed['validation']['admitted']
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==2
        replaced=replace_current(c,cycle_id=cycle_id,position_no=1,
            expected_assessment_situation_id=old_as,expected_state='active',key='p01-after-p02',
            reason='authorized_return',policy_ref={'id':'P01','version':'2.0','checksum':'f'*64},requested_by=99,
            provider=GeneratedCandidateReplacementProvider(str(operation['id'])))
        assert replaced['new_assessment_situation_id']==completed['assessment_situation_id']
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==2


def test_equivalent_generation_claim_is_single_and_late_result_is_not_admitted(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);old_as=str(shown['decision']['assessment_situation_id'])
        operation=begin_generation(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,
            request_key='p02-late',requested_by=99,package=load_variability_package(),
            provider_config={'id':'controlled','version':'1','checksum':'b'*64});c.commit()
    def claim():
        with db() as c:
            try:
                result=claim_generation(c,str(operation['id']));c.commit();return result
            except ValueError as exc:
                return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=[future.result(timeout=20) for future in (pool.submit(claim),pool.submit(claim))]
    claimed=next(item for item in outcomes if isinstance(item,dict))
    assert outcomes.count('M5_EQUIVALENT_OPERATION_ALREADY_CLAIMED')==1
    source=claimed['input_json']['old_content']
    candidate={'case_id':'CASE-TDISC-01','case_version':'v0.1','base_role':claimed['input_json']['base_role'],
        'indicator_targets':claimed['input_json']['indicator_targets'],
        'participant_payload':deepcopy(source['participant_payload']),'execution_payload':deepcopy(source['execution_payload'])}
    candidate['participant_payload']['initial_situation']='Поздняя новая вводная.'
    candidate['participant_payload']['trigger']='Поздний новый триггер.'
    candidate['execution_payload']['materials'][0]['participant_payload']='Поздняя новая вводная.'
    with db() as c:
        c.execute("UPDATE m5_cycles SET status='collection_closed'");c.commit()
    with db() as c:
        result=complete_generation(c,operation_id=str(operation['id']),lease_token=str(claimed['lease_token']),
            candidate=candidate,policy=policy);c.commit()
        assert result=={'status':'rejected_late','error_code':'M5_EQUIVALENT_OPERATION_EXPIRED'}
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==1


def test_controlled_return_179_continues_same_as_without_restoring_budget(db):
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);old_as=str(shown['decision']['assessment_situation_id'])
        c.execute("UPDATE m5_cycle_time_intervals SET started_at=NOW()-INTERVAL '300 seconds' WHERE ended_at IS NULL")
        before=read_cycle(c,cycle_id);deadline=before['calendar_deadline']
        evaluated=datetime.now(timezone.utc)
        event=record_controlled_absence(c,cycle_id=cycle_id,expected_as_id=old_as,source_ref='controlled-179',
            recognized_at=evaluated-timedelta(seconds=179))
        counts_before=c.execute("SELECT (SELECT count(*) FROM m5_assessment_situations) AS situations,(SELECT count(*) FROM m7_return_commands) AS commands").fetchone()
        state=read_return_state(c,cycle_id=cycle_id,owner_user_id=99,evaluated_at=evaluated)
        counts_after=c.execute("SELECT (SELECT count(*) FROM m5_assessment_situations) AS situations,(SELECT count(*) FROM m7_return_commands) AS commands").fetchone()
        assert counts_after==counts_before
        assert state['allowed_action']=='continue_current' and state['recognized_absence_seconds']==179
        assert state['progress']=={'total_positions':1,'completed_positions':0}
        assert str(event['id'])==state['absence_event_id']
        result=continue_return(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,expected_state='active',
            key='return-179',owner_user_id=99,evaluated_at=evaluated)
        replay=continue_return(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,expected_state='active',
            key='return-179',owner_user_id=99,evaluated_at=evaluated)
        assert replay==result and result['branch']=='continued_current'
        assert result['assessment_situation_id']==old_as and result['remaining_seconds']<=state['remaining_seconds']
        assert result['remaining_seconds']<int(c.execute('SELECT time_budget_seconds FROM m5_cycles').fetchone()['time_budget_seconds'])
        assert result['calendar_deadline']==deadline.isoformat()
        assert c.execute("SELECT count(*) AS n FROM m5_assessment_situations").fetchone()['n']==1


def test_controlled_return_180_replaces_presents_once_and_keeps_deadline(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text());package=load_variability_package()
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);old_as=str(shown['decision']['assessment_situation_id'])
        c.execute("UPDATE m5_cycle_time_intervals SET started_at=NOW()-INTERVAL '300 seconds' WHERE ended_at IS NULL")
        deadline=read_cycle(c,cycle_id)['calendar_deadline'];evaluated=datetime.now(timezone.utc)
        record_controlled_absence(c,cycle_id=cycle_id,expected_as_id=old_as,source_ref='controlled-180',
            recognized_at=evaluated-timedelta(seconds=180))
        operation=begin_generation(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,
            request_key='p03-generate',requested_by=99,package=package,
            provider_config={'id':'controlled','version':'1','checksum':'e'*64})
        claimed=claim_generation(c,str(operation['id']));source=claimed['input_json']['old_content']
        candidate={'case_id':'CASE-TDISC-01','case_version':'v0.1','base_role':claimed['input_json']['base_role'],
            'indicator_targets':claimed['input_json']['indicator_targets'],
            'participant_payload':deepcopy(source['participant_payload']),'execution_payload':deepcopy(source['execution_payload'])}
        candidate['participant_payload']['initial_situation']='Новая ситуация после возврата.'
        candidate['participant_payload']['trigger']='Новый триггер после возврата.'
        candidate['execution_payload']['materials'][0]['participant_payload']='Новая ситуация после возврата.'
        completed=complete_generation(c,operation_id=str(operation['id']),lease_token=str(claimed['lease_token']),
            candidate=candidate,policy=policy)
        state=read_return_state(c,cycle_id=cycle_id,owner_user_id=99,evaluated_at=evaluated)
        assert state['allowed_action']=='replace_current' and state['recognized_absence_seconds']==180
        result=continue_return(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,expected_state='active',
            key='return-180',owner_user_id=99,generation_operation_id=str(operation['id']),evaluated_at=evaluated)
        replay=continue_return(c,cycle_id=cycle_id,position_no=1,expected_as_id=old_as,expected_state='active',
            key='return-180',owner_user_id=99,generation_operation_id=str(operation['id']),evaluated_at=evaluated)
        assert replay==result and result['branch']=='replaced_current'
        assert result['assessment_situation_id']==completed['assessment_situation_id'] and result['calendar_deadline']==deadline.isoformat()
        rows=c.execute("SELECT assessment_situation_id,status FROM m5_assessment_situations ORDER BY id").fetchall()
        assert [(str(row['assessment_situation_id']),row['status']) for row in rows]==[(old_as,'terminated'),(completed['assessment_situation_id'],'active')]
        route=replacement_metadata(c,c.execute('SELECT id FROM m5_cycles').fetchone()['id'])
        assert route['progress']=={'total_positions':1,'completed_positions':0}
        assert [x['disposition'] for x in route['positions'][0]['history']]==['replaced','current']


def test_two_replacement_requests_have_one_effect(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id'])
        old_as=str(shown['decision']['assessment_situation_id']);c.commit()
    request=dict(cycle_id=cycle_id,position_no=1,expected_assessment_situation_id=old_as,
        expected_state='active',key='same-key-two-tabs',reason='authorized_return',
        policy_ref={'id':'P01','version':'2.0','checksum':'b'*64},requested_by=99,
        provider=FixedCaseReplacementProvider(policy))
    def run():
        with db() as c:
            result=replace_current(c,**request);c.commit();return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        left,right=[future.result(timeout=20) for future in (pool.submit(run),pool.submit(run))]
    assert left==right
    with db() as c:
        assert c.execute('SELECT count(*) AS n FROM m7_as_replacement_operations').fetchone()['n']==1
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==2


def test_replacement_preparation_failure_is_saved_without_half_switch(db):
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id'])
        old_as=str(shown['decision']['assessment_situation_id'])
        request=dict(cycle_id=cycle_id,position_no=1,expected_assessment_situation_id=old_as,
            expected_state='active',key='provider-unavailable',reason='authorized_return',
            policy_ref={'id':'P01','version':'2.0','checksum':'c'*64},requested_by=99,provider=None)
        failed=replace_current(c,**request)
        assert replace_current(c,**request)==failed
        assert failed['status']=='preparation_failed'
        assert c.execute('SELECT status FROM m5_assessment_situations').fetchone()['status']=='active'
        assert c.execute('SELECT state FROM m7_route_positions').fetchone()['state']=='awaiting_replacement'
        operation=c.execute('SELECT status,error_code FROM m7_as_replacement_operations').fetchone()
        assert operation=={'status':'preparation_failed','error_code':'M7_REPLACEMENT_PROVIDER_UNAVAILABLE'}


def test_replacement_rejects_foreign_position_expired_and_terminal_cycle(db):
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);old_as=str(shown['decision']['assessment_situation_id'])
        base=dict(cycle_id=cycle_id,position_no=1,expected_assessment_situation_id=old_as,
            expected_state='active',reason='authorized_return',
            policy_ref={'id':'P01','version':'2.0','checksum':'d'*64},provider=FixedCaseReplacementProvider(policy))
        with pytest.raises(ValueError,match='M7_CYCLE_NOT_FOUND'):
            replace_current(c,**base,key='foreign-owner',requested_by=98)
        with pytest.raises(ValueError,match='M7_ROUTE_POSITION_NOT_FOUND'):
            replace_current(c,**{**base,'position_no':2},key='foreign-position',requested_by=99)
        c.execute("UPDATE m5_cycles SET started_at=NOW()-INTERVAL '2 hours',calendar_window_seconds=1")
        with pytest.raises(ValueError,match='M7_TIME_LIMIT_REACHED'):
            replace_current(c,**base,key='expired',requested_by=99)
        c.execute("UPDATE m5_cycles SET status='collection_closed'")
        with pytest.raises(ValueError,match='M7_COLLECTION_CLOSED'):
            replace_current(c,**base,key='terminal',requested_by=99)


def active_cycle(connection):
    case=setup(connection,admitted=True);admit_case(connection,case)
    plan=create_plan(connection,personalized_profile_id=7,selected_skills=['K1','K2','K3','K4'],created_by=99,key='plan')
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    decision=choose_next(connection,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='next',created_by=99,policy=policy)
    shown=present(connection,decision_id=str(decision['id']),expected_revision=1)
    return plan,shown


def test_completion_closes_open_as_persists_final_c45_and_c46(db):
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);as_id=str(shown['decision']['assessment_situation_id'])
        result=complete(c,cycle_id=cycle_id,key='finish',action='complete',reason='plan_finished',initiated_by=99)
        replay=complete(c,cycle_id=cycle_id,key='finish',action='complete',reason='plan_finished',initiated_by=99)
        assert replay==result and result['states']=={'cycle':'collection_closed','session':'completed'}
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE assessment_situation_id=%s',(as_id,)).fetchone()['status']=='closed'
        assert c.execute("SELECT count(*) AS n FROM m5_scenario_events WHERE event_type='scenario_completed'").fetchone()['n']==0
        assert c.execute("SELECT count(*) AS n FROM m5_scenario_events WHERE event_type='interaction_terminated'").fetchone()['n']==1
        handoff=build_c45(c,as_id,mode='final');assert str(handoff['handoff_id']) in result['final_handoff_ids']
        assert c.execute('SELECT status FROM m7_finalization_outbox').fetchone()['status']=='pending'
        c46=read_c46(c,cycle_id);assert c46['payload_json']['calculation']['status']=='pending'
        assert c46['payload_json']['composition_checksum']==c46['composition_checksum']
        calculation={'cycle_id':cycle_id,'composition_checksum':c46['composition_checksum'],'revision_id':str(uuid4())}
        empty_cut={'numerator':0,'denominator':9,'included_ids':[],'missing_ids':['synthetic']}
        coverage={key:empty_cut for key in ('opportunities','indicator_assessments','admissible_contributions','components_with_score','complete_components')}
        reconciled=reconcile_c46(c,cycle_id=cycle_id,expected_composition_checksum=c46['composition_checksum'],calculation_ref=calculation,
            coverage=coverage,skill_outcomes=[{'skill_id':'K1','outcome':'partial_score','score':0}])
        assert reconciled['revision_no']==2 and reconciled['status']=='reconciled'
        assert c.execute('SELECT status FROM m5_cycles').fetchone()['status']=='calculated'
        with pytest.raises(ValueError,match='COMPOSITION_MISMATCH'):
            reconcile_c46(c,cycle_id=cycle_id,expected_composition_checksum='0'*64,calculation_ref=calculation,coverage=coverage,skill_outcomes=[])


def test_interruption_allows_one_additional_session_without_copying_dialogue(db):
    with db() as c:
        plan,shown=active_cycle(c);cycle_id=str(plan['cycle_id']);old_as=str(shown['decision']['assessment_situation_id'])
        interrupted=complete(c,cycle_id=cycle_id,key='later',action='interrupt_for_continuation',reason='authorized_return',initiated_by=99)
        new_session=create_additional_session(c,cycle_id=cycle_id,intent_id=interrupted['continuation_intent_id'],key='additional-1',created_by=99)
        assert new_session['ordinal']==2 and new_session['status']=='prepared'
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==1
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE assessment_situation_id=%s',(old_as,)).fetchone()['status']=='closed'
        with pytest.raises(ValueError,match='M7_ADDITIONAL_SESSION_NOT_ALLOWED'):
            create_additional_session(c,cycle_id=cycle_id,intent_id=interrupted['continuation_intent_id'],key='additional-2',created_by=99)


def test_background_calendar_expiry_closes_paused_cycle(db):
    from Api.m5_cycle_runtime import transition_session
    with db() as c:
        plan,_=active_cycle(c);cycle_id=str(plan['cycle_id'])
        session=c.execute('SELECT session_id FROM m5_cycle_sessions ORDER BY ordinal DESC LIMIT 1').fetchone()
        transition_session(c,session_id=str(session['session_id']),action='pause',reason='authorized')
        c.execute("UPDATE m5_cycles SET started_at=NOW()-INTERVAL '80 hours',calendar_window_seconds=3600")
        results=expire_due_cycles(c,initiated_by=99)
        assert len(results)==1 and results[0]['reason']=='calendar_deadline'
        assert c.execute('SELECT status FROM m5_cycles').fetchone()['status']=='collection_closed'


def test_blocking_wait_is_explicit_idempotent_and_does_not_move_deadline(db):
    with db() as c:
        plan,_=active_cycle(c);cycle_id=str(plan['cycle_id']);before=read_cycle(c,cycle_id)
        cycle=c.execute('SELECT id FROM m5_cycles WHERE cycle_id=%s',(plan['cycle_id'],)).fetchone()
        session=c.execute('SELECT id FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1',(cycle['id'],)).fetchone()
        waiting=begin_blocking_wait(c,cycle_db_id=cycle['id'],session_db_id=session['id'],operation_ref='m6:attempt-1',reason='user_blocked')
        replay=begin_blocking_wait(c,cycle_db_id=cycle['id'],session_db_id=session['id'],operation_ref='m6:attempt-1',reason='user_blocked')
        assert replay['id']==waiting['id']
        end_blocking_wait(c,cycle_db_id=cycle['id'],session_db_id=session['id'],operation_ref='m6:attempt-1',reason='finished')
        after=read_cycle(c,cycle_id);assert after['calendar_deadline']==before['calendar_deadline']
        assert c.execute("SELECT count(*) AS n FROM m5_cycle_time_intervals WHERE interval_type='blocking_system_wait'").fetchone()['n']==1

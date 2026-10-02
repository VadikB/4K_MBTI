from __future__ import annotations
from datetime import datetime,timezone
import json
from uuid import UUID

from Api.m5_case_runtime import checksum
from Api.assessment_configuration import definition_checksum
from Api.m5_cycle_runtime import read_cycle
from Api.m5_scenario_runtime import _next_sequence,build_c45
from Api.m7_clarification_package import load_mechanism
from Api.m7_clarification_service import generate
from Api import m7_clarification_repository as repo

def _source(connection,c54_revision_id:str,lock=False):
    suffix=' FOR UPDATE OF s' if lock else ''
    row=connection.execute("""SELECT c.id AS c54_id,c.payload_json,c.payload_hash,c.mode,c.handoff_id,
        a.id AS assessment_revision_id,r.input_json,s.*,h.boundary_sequence,h.envelope_checksum
        FROM m6_c54_revisions c JOIN m6_assessment_revisions a ON a.id=c.assessment_revision_id
        JOIN m6_assessment_requests r ON r.id=a.request_id JOIN m5_assessment_situations s ON s.id=c.as_db_id
        JOIN m5_c45_handoffs h ON h.handoff_id=c.handoff_id WHERE c.id=%s"""+suffix,(UUID(c54_revision_id),)).fetchone()
    if not row:raise ValueError('M7_C54_NOT_FOUND')
    if definition_checksum(row['payload_json'])!=row['payload_hash']:raise ValueError('CHECKSUM_MISMATCH')
    return dict(row)

def decide(connection,*,c54_revision_id:str,key:str,created_by:int,gateway=None):
    source=_source(connection,c54_revision_id,lock=True);as_db=source['id']
    request_hash=checksum({'c54_revision_id':c54_revision_id})
    prior=repo.existing(connection,as_db,key,request_hash)
    if prior:return prior
    latest=connection.execute("SELECT id FROM m6_c54_revisions WHERE as_db_id=%s AND mode='interim' ORDER BY created_at DESC LIMIT 1",(as_db,)).fetchone()
    if not latest or str(latest['id'])!=c54_revision_id:raise ValueError('M7_STALE_C54')
    cycle=read_cycle(connection,str(connection.execute('SELECT cycle_id FROM m5_cycles WHERE id=%s',(source['cycle_db_id'],)).fetchone()['cycle_id']))
    mechanism=load_mechanism()
    minimum_seconds=mechanism['decision']['minimum_remaining_seconds']
    targets=source['payload_json'].get('interim_targets') or []
    uncertainties=[{'indicator_id':x['indicator_id'],'m2_version':x['m2_version'],'uncertainty':x.get('uncertainty'),
        'rationale':x['rationale'],'refs':x['refs']} for x in targets if x.get('uncertainty')]
    input_value={'schema_version':1,'c54_revision_id':c54_revision_id,'handoff_id':str(source['handoff_id']),
        'boundary_sequence':source['boundary_sequence'],'as_id':str(source['assessment_situation_id']),
        'indicator_ids':[x['indicator_id'] for x in uncertainties],'uncertainties':uncertainties,
        'turns':source['input_json']['material']['turns'],'case_ref':source['snapshot_json']['case_ref'],
        'remaining_seconds':cycle['remaining_seconds'],'minimum_remaining_seconds':minimum_seconds,
        'calendar_deadline':cycle['calendar_deadline'].isoformat() if cycle['calendar_deadline'] else None}
    status='NO_QUESTION';question=None;trace={};explanation={'code':'M7_NO_ASSESSMENT_UNCERTAINTY'}
    if source['mode']!='interim' or source['status']!='scenario_ended':status='STOP';explanation={'code':'M7_AS_NOT_OPEN_AFTER_SCENARIO'}
    elif cycle['status'] not in {'active','paused'}:status='STOP';explanation={'code':'M7_COLLECTION_CLOSED'}
    elif cycle['started_at'] and (cycle['remaining_seconds']<minimum_seconds or (cycle['calendar_deadline'] and datetime.now(timezone.utc)>=cycle['calendar_deadline'])):status='STOP';explanation={'code':'M7_CLARIFICATION_TIME_UNAVAILABLE'}
    elif any(x['uncertainty']['requires_new_independent_action'] for x in uncertainties):status='NEW_AS';explanation={'code':'M7_NEW_INDEPENDENT_ACTION_REQUIRED','indicator_ids':[x['indicator_id'] for x in uncertainties if x['uncertainty']['requires_new_independent_action']]}
    elif uncertainties:
        try:question,trace=generate(input_value,mechanism,gateway=gateway)
        except Exception as exc:
            status='WAIT_TECHNICAL';trace=getattr(exc,'ai_trace',{});explanation={'code':'M7_QUESTION_GENERATION_FAILED','error_type':type(exc).__name__}
        else:
            if question['admissible']:status='ASK';explanation={'code':'M7_CLARIFICATION_ADMISSIBLE','purpose':question['purpose']}
            else:status='NO_QUESTION';explanation={'code':'M7_QUESTION_NOT_ADMISSIBLE','reason':question['refusal_reason']}
    saved=repo.save(connection,as_db_id=as_db,c54_revision_id=c54_revision_id,key=key,request_hash=request_hash,status=status,
        input_value=input_value,mechanism=mechanism,question=question,explanation=explanation,trace=trace,created_by=created_by)
    return repo.read(connection,saved['id'])

def present(connection,*,decision_id:str,expected_c54_revision_id:str):
    decision=repo.read(connection,decision_id)
    if decision['question_turn_id']:return decision
    if decision['status']!='ASK':raise ValueError('M7_CLARIFICATION_NOT_PRESENTABLE')
    if str(decision['c54_revision_id'])!=expected_c54_revision_id:raise ValueError('M7_STALE_C54')
    source=_source(connection,expected_c54_revision_id,lock=True)
    latest=connection.execute("SELECT id FROM m6_c54_revisions WHERE as_db_id=%s AND mode='interim' ORDER BY created_at DESC LIMIT 1",(source['id'],)).fetchone()
    if source['status']!='scenario_ended' or not latest or str(latest['id'])!=expected_c54_revision_id:raise ValueError('M7_CLARIFICATION_STATE_CHANGED')
    cycle=read_cycle(connection,str(connection.execute('SELECT cycle_id FROM m5_cycles WHERE id=%s',(source['cycle_db_id'],)).fetchone()['cycle_id']))
    minimum_seconds=decision['mechanism_json']['decision']['minimum_remaining_seconds']
    if cycle['status']!='active' or cycle['remaining_seconds']<minimum_seconds or (cycle['calendar_deadline'] and datetime.now(timezone.utc)>=cycle['calendar_deadline']):raise ValueError('M7_CLARIFICATION_TIME_UNAVAILABLE')
    turn_id=UUID(str(decision['id']));seq=_next_sequence(connection,source['id'])
    connection.execute("""INSERT INTO m5_dialogue_turns(assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES(%s,%s,%s,'assessment','m7-clarification',%s,%s)""",(source['id'],turn_id,seq,decision['question_json']['text'],f'm7-question:{decision_id}'))
    connection.execute('INSERT INTO m7_clarification_deliveries VALUES(%s,%s,%s,NOW())',(decision['id'],turn_id,seq))
    return repo.read(connection,decision_id)

def answer(connection,*,decision_id:str,request_id:str,turn_id:str,content:str):
    decision=repo.read(connection,decision_id)
    if decision['response_outcome']:
        existing=connection.execute('SELECT content_text,request_id FROM m5_dialogue_turns WHERE turn_id=%s',(decision['answer_turn_id'],)).fetchone()
        if not existing or existing['request_id']!=request_id or existing['content_text']!=content:raise ValueError('IDEMPOTENCY_CONFLICT')
        return decision
    if not decision['question_turn_id']:raise ValueError('M7_QUESTION_NOT_DELIVERED')
    source=_source(connection,str(decision['c54_revision_id']),lock=True)
    if source['status']!='scenario_ended':raise ValueError('M7_CLARIFICATION_STATE_CHANGED')
    cycle=read_cycle(connection,str(connection.execute('SELECT cycle_id FROM m5_cycles WHERE id=%s',(source['cycle_db_id'],)).fetchone()['cycle_id']))
    if cycle['status']!='active' or (cycle['calendar_deadline'] and datetime.now(timezone.utc)>=cycle['calendar_deadline']):raise ValueError('M7_CLARIFICATION_TIME_UNAVAILABLE')
    seq=_next_sequence(connection,source['id']);tid=UUID(turn_id)
    connection.execute("""INSERT INTO m5_dialogue_turns(assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES(%s,%s,%s,'assessee','assessee',%s,%s)""",(source['id'],tid,seq,content,request_id))
    handoff=build_c45(connection,str(source['assessment_situation_id']),mode='interim')
    connection.execute("INSERT INTO m7_clarification_responses(decision_id,outcome,request_id,answer_turn_id,sequence_no,handoff_id) VALUES(%s,'answered',%s,%s,%s,%s)",
        (decision['id'],request_id,tid,seq,handoff['handoff_id']))
    return repo.read(connection,decision_id)

def record_outcome(connection,*,decision_id:str,request_id:str,outcome:str):
    decision=repo.read(connection,decision_id)
    if outcome not in {'no_answer','refused'}:raise ValueError('M7_CLARIFICATION_OUTCOME_INVALID')
    if decision['response_outcome']:
        if decision['response_outcome']!=outcome or decision['response_request_id']!=request_id:raise ValueError('IDEMPOTENCY_CONFLICT')
        return decision
    if not decision['question_turn_id']:raise ValueError('M7_QUESTION_NOT_DELIVERED')
    source=_source(connection,str(decision['c54_revision_id']),lock=True)
    if source['status']!='scenario_ended':raise ValueError('M7_CLARIFICATION_STATE_CHANGED')
    connection.execute("INSERT INTO m7_clarification_responses(decision_id,outcome,request_id) VALUES(%s,%s,%s)",(decision['id'],outcome,request_id))
    return repo.read(connection,decision_id)

def read(connection,decision_id:str):
    return repo.read(connection,decision_id)

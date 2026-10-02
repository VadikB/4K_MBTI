from __future__ import annotations
from datetime import datetime,timedelta,timezone
import json
from uuid import UUID,uuid4

from Api.m5_case_runtime import checksum
from Api import m5_scenario_runtime
from Api.m5_cycle_runtime import read_cycle
from Api import m7_completion_repository as repo

TERMINAL_CYCLE={'collection_closed','calculation_pending','calculated','failed'}

def _cycle(connection,cycle_id,lock=True):
    row=connection.execute('SELECT * FROM m5_cycles WHERE cycle_id=%s'+(' FOR UPDATE' if lock else ''),(UUID(str(cycle_id)),)).fetchone()
    if not row:raise ValueError('M7_CYCLE_NOT_FOUND')
    return dict(row)

def _effective_limit(connection,cycle):
    state=read_cycle(connection,str(cycle['cycle_id']))
    now=datetime.now(timezone.utc);deadline=state['calendar_deadline']
    if deadline and now>=deadline:return 'calendar_deadline',deadline
    if state['remaining_seconds']<=0:
        remaining=int(cycle['time_budget_seconds'])
        rows=connection.execute("SELECT started_at,COALESCE(ended_at,NOW()) AS ended_at FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND interval_type='collecting' ORDER BY started_at,id",(cycle['id'],)).fetchall()
        for row in rows:
            seconds=max(0,int((row['ended_at']-row['started_at']).total_seconds()))
            if seconds>=remaining:return 'time_budget',row['started_at']+timedelta(seconds=remaining)
            remaining-=seconds
        return 'time_budget',now
    return None,None

def _finalize_as(connection,row,reason,key):
    status=row['status'];as_id=str(row['assessment_situation_id'])
    if status in {'closed','rejected'}:return None
    if status in {'prepared','admitted'}:
        m5_scenario_runtime.append_event(connection,as_db_id=row['id'],event_type='assessment_situation_not_presented',
            event_key=f'completion-not-presented:{key}',cause={'reason':reason,'from':status},payload={'status':'closed'})
        connection.execute("UPDATE m5_assessment_situations SET status='closed',closed_at=NOW() WHERE id=%s",(row['id'],))
        m5_scenario_runtime.append_event(connection,as_db_id=row['id'],event_type='assessment_situation_closed',
            event_key=f'completion-close:{key}',cause={'reason':reason,'from':status},payload={'status':'closed','presented':False})
        return None
    if status in {'active','paused'}:
        m5_scenario_runtime.transition(connection,assessment_situation_id=as_id,action='terminate',reason=reason,request_id=f'{key}:terminate')
        status='terminated'
    if status in {'terminated','scenario_ended'}:
        m5_scenario_runtime.transition(connection,assessment_situation_id=as_id,action='close',reason=reason,request_id=f'{key}:close')
    handoff=m5_scenario_runtime.build_c45(connection,as_id,mode='final')
    connection.execute("""INSERT INTO m7_finalization_outbox(assessment_situation_db_id,handoff_id,status)
        VALUES(%s,%s,'pending') ON CONFLICT(assessment_situation_db_id) DO NOTHING""",(row['id'],handoff['handoff_id']))
    return handoff

def _composition(connection,cycle):
    sessions=[dict(x) for x in connection.execute('SELECT * FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal',(cycle['id'],)).fetchall()]
    situations=[dict(x) for x in connection.execute("""SELECT s.id,s.assessment_situation_id,s.session_db_id,s.status,s.snapshot_json,s.scenario_ended_at,s.closed_at,
        h.handoff_id,h.envelope_checksum,h.boundary_sequence FROM m5_assessment_situations s
        LEFT JOIN LATERAL(SELECT * FROM m5_c45_handoffs x WHERE x.assessment_situation_db_id=s.id AND x.mode='final' ORDER BY x.created_at DESC LIMIT 1) h ON TRUE
        WHERE s.cycle_db_id=%s ORDER BY s.id""",(cycle['id'],)).fetchall()]
    identity={'cycle_id':str(cycle['cycle_id']),'target_set_checksum':cycle['target_set_checksum'],
        'sessions':[{'session_id':str(x['session_id']),'ordinal':x['ordinal']} for x in sessions],
        'situations':[{'assessment_situation_id':str(x['assessment_situation_id']),'session_db_id':x['session_db_id'],
            'handoff_id':str(x['handoff_id']) if x['handoff_id'] else None,'handoff_checksum':x['envelope_checksum']} for x in situations]}
    return sessions,situations,identity,checksum(identity)

def _create_c46(connection,cycle):
    sessions,situations,identity,composition_checksum=_composition(connection,cycle)
    intervals=[dict(x) for x in connection.execute('SELECT * FROM m5_cycle_time_intervals WHERE cycle_db_id=%s ORDER BY started_at,id',(cycle['id'],)).fetchall()]
    plan=connection.execute("""SELECT p.id,p.full_target_set_json,p.planned_target_set_json,p.observation_requirements_json,
        r.id AS revision_id,r.content_json FROM m7_cycle_plans p
        JOIN LATERAL(SELECT * FROM m7_plan_revisions WHERE plan_id=p.id ORDER BY revision_no DESC LIMIT 1) r ON TRUE
        WHERE p.cycle_db_id=%s""",(cycle['id'],)).fetchone()
    state=read_cycle(connection,str(cycle['cycle_id']))
    payload={'schema_version':1,'contract':'C-46','message_version':'1.0','owner':'PM-04','consumer':'PM-06',
        'cycle':{'id':str(cycle['cycle_id']),'owner_user_id':cycle['owner_user_id'],'profile_ref':cycle['profile_ref_json'],
            'selected_role_ref':cycle['selected_role_ref_json'],'usage_scope':cycle['usage_scope']},
        'goal':(plan['content_json']['goal'] if plan else None),'full_target_set':(plan['full_target_set_json'] if plan else cycle['target_set_json']),
        'plan':({'id':str(plan['id']),'revision_id':str(plan['revision_id']),'planned_target_set':plan['planned_target_set_json'],
            'observation_requirements':plan['observation_requirements_json'],'untraversed_route':plan['content_json'].get('route',[]),'requirements_state':'pending'} if plan else None),
        'composition':identity,'composition_checksum':composition_checksum,
        'sessions':[{'session_id':str(x['session_id']),'ordinal':x['ordinal'],'status':x['status'],'started_at':x['started_at'].isoformat() if x['started_at'] else None,
            'ended_at':x['ended_at'].isoformat() if x['ended_at'] else None,'close_reason':x['close_reason']} for x in sessions],
        'assessment_situations':[{'assessment_situation_id':str(x['assessment_situation_id']),'session_db_id':x['session_db_id'],'status':x['status'],
            'case_ref':x['snapshot_json']['case_ref'],'handoff_id':str(x['handoff_id']) if x['handoff_id'] else None,
            'handoff_checksum':x['envelope_checksum'],'boundary_sequence':x['boundary_sequence']} for x in situations],
        'time':{'budget_seconds':cycle['time_budget_seconds'],'calendar_window_seconds':cycle['calendar_window_seconds'],
            'parameter_sources':cycle['parameter_sources_json'],'started_at':cycle['started_at'].isoformat() if cycle['started_at'] else None,
            'deadline':state['calendar_deadline'].isoformat() if state['calendar_deadline'] else None,'consumed_seconds':state['consumed_seconds'],
            'intervals':[{'session_db_id':x['session_db_id'],'type':x['interval_type'],'started_at':x['started_at'].isoformat(),
                'ended_at':x['ended_at'].isoformat() if x['ended_at'] else None,'reason':x['reason']} for x in intervals]},
        'collection':{'status':cycle['status'],'closed_at':cycle['collection_closed_at'].isoformat() if cycle['collection_closed_at'] else None,
            'reason':cycle['close_reason']},'calculation':{'status':'pending','revision_ref':None},
        'coverage':{'opportunities':None,'indicator_assessments':None,'admissible_contributions':None,'components_with_score':None,'complete_components':None}}
    rid=uuid4();digest=checksum(payload)
    connection.execute("""INSERT INTO m7_c46_revisions(id,cycle_db_id,revision_no,status,composition_checksum,payload_json,payload_checksum)
        VALUES(%s,%s,1,'collection_snapshot',%s,%s::jsonb,%s) ON CONFLICT(cycle_db_id,revision_no) DO NOTHING""",
        (rid,cycle['id'],composition_checksum,json.dumps(payload,ensure_ascii=False),digest))
    return repo.read_c46(connection,cycle['id'])

def complete(connection,*,cycle_id,key,action,reason,initiated_by):
    cycle=_cycle(connection,cycle_id);request={'action':action,'reason':reason};request_checksum=checksum(request)
    prior=repo.existing(connection,cycle['id'],key,request_checksum)
    if prior:return prior
    if cycle['status'] in TERMINAL_CYCLE:raise ValueError('M7_COLLECTION_CLOSED')
    if action not in {'complete','final_refusal','interrupt_for_continuation','time_limit'}:raise ValueError('M7_COMPLETION_ACTION_INVALID')
    effective_at=datetime.now(timezone.utc);limit_kind=None
    if action=='time_limit':
        limit_kind,effective_at=_effective_limit(connection,cycle)
        if not limit_kind:raise ValueError('M7_TIME_LIMIT_NOT_REACHED')
        reason=limit_kind
    sessions=connection.execute("SELECT * FROM m5_cycle_sessions WHERE cycle_db_id=%s AND status IN('prepared','active','paused','interrupted') ORDER BY ordinal FOR UPDATE",(cycle['id'],)).fetchall()
    current=dict(sessions[-1]) if sessions else None
    before={'cycle':cycle['status'],'session':current['status'] if current else None}
    situations=connection.execute("SELECT * FROM m5_assessment_situations WHERE cycle_db_id=%s AND status NOT IN('closed','rejected') ORDER BY id FOR UPDATE",(cycle['id'],)).fetchall()
    handoffs=[]
    for item in situations:
        handoff=_finalize_as(connection,dict(item),reason,key)
        if handoff:handoffs.append(str(handoff['handoff_id']))
    connection.execute('UPDATE m5_cycle_time_intervals SET ended_at=NOW() WHERE cycle_db_id=%s AND ended_at IS NULL',(cycle['id'],))
    if action=='interrupt_for_continuation':
        if not current or current['status'] not in {'active','paused'}:raise ValueError('M7_CONTINUATION_NOT_INTERRUPTED')
        connection.execute("UPDATE m5_cycle_sessions SET status='interrupted',ended_at=NOW(),close_reason=%s,updated_at=NOW() WHERE id=%s",(reason,current['id']))
        connection.execute("UPDATE m5_cycles SET status='interrupted',close_reason=%s,updated_at=NOW() WHERE id=%s",(reason,cycle['id']))
        snapshot={'cycle_id':str(cycle['cycle_id']),'session_id':str(current['session_id']),'profile_ref':cycle['profile_ref_json'],
            'target_set_checksum':cycle['target_set_checksum'],'intent':'continue','remaining_at_interrupt':read_cycle(connection,str(cycle['cycle_id']))['remaining_seconds']}
        intent_id=uuid4();connection.execute("""INSERT INTO m7_continuation_intents(id,cycle_db_id,interrupted_session_db_id,status,snapshot_json,snapshot_checksum,created_by)
            VALUES(%s,%s,%s,'pending',%s::jsonb,%s,%s)""",(intent_id,cycle['id'],current['id'],json.dumps(snapshot),checksum(snapshot),initiated_by))
        c46=None;after={'cycle':'interrupted','session':'interrupted'}
    else:
        if current:connection.execute("UPDATE m5_cycle_sessions SET status='completed',ended_at=COALESCE(ended_at,NOW()),close_reason=%s,updated_at=NOW() WHERE id=%s",(reason,current['id']))
        connection.execute("UPDATE m5_cycles SET status='collection_closed',collection_closed_at=NOW(),close_reason=%s,updated_at=NOW() WHERE id=%s",(reason,cycle['id']))
        cycle=_cycle(connection,cycle_id,lock=False);c46=_create_c46(connection,cycle);intent_id=None;after={'cycle':'collection_closed','session':'completed' if current else None}
    event_id=uuid4();boundary={'handoff_ids':handoffs,'limit_kind':limit_kind}
    connection.execute("""INSERT INTO m7_transition_events(id,cycle_db_id,session_db_id,event_type,reason,initiated_by,before_json,after_json,boundary_json,effective_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)""",(event_id,cycle['id'],current['id'] if current else None,action,reason,initiated_by,json.dumps(before),json.dumps(after),json.dumps(boundary),effective_at))
    result={'cycle_id':str(cycle['cycle_id']),'event_id':str(event_id),'action':action,'reason':reason,'states':after,
        'final_handoff_ids':handoffs,'continuation_intent_id':str(intent_id) if intent_id else None,'c46_revision_id':str(c46['id']) if c46 else None,
        'processing_status':'pending' if handoffs else 'not_required'}
    connection.execute('INSERT INTO m7_completion_commands VALUES(%s,%s,%s,%s::jsonb,NOW())',(cycle['id'],key,request_checksum,json.dumps(result)))
    return result

def create_additional_session(connection,*,cycle_id,intent_id,key,created_by):
    from Api.m5_cycle_runtime import create_session
    cycle=_cycle(connection,cycle_id);request_checksum=checksum({'intent_id':intent_id})
    prior=connection.execute('SELECT * FROM m7_additional_session_keys WHERE cycle_db_id=%s AND key=%s',(cycle['id'],key)).fetchone()
    if prior:
        if prior['request_checksum']!=request_checksum:raise ValueError('IDEMPOTENCY_CONFLICT')
        return dict(connection.execute('SELECT * FROM m5_cycle_sessions WHERE id=%s',(prior['session_db_id'],)).fetchone())
    intent=connection.execute("SELECT * FROM m7_continuation_intents WHERE id=%s AND cycle_db_id=%s FOR UPDATE",(UUID(intent_id),cycle['id'])).fetchone()
    if not intent or intent['status']!='pending':raise ValueError('M7_ADDITIONAL_SESSION_NOT_ALLOWED')
    if checksum(intent['snapshot_json'])!=intent['snapshot_checksum'] or intent['snapshot_json']['profile_ref']!=cycle['profile_ref_json'] or intent['snapshot_json']['target_set_checksum']!=cycle['target_set_checksum']:raise ValueError('COMPOSITION_MISMATCH')
    if cycle['status']!='interrupted' or not _effective_limit(connection,cycle)==(None,None):raise ValueError('M7_ADDITIONAL_SESSION_NOT_ALLOWED')
    session=create_session(connection,cycle_id=str(cycle['cycle_id']),created_by=created_by)
    connection.execute("UPDATE m7_continuation_intents SET status='consumed',consumed_at=NOW() WHERE id=%s",(intent['id'],))
    connection.execute('INSERT INTO m7_additional_session_keys VALUES(%s,%s,%s,%s)',(cycle['id'],key,request_checksum,session['id']))
    return session

def control(connection,*,cycle_id,key,action,reason,initiated_by):
    from Api.m5_cycle_runtime import transition_session
    cycle=_cycle(connection,cycle_id);request_checksum=checksum({'action':action,'reason':reason})
    prior=repo.existing(connection,cycle['id'],key,request_checksum)
    if prior:return prior
    if cycle['status'] in TERMINAL_CYCLE:raise ValueError('M7_COLLECTION_CLOSED')
    if action=='resume' and _effective_limit(connection,cycle)!=(None,None):
        return complete(connection,cycle_id=cycle_id,key=f'{key}:expiry',action='time_limit',reason='resume_after_limit',initiated_by=initiated_by)
    session=connection.execute('SELECT * FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1 FOR UPDATE',(cycle['id'],)).fetchone()
    if not session:raise ValueError('M7_SESSION_NOT_FOUND')
    open_as=connection.execute("SELECT * FROM m5_assessment_situations WHERE session_db_id=%s AND status IN('active','paused') ORDER BY id DESC LIMIT 1 FOR UPDATE",(session['id'],)).fetchone()
    if open_as:
        m5_scenario_runtime.transition(connection,assessment_situation_id=str(open_as['assessment_situation_id']),action=action,reason=reason,request_id=f'{key}:{action}')
    saved=transition_session(connection,session_id=str(session['session_id']),action=action,reason=reason)
    result={'cycle_id':cycle_id,'session_id':str(session['session_id']),'action':action,'cycle_status':'paused' if action=='pause' else 'active',
        'session_status':saved['status'],'assessment_situation_id':str(open_as['assessment_situation_id']) if open_as else None}
    connection.execute('INSERT INTO m7_completion_commands VALUES(%s,%s,%s,%s::jsonb,NOW())',(cycle['id'],key,request_checksum,json.dumps(result)))
    return result

def read_status(connection,cycle_id):
    cycle=_cycle(connection,cycle_id,lock=False);state=read_cycle(connection,cycle_id)
    latest=connection.execute('SELECT status FROM m7_c46_revisions WHERE cycle_db_id=%s ORDER BY revision_no DESC LIMIT 1',(cycle['id'],)).fetchone()
    return {'cycle_id':cycle_id,'collection_status':cycle['status'],'processing_status':('processing' if cycle['status']=='collection_closed' else cycle['status']),
        'remaining_seconds':state['remaining_seconds'],'calendar_deadline':state['calendar_deadline'],'close_reason':cycle['close_reason'],
        'c46_status':latest['status'] if latest else None,'can_continue':cycle['status'] in {'active','paused','interrupted'}}

def read_c46(connection,cycle_id):
    cycle=_cycle(connection,cycle_id,lock=False);return repo.read_c46(connection,cycle['id'])

def reconcile_c46(connection,*,cycle_id,expected_composition_checksum,calculation_ref,coverage,skill_outcomes):
    cycle=_cycle(connection,cycle_id);current=repo.read_c46(connection,cycle['id'])
    _,_,identity,actual=_composition(connection,cycle)
    if expected_composition_checksum!=current['composition_checksum'] or actual!=current['composition_checksum']:
        raise ValueError('COMPOSITION_MISMATCH')
    if str(calculation_ref.get('cycle_id'))!=str(cycle['cycle_id']) or calculation_ref.get('composition_checksum')!=actual:
        raise ValueError('COMPOSITION_MISMATCH')
    required_coverage={'opportunities','indicator_assessments','admissible_contributions','components_with_score','complete_components'}
    if set(coverage)!=required_coverage:raise ValueError('C46_COVERAGE_CONTRACT_INVALID')
    allowed_outcomes={'full_score','partial_score','result_without_score','no_result'}
    if any(x.get('outcome') not in allowed_outcomes for x in skill_outcomes):raise ValueError('C46_SKILL_OUTCOME_INVALID')
    payload=dict(current['payload_json']);payload['composition']=identity;payload['calculation']={'status':'completed','revision_ref':calculation_ref}
    payload['coverage']=coverage;payload['skill_outcomes']=skill_outcomes
    revision=current['revision_no']+1;rid=uuid4()
    connection.execute("""INSERT INTO m7_c46_revisions(id,cycle_db_id,revision_no,status,composition_checksum,payload_json,payload_checksum,calculation_ref_json)
        VALUES(%s,%s,%s,'reconciled',%s,%s::jsonb,%s,%s::jsonb)""",(rid,cycle['id'],revision,actual,json.dumps(payload,ensure_ascii=False),checksum(payload),json.dumps(calculation_ref,ensure_ascii=False)))
    connection.execute("UPDATE m5_cycles SET status='calculated',updated_at=NOW() WHERE id=%s AND status IN('collection_closed','calculation_pending')",(cycle['id'],))
    return repo.read_c46(connection,cycle['id'])

def expire_due_cycles(connection,*,initiated_by=None):
    rows=connection.execute("SELECT cycle_id FROM m5_cycles WHERE status IN('active','paused','interrupted') ORDER BY id FOR UPDATE SKIP LOCKED").fetchall();results=[]
    for row in rows:
        try:
            with connection.transaction():
                cycle=_cycle(connection,str(row['cycle_id']))
                if _effective_limit(connection,cycle)!=(None,None):
                    results.append(complete(connection,cycle_id=str(row['cycle_id']),key='automatic-expiry',action='time_limit',reason='automatic',initiated_by=initiated_by or cycle['created_by']))
        except ValueError:
            continue
    return results

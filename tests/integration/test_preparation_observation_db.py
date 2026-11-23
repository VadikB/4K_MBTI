"""Narrow persistence/orchestration checks; no full synthetic Cycle or real providers."""
from contextlib import contextmanager
from uuid import uuid4
import json
import psycopg
from psycopg.rows import dict_row
import pytest
from Api import preparation_observation as observation, m10_product_flow
from scripts.preparation_diagnostics import lookup
from tests.integration.test_m10_product_path_db import product_db  # noqa: F401
from tests.integration.test_m10_product_path_db import test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases as first_preparation

pytestmark = pytest.mark.integration

@pytest.fixture
def observation_db(test_database_url):
    schema='preparation_pytest_'+uuid4().hex
    with psycopg.connect(test_database_url) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    @contextmanager
    def factory():
        with psycopg.connect(test_database_url,row_factory=dict_row) as c:
            c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            c.commit()
            yield c
    try:
        with factory() as c:
            observation.ensure_schema(c)
            c.execute('''CREATE TABLE product_cycle_preparation_operations(operation_id TEXT,status TEXT,attempt_token UUID,
                attempts INT,locked_at TIMESTAMPTZ,error_code TEXT,request_json JSONB,result_json JSONB,
                created_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)''')
            c.execute('CREATE TABLE m5_cycles(id INT,cycle_id UUID)')
            c.execute('CREATE TABLE m10_pipeline_runs(cycle_db_id INT,status TEXT)')
            c.execute('CREATE TABLE m10_report_claims(cycle_db_id INT,token UUID,lease_until TIMESTAMPTZ)')
        yield factory
    finally:
        with psycopg.connect(test_database_url) as c:
            c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_committed_stages_attempt_fence_read_only_lookup_and_once_only_delay(observation_db,caplog):
    factory=observation_db
    token=uuid4()
    with factory() as c:
        c.execute("INSERT INTO product_cycle_preparation_operations (operation_id,status,attempt_token,attempts,locked_at,error_code,request_json,result_json) VALUES ('operation','running',%s,1,NOW(),NULL,'{}','{}')",(token,))
    first=observation.begin('cycle','operation',token,'assessment','plan',factory=factory)
    with factory() as c:
        from datetime import datetime,timezone
        stored=c.execute("SELECT created_at FROM product_cycle_preparation_operations").fetchone()
        public=observation.attach(c,{'operation_id':'operation','status':'running','created_at':stored['created_at']})['preparation']
        assert abs((datetime.now(timezone.utc)-datetime.fromisoformat(public['started_at'])).total_seconds())<30
    observation.record(first,'checking',heartbeat=True)
    with factory() as c:
        c.execute("UPDATE preparation_observations SET stage_started_at=NOW()-INTERVAL '27 minutes',started_at=NOW()-INTERVAL '30 minutes'")
    observation.record(first,heartbeat=True)
    observation.record(first,heartbeat=True)
    with factory() as c:
        c.execute('SET TRANSACTION READ ONLY')
        observed=observation.read(c,'cycle','operation')
        result=observation.project({'operation_id':'operation','status':'running'},observed)
        assert result['delayed'] and result['freshness']=='confirmed'
        assert observed['delay_events']==['checking']
        diagnostic=lookup(c,result['reference'])
        assert diagnostic[0]['operation']['operation_id']=='operation'
        assert 'test_candidate' in diagnostic[0]['owner']
        assert observation.read(c,'cycle','operation')['stage_started_at']==observed['stage_started_at']
    assert len([r for r in caplog.records if 'preparation_delay' in r.message])==1
    successor=uuid4()
    with factory() as c:
        c.execute("UPDATE product_cycle_preparation_operations SET attempt_token=%s",(successor,))
    current=observation.begin('cycle','operation',successor,'assessment','first',factory=factory)
    observation.record(first,'plan',heartbeat=True)
    observation.record(current,'checking',heartbeat=True)
    with factory() as c:
        rows=c.execute('SELECT * FROM preparation_observations ORDER BY id').fetchall()
        assert len(rows)==2 and rows[0]['stage']=='checking' and rows[1]['stage']=='checking'
        assert rows[0]['history_json']!=rows[1]['history_json']
    with pytest.raises(RuntimeError,match='ATTEMPT_STALE'):
        observation.begin('cycle','operation',token,'assessment','plan',factory=factory)


def test_real_sync_next_entry_exposes_intermediate_stage_before_provider_returns(observation_db,monkeypatch):
    factory=observation_db
    monkeypatch.setattr(m10_product_flow,'_policy',lambda *_a,**_k:{})
    def provider(connection,**kwargs):
        with factory() as other:
            saved=observation.read(other,'sync','sync-next')
            assert saved['stage']=='next' and saved['status']=='running'
            assert observation.sync_owned(other,'sync-next',100) is None
            assert observation.sync_owned(other,'sync-next',99)['preparation']['stage_label']=='Готовим следующую ситуацию'
        return {'status':'SELECTED'}
    monkeypatch.setattr(m10_product_flow.m7_cycle_planner,'choose_next',provider)
    monkeypatch.setattr(m10_product_flow.m7_cycle_planner,'read_plan',lambda *_a:{'cycle_id':'saved-cycle'})
    with observation.synchronous('sync-next','next',{'user_id':99,'cycle_id':'saved-cycle'},factory=factory):
        with factory() as c:
            m10_product_flow._prepare_next(c,plan={'cycle_id':'saved-cycle','revision_id':'saved-revision'},user_id=99,key='key')
    with factory() as c:
        assert observation.read(c,'sync','sync-next')['status']=='completed'


def test_real_first_worker_records_material_and_checking_before_completion(product_db,monkeypatch,tmp_path):
    stages=[]
    original=observation.record
    def capture(observer,stage=None,**kwargs):
        result=original(observer,stage,**kwargs)
        if stage and observer:
            with product_db() as c:
                observed=observation.read(c,observer[0],observer[1])
                assert observed['stage']==stage
                if observer[0]=='cycle':
                    assert c.execute('SELECT status FROM product_cycle_preparation_operations WHERE operation_id=%s',(observer[1],)).fetchone()['status']=='running'
            stages.append(stage)
        return result
    monkeypatch.setattr(observation,'record',capture)
    first_preparation(product_db,monkeypatch,tmp_path,True,False,None,None,first_case_only=True)
    assert 'first' in stages and 'checking' in stages
    assert stages.index('first')<stages.index('checking')


def test_report_entry_stages_and_ready_with_no_material(product_db,monkeypatch):
    from tests.integration.test_m10_product_path_db import test_s10_d_closed_cycle_without_presented_material_has_no_result_report as report_only
    from Api import m10_orchestration
    seen=[]
    def instrument(module,name,expected):
        original=getattr(module,name)
        def invoke(*args,**kwargs):
            with product_db() as c:
                stage=c.execute("SELECT stage FROM preparation_observations WHERE source='report' ORDER BY id DESC LIMIT 1").fetchone()
                assert stage['stage']==expected
                seen.append(expected)
            return original(*args,**kwargs)
        monkeypatch.setattr(module,name,invoke)
    instrument(m10_orchestration.m6_cycle_aggregation_repository,'create_substantive_detached','results')
    instrument(m10_orchestration.m8_results,'create_report_detached','report')
    report_only(product_db)
    assert seen==['results','report']
    with product_db() as c:
        cycle=c.execute('SELECT cycle_id FROM m5_cycles').fetchone()['cycle_id']
        public=observation.report_status(c,str(cycle))
        assert public['status']=='ready' and public['stage_label']=='Отчёт готов' and not public['delayed']


def test_report_clock_does_not_start_with_an_open_cycle_interim_marker(product_db):
    # Persisted upstream pipeline marker is a synthetic fixture. No Dialogue,
    # material interpretation or provider result is asserted by this boundary test.
    from tests.integration.test_m10_product_path_db import create_plan, complete
    from Api import m10_orchestration
    with product_db() as c:
        plan=create_plan(c,personalized_profile_id=product_db.profile_id,selected_skills=['K1','K2','K3','K4'],
            created_by=99,key='progress-clock-plan',usage_scope='assessment')
        cycle_id=str(plan['cycle_id'])
        cycle_db_id=c.execute('SELECT id FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone()['id']
        m10_orchestration._set_state(c,cycle_db_id,status='processing',stage='evidence_queued')
        assert observation.read(c,'report',cycle_id) is None
        c.commit()
        complete(c,cycle_id=cycle_id,key='progress-clock-close',action='complete',reason='no_presented_material',initiated_by=99)
        closed_at=c.execute('SELECT collection_closed_at FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone()['collection_closed_at']
        m10_orchestration._observe_report_queue(c)
        observed=observation.read(c,'report',cycle_id)
        assert observed['stage']=='answers'
        assert observed['started_at']==observed['stage_started_at']==closed_at


def test_public_numbers_resolve_distinct_real_operations_attempts_and_owners(observation_db):
    """Use generated operation IDs and real public projection, never a copied fixture code."""
    factory = observation_db
    references = set()
    for kind, stage in [('assessment', 'plan'), ('next', 'checking')]:
        operation_id = 'review-' + uuid4().hex
        attempts = [uuid4(), uuid4()]
        with factory() as c:
            c.execute('''INSERT INTO product_cycle_preparation_operations
                (operation_id,status,attempt_token,attempts,locked_at,request_json,result_json)
                VALUES (%s,'running',%s,1,NOW(),%s,'{}')''',
                (operation_id, attempts[0], json.dumps({'assignment_id': 91, 'cycle_id': str(uuid4())})))
        for index, token in enumerate(attempts):
            with factory() as c:
                c.execute('UPDATE product_cycle_preparation_operations SET attempt_token=%s,attempts=%s WHERE operation_id=%s',
                          (token, index + 1, operation_id))
            observer = observation.begin('cycle', operation_id, token, kind, stage, factory=factory)
            observation.record(observer, stage, heartbeat=True)
        with factory() as c:
            c.execute('SET TRANSACTION READ ONLY')
            public = observation.project({'operation_id': operation_id, 'status': 'running'},
                                         observation.read(c, 'cycle', operation_id))
            found = lookup(c, public['reference'])
            assert len(found) == 2
            assert {item['operation_id'] for item in found} == {operation_id}
            assert {item['attempt_token'] for item in found} == {str(token) for token in attempts}
            assert {item['owner'] for item in found} == {observation.OWNERS[stage]}
            assert all(item['operation']['assignment_id'] == '91' for item in found)
            assert public['reference'] not in references
            references.add(public['reference'])

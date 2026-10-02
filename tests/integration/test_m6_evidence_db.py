from contextlib import contextmanager
from uuid import UUID, uuid4
import json
from pathlib import Path
import subprocess
import sys
import psycopg
from psycopg.rows import dict_row
import pytest
from Api import m6_repository as repo
from Api.m6_package import load_mechanism
from Api.m6_input_resolver import resolve
from Api.m6_worker import run_request
from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import import_package, prepare_assessment_situation
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_scenario_runtime import start, transition, build_c45
from scripts.build_m5_case_package import OUTPUT

pytestmark=pytest.mark.integration

GC_PACKAGE = Path(__file__).resolve().parents[1] / 'fixtures/m6_gc/v1'


@pytest.mark.parametrize('name', [
    'independent', 'character', 'before_disclosure', 'composite', 'insufficient',
    'nonperformance', 'contradiction', 'paraphrase', 'retain',
])
def test_task02_candidate_chain_database_readback(database, name):
    """Сохранение draft output, не правильность разбора и не прогон GC."""
    from Api.m5_case_runtime import checksum
    fixture = json.loads((GC_PACKAGE / 'candidates' / (name + '.json')).read_text())
    factory, handoff_id = database
    with factory() as c:
        saved = c.execute('SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s', (handoff_id,)).fetchone()
        envelope = saved['envelope_json']
        source = fixture['resolver_input']['handoff']['envelope_json']
        # Rebind only the synthetic recording to the AS created in this isolated DB.
        # Existing AS/Cycle/Session/version references stay those of the saved snapshot.
        for key in ('dialogue', 'presented_materials', 'boundary', 'boundary_sequence'):
            envelope[key] = source[key]
        c.execute('''UPDATE m5_c45_handoffs SET envelope_json=%s::jsonb,
            envelope_checksum=%s,boundary_sequence=%s WHERE handoff_id=%s''',
            (json.dumps(envelope), checksum(envelope), envelope['boundary_sequence'], handoff_id))
        request = enqueue(c, handoff_id, 'candidate-' + name)
        c.commit()
    class RecordedDraft:
        enabled = True
        def chat(self, messages, **kwargs):
            material = json.loads(messages[1]['content'])
            assert material['turns'] == fixture['material']['turns']
            assert material['materials'] == fixture['material']['materials']
            assert material['indicator_targets'] == fixture['material']['indicator_targets']
            return json.dumps(fixture['draft_analysis'], ensure_ascii=False)
    run_request(request['id'], connection_factory=factory, gateway=RecordedDraft())
    run_request(request['id'], connection_factory=factory, gateway=RecordedDraft())
    with factory() as c:
        status = repo.read_request(c, request['id'])
        assert status['status'] == 'succeeded'
        result = repo.read_analysis(c, status['analysis_revision_id'])
        assert result['analysis'] == fixture['draft_analysis']
        assert result['material'] == request['input_json']
        assert len(result['bundles']) == 9
        assert c.execute('SELECT count(*) AS n FROM m6_processing_attempts').fetchone()['n'] == 1


def test_timeout_is_failed_attempt_without_assessment_and_can_retry(database):
    factory, handoff_id = database
    with factory() as c:
        request = enqueue(c, handoff_id)
        c.commit()
    class Timeout:
        enabled = True
        def chat(self, *args, **kwargs):
            raise TimeoutError('synthetic timeout; no provider call')
    run_request(request['id'], connection_factory=factory, gateway=Timeout())
    with factory() as c:
        assert repo.read_request(c, request['id'])['status'] == 'failed'
        attempt = c.execute('SELECT status,error_code FROM m6_processing_attempts').fetchone()
        assert attempt == {'status': 'failed', 'error_code': 'TimeoutError'}
        assert c.execute('SELECT count(*) AS n FROM m6_analysis_revisions').fetchone()['n'] == 0
        assert c.execute('SELECT count(*) AS n FROM m6_evidence_bundles').fetchone()['n'] == 0
    class Success:
        enabled = True
        def chat(self, messages, **kwargs):
            return json.dumps(empty_output(json.loads(messages[1]['content'])))
    run_request(request['id'], connection_factory=factory, gateway=Success())
    with factory() as c:
        assert repo.read_request(c, request['id'])['status'] == 'succeeded'
        assert c.execute('SELECT count(*) AS n FROM m6_processing_attempts').fetchone()['n'] == 2


def test_process_exit_after_claim_commit_recovers_once(database, test_database_url):
    factory, handoff_id = database
    with factory() as c:
        request = enqueue(c, handoff_id)
        schema = c.execute('SELECT current_schema() AS name').fetchone()['name']
        c.commit()
    script = '''
import os, sys, psycopg
from psycopg.rows import dict_row
from Api.m6_repository import claim
with psycopg.connect(sys.argv[1], row_factory=dict_row) as c:
    c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(sys.argv[2])))
    job = claim(c, sys.argv[3])
    assert job is not None
    c.commit()
os._exit(73)
'''
    child = subprocess.run([sys.executable, '-c', script, test_database_url, schema, str(request['id'])],
                           cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=20)
    assert child.returncode == 73, child.stderr.decode()
    with factory() as c:
        assert repo.read_request(c, request['id'])['status'] == 'running'
        assert c.execute('SELECT count(*) AS n FROM m6_analysis_revisions').fetchone()['n'] == 0
        # Controlled time boundary; the child really exited, no real lease-duration wait.
        c.execute("UPDATE m6_processing_requests SET lease_expires_at=NOW()-INTERVAL '1 second'")
        c.commit()
    class Success:
        enabled = True
        def chat(self, messages, **kwargs):
            return json.dumps(empty_output(json.loads(messages[1]['content'])))
    run_request(request['id'], connection_factory=factory, gateway=Success())
    run_request(request['id'], connection_factory=factory, gateway=Success())
    with factory() as c:
        assert repo.read_request(c, request['id'])['status'] == 'succeeded'
        attempts = c.execute('SELECT status FROM m6_processing_attempts ORDER BY attempt_no').fetchall()
        assert [a['status'] for a in attempts] == ['expired', 'succeeded']
        assert c.execute('SELECT count(*) AS n FROM m6_analysis_revisions').fetchone()['n'] == 1


@pytest.fixture
def database(test_database_url):
    schema='m6_pytest_'+uuid4().hex
    @contextmanager
    def connect():
        with psycopg.connect(test_database_url,row_factory=dict_row) as c:
            c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            c.commit()
            yield c
    with psycopg.connect(test_database_url) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    try:
        with connect() as c:
            c.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)');c.execute('INSERT INTO users VALUES(99)')
            c.execute('''CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY,status TEXT,
                content_json JSONB,provenance_json JSONB,checksum TEXT)''')
            ensure_m5_runtime_schema(c);repo.ensure_schema(c)
            package=json.loads((OUTPUT/'case-package.json').read_text());case=package['cases'][0]
            import_package(c,package=package,manifest=json.loads((OUTPUT/'manifest.json').read_text()),
                           execution_rules=json.loads((OUTPUT/'execution-rules.json').read_text()))
            c.execute("INSERT INTO assessment_personalized_profiles VALUES(7,'ready',%s::jsonb,'{}',%s)",
                      (json.dumps({'role_profile':{'code':case['base_role']},'email':'synthetic@example.invalid'}),'c'*64))
            cycle,session=create_cycle_session_for_case(c,personalized_profile_id=7,case_id=case['case_id'],
                case_version=case['version'],created_by=99,usage_scope='qa')
            prepared=prepare_assessment_situation(c,assessment_situation_id=str(uuid4()),case_id=case['case_id'],
                case_version=case['version'],personalized_profile_id=7,cycle_db_id=cycle['id'],session_db_id=session['id'],
                substitutions=[],policy=json.loads((OUTPUT/'admission-policy.json').read_text()),usage_scope='qa',qa_authorized_by=99)
            as_id=prepared['assessment_situation_id']
            start(c,as_id)
            c.execute('''INSERT INTO m5_dialogue_turns
                (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
                SELECT id,%s,2,'assessee','assessee','Синтетический ответ','synthetic-turn'
                FROM m5_assessment_situations WHERE assessment_situation_id=%s''',(uuid4(),UUID(as_id)))
            transition(c,assessment_situation_id=as_id,action='scenario_end',reason='synthetic',request_id='end')
            transition(c,assessment_situation_id=as_id,action='close',reason='synthetic',request_id='close')
            handoff=build_c45(c,as_id)
            c.commit()
        yield connect,str(handoff['handoff_id'])
    finally:
        with psycopg.connect(test_database_url) as c:
            c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def empty_output(material):
    return {'schema_version':1,'fragments':[],'signals':[],'evidence':[], 'attribution_notes':[],
        'bundles':[{'indicator_id':x['indicator_id'],'evidence_ids':[], 'opportunity_basis':'synthetic test; not GC',
                    'context_refs':[],'limitations':[],'contradictions':[]} for x in material['indicator_targets']]}


def enqueue(c,h,key='first'):
    aid,material=resolve(c,h)
    assert 'synthetic@example.invalid' not in json.dumps(material)
    return repo.enqueue(c,as_db_id=aid,handoff_id=h,key=key,material=material,
                        mechanism=load_mechanism('m6_evidence/1.0.0'),created_by=99)


def test_real_c45_empty_bundle_readback_and_replay(database):
    factory,h=database
    with factory() as c:
        request=enqueue(c,h);assert enqueue(c,h,'alias')['id']==request['id'];c.commit()
    class Gateway:
        enabled=True
        def chat(self,messages,**kw): return json.dumps(empty_output(json.loads(messages[1]['content'])))
    run_request(request['id'],connection_factory=factory,gateway=Gateway())
    run_request(request['id'],connection_factory=factory,gateway=Gateway())
    with factory() as c:
        status=repo.read_request(c,request['id']);assert status['status']=='succeeded'
        analysis=repo.read_analysis(c,status['analysis_revision_id'])
        assert analysis['analysis']['fragments']==[]
        assert len(analysis['bundles'])==len(request['input_json']['indicator_targets'])
        assert c.execute('SELECT count(*) AS n FROM m6_processing_attempts').fetchone()['n']==1


def test_failure_retry_expired_lease_and_late_attempt(database):
    factory,h=database
    with factory() as c:
        request=enqueue(c,h);c.commit()
    class Broken:
        enabled=True
        def chat(self,*a,**kw): return 'invalid'
    run_request(request['id'],connection_factory=factory,gateway=Broken())
    with factory() as c:
        assert repo.read_request(c,request['id'])['status']=='failed'
        assert c.execute('SELECT count(*) AS n FROM m6_analysis_revisions').fetchone()['n']==0
        old=repo.claim(c,request['id']);assert repo.claim(c,request['id']) is None
        c.execute("UPDATE m6_processing_requests SET lease_expires_at=NOW()-INTERVAL '1 second'");c.commit()
    with factory() as c:
        new=repo.claim(c,request['id']);c.commit()
    with factory() as c:
        assert not repo.finish(c,old,empty_output(old['input_json']),{})
        assert repo.finish(c,new,empty_output(new['input_json']),{})
        c.commit()
    with factory() as c: assert repo.read_request(c,request['id'])['status']=='succeeded'


def test_tamper_and_conflicting_key(database):
    factory,h=database
    with factory() as c:
        request=enqueue(c,h)
        changed=dict(request['input_json']);changed['context']={'base_role':'changed'}
        with pytest.raises(ValueError,match='IDEMPOTENCY_CONFLICT'):
            repo.enqueue(c,as_db_id=request['as_db_id'],handoff_id=h,key='first',material=changed,
                         mechanism=request['mechanism_json'],created_by=99)
        c.execute("UPDATE m5_c45_handoffs SET envelope_checksum='bad'")
        with pytest.raises(ValueError,match='CHECKSUM_MISMATCH'):resolve(c,h)


def test_processing_snapshot_survives_source_change(database,monkeypatch):
    factory,h=database
    with factory() as c:
        request=enqueue(c,h);c.commit()
        c.execute("UPDATE assessment_personalized_profiles SET checksum='changed'")
        c.commit()
    import Api.m6_package as package
    def unavailable(*args, **kwargs):
        raise AssertionError('current source must not be read on replay')
    monkeypatch.setattr(package,'load_mechanism',unavailable)
    import Api.m6_input_resolver as resolver
    monkeypatch.setattr(resolver,'load_criteria',unavailable)
    class Gateway:
        enabled=True
        def chat(self,messages,**kw):return json.dumps(empty_output(json.loads(messages[1]['content'])))
    run_request(request['id'],connection_factory=factory,gateway=Gateway())
    with factory() as c:assert repo.read_request(c,request['id'])['status']=='succeeded'


def test_unknown_schema_and_cross_cycle_rejected(database):
    from Api.m5_case_runtime import checksum
    factory,h=database
    with factory() as c:
        row=c.execute('SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s',(h,)).fetchone()
        original=row['envelope_json']; changed={**original,'schema_version':99}
        c.execute('UPDATE m5_c45_handoffs SET envelope_json=%s::jsonb,envelope_checksum=%s WHERE handoff_id=%s',
                  (json.dumps(changed),checksum(changed),h))
        with pytest.raises(ValueError,match='SCHEMA'):resolve(c,h)
        changed={**original,'cycle_ref':{**original['cycle_ref'],'id':'999'}}
        c.execute('UPDATE m5_c45_handoffs SET envelope_json=%s::jsonb,envelope_checksum=%s WHERE handoff_id=%s',
                  (json.dumps(changed),checksum(changed),h))
        with pytest.raises(ValueError,match='COMPOSITION'):resolve(c,h)


def test_concurrent_claim_and_immutable_revisions(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    factory,h=database
    with factory() as c:request=enqueue(c,h);c.commit()
    barrier=Barrier(2)
    def take():
        with factory() as c:
            barrier.wait(timeout=5)
            job=repo.claim(c,request['id']);c.commit();return job
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=list(pool.map(lambda _:take(),range(2)))
    assert sum(j is not None for j in jobs)==1
    job=next(j for j in jobs if j is not None)
    with factory() as c:repo.finish(c,job,empty_output(job['input_json']),{});c.commit()
    with factory() as c:
        with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
            c.execute("UPDATE m6_analysis_revisions SET output_json='{}'")
        c.rollback()
        with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
            c.execute("UPDATE m6_processing_requests SET input_hash='bad'")
        c.rollback()


def test_new_mechanism_keeps_bundle_identity_and_history(database):
    from copy import deepcopy
    from Api.assessment_configuration import definition_checksum
    factory,h=database
    with factory() as c:
        first=enqueue(c,h);job=repo.claim(c,first['id']);repo.finish(c,job,empty_output(job['input_json']),{})
        mechanism=deepcopy(first['mechanism_json']);mechanism['handler']='synthetic-next-version'
        second=repo.enqueue(c,as_db_id=first['as_db_id'],handoff_id=h,key='next',material=first['input_json'],mechanism=mechanism,created_by=99)
        job2=repo.claim(c,second['id']);repo.finish(c,job2,empty_output(job2['input_json']),{})
        assert c.execute('SELECT count(*) AS n FROM m6_analysis_revisions').fetchone()['n']==2
        assert c.execute('SELECT count(*) AS n FROM m6_evidence_bundles').fetchone()['n']==len(first['input_json']['indicator_targets'])
        assert c.execute('SELECT count(*) AS n FROM m6_bundle_revisions').fetchone()['n']==2*len(first['input_json']['indicator_targets'])


def test_restart_recovery_selects_queued_request(database,monkeypatch):
    import Api.m6_worker as worker
    factory,h=database
    with factory() as c:request=enqueue(c,h);c.commit()
    received=[]
    monkeypatch.setattr(worker,'run_request',lambda rid,**kwargs:received.append(rid))
    assert worker.recover_pending(factory)
    assert received==[request['id']]


def test_real_fragment_readback(database):
    factory,h=database
    with factory() as c:request=enqueue(c,h);c.commit()
    class Gateway:
        enabled=True
        def chat(self,messages,**kw):
            m=json.loads(messages[1]['content']);out=empty_output(m);turn=m['turns'][0];target=m['indicator_targets'][0]
            criterion=next(x for x in m['criteria'] if x['id']==target['indicator_id'])
            out['fragments']=[{'id':'f','turn_id':turn['turn_id'],'start':0,'end':len(turn['content']),'quote':turn['content']}]
            out['signals']=[{'id':'s','fragment_id':'f','observation':'synthetic fixture','form_description':'synthetic','context_refs':[]}]
            out['evidence']=[{'id':'e','indicator_id':target['indicator_id'],'m2_version':target['m2_version'],'type':'Simple',
                'interpretation':'synthetic fixture; not a GC','bs_ids':['s'],'fragment_ids':['f'],
                'attribution':{'function':criterion['function'],'product':criterion['product'],
                    'evidence_pattern':criterion['evidence_pattern'],'boundaries':criterion['boundary']},
                'context_refs':[],'limitations':['synthetic'],'ordered_turn_ids':[turn['turn_id']]}]
            out['bundles'][0]['evidence_ids']=['e']
            return json.dumps(out)
    run_request(request['id'],connection_factory=factory,gateway=Gateway())
    with factory() as c:
        status=repo.read_request(c,request['id']);assert status['status']=='succeeded'
        value=repo.read_analysis(c,status['analysis_revision_id'])
        assert value['analysis']['fragments'][0]['quote']==value['material']['turns'][0]['content']

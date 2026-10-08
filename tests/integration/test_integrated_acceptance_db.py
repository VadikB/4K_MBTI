"""G10.7-09: actual saved QA chain; synthetic numeric outputs, not semantic GC."""
import json
from types import SimpleNamespace
import pytest
from test_m6_evidence_db import database, enqueue, empty_output, _assessment_output
from Api import m6_repository, m6_assessment_repository, m6_cycle_aggregation_repository, m8_results
from Api.m6_worker import run_request
from Api.m6_assessment_worker import run_request as run_assessment
from Api.m6_assessment_package import load_mechanism
from Api.m7_completion import complete, read_c46
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark=pytest.mark.integration


@pytest.mark.parametrize('database',['G107-numeric-v1'],indirect=True)
@pytest.mark.parametrize('mode,levels,expected,score',[
    # M2 K1.3: C06={I12}, C07={I13,I14}; equal component weights (M6).
    # Independent expectation: (1 + (2+3)/2)/2 = 7/4, not flat IA mean 2.
    ('full',['L1','L2','L3'],'full_score',1.75),
    ('zero',['L0','L0','L0'],'full_score',0),
    ('partial',['L1','L2','L3'],'partial_score',1.5),
    ('qualitative',['L1','L2','L3'],'result_without_score',None),
    ('none',['L1','L2','L3'],'no_result',None),
])
def test_four_saved_outcomes_and_ai_independent_read(database,monkeypatch,mode,levels,expected,score):
    factory,handoff=database
    with factory() as c:
        job=enqueue(c,handoff);c.commit()
    class Evidence:
        enabled=True
        def chat(self,messages,**kw):return json.dumps(empty_output(json.loads(messages[1]['content'])))
    run_request(job['id'],connection_factory=factory,gateway=Evidence())
    with factory() as c:
        revision=m6_repository.read_request(c,job['id'])['analysis_revision_id']
        job=m6_assessment_repository.enqueue(c,evidence_revision_id=str(revision),key='G09-ia',
            mechanism=load_mechanism('m6_indicator_assessment/1.0.0'),created_by=99);c.commit()
    class NumericFixture:
        enabled=True
        def chat(self,messages,**kw):
            value=json.loads(messages[1]['content']);output=_assessment_output(value)
            assert [x['indicator_id'] for x in output['targets']]==['K1.I12','K1.I13','K1.I14']
            for target,level,criterion in zip(output['targets'],levels,value['material']['criteria']):
                target['outcome']=level;target['descriptor_basis']=criterion['levels'][level]
                if level=='L0':
                    target['refs']=[{'kind':'turn','id':value['material']['turns'][0]['turn_id'],'meaning':'synthetic nonperformance boundary'}]
            return json.dumps(output,ensure_ascii=False)
    run_assessment(job['id'],connection_factory=factory,gateway=NumericFixture())
    with factory() as c:
        assert m6_assessment_repository.read_request(c,job['id'])['status']=='succeeded'
        cycle=str(c.execute('SELECT cycle_id FROM m5_cycles').fetchone()['cycle_id'])
        complete(c,cycle_id=cycle,key='G09-close',action='complete',reason='synthetic',initiated_by=99)
        rows=c.execute('''SELECT i.indicator_id,r.id FROM m6_indicator_assessment_revisions r
            JOIN m6_indicator_assessments i ON i.id=r.indicator_assessment_id ORDER BY i.indicator_id''').fetchall()
        decisions=[{'indicator_id':row['indicator_id'],'included_revision_ids':[str(row['id'])],
            'numeric_admissible':mode not in ('none','qualitative') and not(mode=='partial' and n==2),
            'interpretation_admissible':mode!='none','reason_code':'SYNTHETIC_NUMERIC_TRANSFER',
            'rationale':'QA arithmetic fixture only; no semantic admission assertion','conditions_refs':['G09-fixture']}
            for n,row in enumerate(rows)]
        args=dict(cycle_id=cycle,key='G09-calculation',expected_composition_checksum=read_c46(c,cycle)['composition_checksum'],
            admission_mechanism_version='synthetic-numeric/1',decisions=decisions,created_by=99)
        calculated=m6_cycle_aggregation_repository.create(c,**args)
        assert m6_cycle_aggregation_repository.create(c,**args)['id']==calculated['id']
        skill=next(s for s in calculated['c56']['skill_outcomes'] if s['skill_id']=='K1.3')
        assert skill['outcome']==expected
        assert (skill['score']['value'] if skill.get('score') is not None else None)==score
        assert calculated['c56']['coverage']['full_m2']['admissible_contributions']['denominator']==3
        result=m8_results.create_results(c,cycle_id=cycle,calculation_id=calculated['id'],key='G09-results',target_profile=None,created_by=99)
        report=m8_results.create_report(c,results_revision_id=result['revision_id'],audience='assessee',key='G09-report',target_profile=None,created_by=99)
        projected=next(s for s in report['c67']['skills'] if s['skill_id']=='K1.3')
        assert projected['outcome']==expected
        assert 'skill_level' not in projected
        c.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN)')
        c.execute('CREATE TABLE organization_memberships(user_id BIGINT,organization_id BIGINT)')
        c.execute('INSERT INTO organizations VALUES(1,TRUE)');c.execute('INSERT INTO organization_memberships VALUES(99,1)')
        c.execute("UPDATE m5_cycles SET organization_id=1,usage_scope='assessment'")
        c.commit()
    import Api.routes as routes
    import Api.m6_admission as admission
    def no_ai(*a,**kw):raise AssertionError('Saved read must not call AI/admission')
    monkeypatch.setattr(admission,'decide',no_ai)
    monkeypatch.setattr(m8_results,'generate_recommendations',no_ai)
    monkeypatch.setattr(routes,'get_connection',factory)
    monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda token:SimpleNamespace(id=99))
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME,'synthetic-owner')
        read=http.get(f'/users/assessment/m8/reports/{report["id"]}')
        assert read.status_code==200 and read.json()['c67']==report['c67']
        pdf=http.get(f'/users/assessment/m8/reports/{report["id"]}/pdf')
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')

"""R11.1: synthetic saved chain, real PostgreSQL and HTTP delivery; not GC."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import json
import os
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_m6_evidence_db import database, enqueue, empty_output, _assessment_output
from Api import m6_repository, m6_assessment_repository, m8_results
from Api.m6_worker import run_request
from Api.m6_assessment_worker import run_request as run_assessment
from Api.m6_assessment_package import load_mechanism
from Api.m6_cycle_aggregation_repository import create
from Api.m7_completion import complete, read_c46
from Api.m8_recommendations import load_package
from Api.m8_recommendation_basis import resolve
from Api.m5_case_runtime import checksum

pytestmark=pytest.mark.integration


def saved_chain(database, *, mode='positive'):
    factory,handoff=database
    with factory() as c:
        c.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN)')
        c.execute('CREATE TABLE organization_memberships(user_id BIGINT,organization_id BIGINT)')
        c.execute('INSERT INTO organizations VALUES(1,TRUE)')
        c.execute('INSERT INTO organization_memberships VALUES(99,1)')
        c.execute('UPDATE m5_cycles SET organization_id=1')
        from Api.m10_orchestration import ensure_schema
        ensure_schema(c)
        request=enqueue(c,handoff,key='r11-evidence');c.commit()
    action=load_package()['templates']['supported_actions'][1]['confirmed_action']
    class Evidence:
        enabled=True
        def chat(self,messages,**kwargs):
            material=json.loads(messages[1]['content']);value=empty_output(material)
            index=2 if mode=='mixed' else 0
            criterion=material['criteria'][index];indicator=criterion['id'];turn=material['turns'][0]
            value['fragments']=[{'id':'f1','turn_id':turn['turn_id'],'start':0,'end':len(turn['content']),'quote':turn['content']}]
            value['signals']=[{'id':'bs1','fragment_id':'f1','observation':'Синтетическая запись действия',
                              'form_description':'прямой ответ','context_refs':[]}]
            value['evidence']=[{'id':'e1','indicator_id':indicator,'m2_version':criterion['m2_version'],'type':'Simple',
                'interpretation':action,'bs_ids':['bs1'],'fragment_ids':['f1'],
                'attribution':{'function':criterion['function'],'product':criterion['product'],
                               'evidence_pattern':criterion['evidence_pattern'],'boundaries':criterion['boundary']},
                'context_refs':[],'limitations':['Синтетический пример, не GC'],'ordered_turn_ids':[turn['turn_id']]}]
            value['bundles'][index]['evidence_ids']=['e1']
            return json.dumps(value,ensure_ascii=False)
    run_request(request['id'],connection_factory=factory,gateway=Evidence())
    with factory() as c:
        evidence=m6_repository.read_request(c,request['id'])['analysis_revision_id']
        ia_request=m6_assessment_repository.enqueue(c,evidence_revision_id=str(evidence),key='r11-ia',
            mechanism=load_mechanism('m6_indicator_assessment/1.0.0'),created_by=99);c.commit()
    class Assessment:
        enabled=True
        def chat(self,messages,**kwargs):
            value=json.loads(messages[1]['content']);output=_assessment_output(value)
            for i,target in enumerate(output['targets']):
                target.update(outcome='INSUFFICIENT_EVIDENCE',descriptor_basis=None,refs=[],
                    uncertainty={'missing_or_conflicting_feature':'Нет проверяемого действия','impact':'Уровень не обоснован',
                    'clarification_needed':'Не хватает материала','resolution_information':[],'requires_new_independent_action':True})
                target['confidence']['confirmed_features']=[]
                if i==(2 if mode=='mixed' else 0) and mode!='empty':
                    criterion=value['material']['criteria'][i]
                    target.update(outcome='L1',descriptor_basis=criterion['levels']['L1'],
                        rationale='В данном ответе восстановлен основной прямо выраженный смысл позиции другого.',uncertainty=None,
                        refs=[{'kind':'evidence','id':'e1','meaning':action}])
                    target['confidence']=deepcopy(target['confidence'])
                    target['confidence']['confirmed_features']=[action]
            return json.dumps(output,ensure_ascii=False)
    run_assessment(ia_request['id'],connection_factory=factory,gateway=Assessment())
    with factory() as c:
        assert m6_assessment_repository.read_request(c,ia_request['id'])['status']=='succeeded'
        cycle=str(c.execute('SELECT cycle_id FROM m5_cycles').fetchone()['cycle_id'])
        complete(c,cycle_id=cycle,key='r11-close',action='complete',reason='synthetic',initiated_by=99)
        rows=c.execute('''SELECT i.indicator_id,r.id,r.content_json FROM m6_indicator_assessment_revisions r
                          JOIN m6_indicator_assessments i ON i.id=r.indicator_assessment_id''').fetchall()
        decisions=[{'indicator_id':row['indicator_id'],'included_revision_ids':[str(row['id'])] if row['content_json']['outcome']=='L1' else [],
                    'interpretation_admissible':mode!='denied','numeric_admissible':mode not in ('qualitative','denied') and row['content_json']['outcome']=='L1',
                    'reason_code':'SYNTHETIC','rationale':'synthetic explicit interpretation admission','conditions_refs':['synthetic']} for row in rows]
        calculation=create(c,cycle_id=cycle,key='r11-calculation',expected_composition_checksum=read_c46(c,cycle)['composition_checksum'],
                           admission_mechanism_version='synthetic-test/1',decisions=decisions,created_by=99)
        results=m8_results.create_results(c,cycle_id=cycle,calculation_id=calculation['id'],key='r11-results',target_profile=None,created_by=99)
        report=m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',key='r11-report',target_profile=None,created_by=99)
        c.commit()
    return factory,results,report


@pytest.mark.parametrize('mode',['positive','mixed','empty','qualitative','denied'])
def test_r11_saved_basis_and_scope(database,mode):
    factory,results,report=saved_chain(database,mode=mode)
    if os.getenv('R11_ARTIFACT_DIR'):
        destination=Path(os.environ['R11_ARTIFACT_DIR']);destination.mkdir(parents=True,exist_ok=True)
        (destination/(mode+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n')
    recs=report['c67']['recommendations']
    if mode in ('empty','denied'):
        assert not recs and report['c67']['recommendation_generation']['status']=='unavailable'
    else:
        assert recs, report['c67']['recommendation_generation']
        assert all(x['basis_refs'][0]['outcome']=='L1' for x in recs)
        assert {x['type'] for x in recs}==({'Development'} if mode=='mixed' else
            {'Development','Consolidation / Maintenance','Application / Transfer'})
        if mode=='qualitative':
            assert any(s['outcome']=='result_without_score' for s in results['results']['assessed_skill_profile'])
        with factory() as c:
            resolved=resolve(c,results)
            assert any(p['traces'] and p['traces'][0].get('fragments') for p in resolved['projections'])
            for change in ('cycle','results','ia','evidence','duplicate'):
                bad=deepcopy(results)
                if change=='cycle':bad['cycle_id']=str(uuid4())
                if change=='results':bad['results']['admissions']=[]
                if change=='ia':bad['results']['observations'][0]['revision_id']=str(uuid4())
                if change=='evidence':bad['results']['observations'][0]['evidence_revision_id']=str(uuid4())
                if change=='duplicate':bad['results']['observations']*=2
                with pytest.raises(ValueError):resolve(c,bad)


def test_r11_history_regeneration_failure_and_real_http(database,monkeypatch,tmp_path):
    factory,results,report=saved_chain(database)
    with factory() as c:
        ia_before=c.execute('SELECT id,content_hash FROM m6_indicator_assessment_revisions ORDER BY id').fetchall()
        before=c.execute('SELECT payload_checksum FROM m8_result_revisions WHERE id=%s',(results['revision_id'],)).fetchone()
        old=deepcopy(report['c67']);old['recommendation_generation']['contract_version']='m8-recommendations/1.0.0'
        old['recommendations'][0]['goal']='Выдуманное проявление старого генератора'
        old_id=str(uuid4());old['report_id']=old_id;old['report_revision_no']=2
        c.execute('''INSERT INTO m8_reports(id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
                     VALUES(%s,%s,2,'assessee','m8-basic-report/1.1.0',%s::jsonb,%s,'ready','old','old',99)''',
                  (old_id,results['revision_id'],json.dumps(old,ensure_ascii=False),checksum(old)))
        historical=m8_results.read_report(c,old_id)
        assert historical['c67']['recommendations']==[]
        assert c.execute('SELECT c67_json FROM m8_reports WHERE id=%s',(old_id,)).fetchone()['c67_json']==old
        newer_profile={'role_profile':{'typical_tasks':['Новая задача вне snapshot Cycle']}}
        c.execute("INSERT INTO assessment_personalized_profiles VALUES(8,'ready',%s::jsonb,'{}',%s)",
                  (json.dumps(newer_profile),checksum(newer_profile)))
        fresh=m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',key='new',target_profile=None,created_by=99)
        assert 'Новая задача вне snapshot Cycle' not in json.dumps(fresh,ensure_ascii=False,default=str)
        assert fresh['revision_no']==3 and fresh['c67']['recommendations']==report['c67']['recommendations']
        assert m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',key='new',target_profile=None,created_by=99)['id']==fresh['id']
        assert before==c.execute('SELECT payload_checksum FROM m8_result_revisions WHERE id=%s',(results['revision_id'],)).fetchone()
        assert ia_before==c.execute('SELECT id,content_hash FROM m6_indicator_assessment_revisions ORDER BY id').fetchall()
        c.execute("UPDATE m5_cycles SET usage_scope='assessment'");c.commit()
    import Api.routes as routes
    monkeypatch.setattr(routes,'get_connection',factory)
    monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda token:SimpleNamespace(id=99 if token=='owner' else 100))
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
        url=f"/users/assessment/m8/cycles/{results['cycle_id']}/reports/latest"
        response=http.get(url);assert response.status_code==200
        assert response.json()['c67']['recommendations']==fresh['c67']['recommendations']
        # REV-03: selecting a historical report must not silently open the latest revision.
        saved_response=http.get(f"/users/assessment/m8/reports/{report['id']}")
        assert saved_response.status_code==200
        assert saved_response.json()['id']==report['id']
        assert saved_response.json()['revision_no']==1
        assert saved_response.json()['c67']==report['c67']
        with factory() as history_connection:
            history=m8_results.list_owned_reports(history_connection,99)
        assert len(history)==1 and len(history[0]['versions'])==3
        assert history[0]['report_id']==fresh['id']

        pdf=http.get(f"/users/assessment/m8/reports/{fresh['id']}/pdf")
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
        (tmp_path/'report.pdf').write_bytes(pdf.content)
        if os.getenv('R11_ARTIFACT_DIR'):
            destination=Path(os.environ['R11_ARTIFACT_DIR']);destination.mkdir(parents=True,exist_ok=True)
            (destination/'report.pdf').write_bytes(pdf.content)
            (destination/'http-report.json').write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n')
        legacy_pdf=http.get(f'/users/assessment/m8/reports/{old_id}/pdf');assert legacy_pdf.status_code==200
        http.cookies.set(routes.SESSION_COOKIE_NAME,'other')
        assert http.get(url).status_code==403
        assert http.get(f"/users/assessment/m8/reports/{fresh['id']}/pdf").status_code==403
    with factory() as c:
        with monkeypatch.context() as patch:
            patch.setattr(m8_results,'generate_recommendations',lambda *a,**k:(_ for _ in ()).throw(ValueError('synthetic failure')))
            failed=m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',key='failure',target_profile=None,created_by=99)
        if os.getenv('R11_ARTIFACT_DIR'):
            (Path(os.environ['R11_ARTIFACT_DIR'])/'failure.json').write_text(json.dumps(failed,ensure_ascii=False,indent=2,default=str)+'\n')
        assert failed['c67']['skills'] and not failed['c67']['recommendations']
        assert failed['c67']['recommendation_generation']['status']=='failed'
        assert m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',key='failure',target_profile=None,created_by=99)['id']==failed['id']
        c.commit()

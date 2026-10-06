"""A8.1 saved revisions -> admission -> C56 -> Results -> HTTP C67/PDF. Not GC."""
from copy import deepcopy
from types import SimpleNamespace
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_m6_evidence_db import database
from test_m8_recommendation_basis_db import saved_chain
from tests.m6_admission_fixture import RecordedAdmissionGateway
from Api import m6_cycle_aggregation_repository as calculations, m8_results
from Api.m6_admission_material import resolve
from Api.m7_completion import read_c46
from Api.m5_case_runtime import checksum

pytestmark = pytest.mark.integration


def add_original_plan(factory):
    from Api.m7_planning_repository import save_plan
    with factory() as c:
        cycle=dict(c.execute('SELECT * FROM m5_cycles').fetchone())
        targets=c.execute('SELECT snapshot_json FROM m5_assessment_situations').fetchone()['snapshot_json']['indicator_targets']
        save_plan(c,cycle=cycle,profile_ref={},full_targets=targets,planned_targets=targets,
                  requirements=[{'indicator_id':x['indicator_id'],'distinct_as_required':1} for x in targets],
                  rules={'snapshot_checksum':'a'*64},content={'status':'READY','route':[],'goal':'synthetic admission regression'},
                  created_by=99,key='synthetic-original-plan',request_hash='b'*64)
        c.commit()


@pytest.mark.parametrize('mode',['admitted','joint_failure','not_comparable','no_ia'])
def test_saved_chain_retry_and_http(database,monkeypatch,tmp_path,mode):
    add_original_plan(database[0])
    factory,old_results,old_report=saved_chain(database)
    gateway=RecordedAdmissionGateway(fail='joint' if mode=='joint_failure' else None,
        joint='NOT_COMPARABLE' if mode=='not_comparable' else 'COMPARABLE',
        individual='NOT_ADMITTED' if mode=='no_ia' else 'ADMITTED')
    cycle=old_results['cycle_id']
    with factory() as c:
        composition=read_c46(c,cycle)['composition_checksum']
        calculated=calculations.create_substantive(c,cycle_id=cycle,key='substantive-1',
            expected_composition_checksum=composition,created_by=99,gateway=gateway)
        admitted=[d for d in calculated['c56']['admissions'] if d['interpretation_admissible']]
        if mode=='no_ia': assert not admitted
        else:
            assert len(admitted)==1
            assert admitted[0]['numeric_admissible']==(mode=='admitted')
            assert admitted[0]['contexts'][0]['material']['handoff_ref']
        calls=len(gateway.calls)
        assert calculations.create_substantive(c,cycle_id=cycle,key='substantive-1',
            expected_composition_checksum=composition,created_by=99,gateway=gateway)['id']==calculated['id']
        assert len(gateway.calls)==calls
        results=m8_results.create_results(c,cycle_id=cycle,calculation_id=calculated['id'],
            key='substantive-results',target_profile=None,created_by=99)
        report=m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',
            key='substantive-report',target_profile=None,created_by=99)
        assert report['c67']['admission_summary']
        assert 'ai_trace' not in json.dumps(report['c67'])
        assert 'm6-substantive-admission/2' not in json.dumps(report['c67'])
        assert all(d['mechanism_ref']['ref']=='m6_substantive_admission/2.0.0' for d in report['c67']['admission_summary'])
        assert report['c67']['reliability']['status']=='not_verified'
        refs={r for d in calculated['c56']['admissions'] for r in d['interpretable_revision_ids']}
        assert all(b['ia_revision_id'] in refs for rec in report['c67']['recommendations'] for b in rec['basis_refs'])
        if mode=='no_ia': assert not report['c67']['recommendations']
        else: assert report['c67']['recommendations']
        if mode in ('joint_failure','not_comparable'):
            assert any(s['outcome']=='result_without_score' for s in report['c67']['skills'])
        original=deepcopy(report)
        retry=calculations.create_substantive(c,cycle_id=cycle,key='substantive-retry',
            expected_composition_checksum=composition,created_by=99,gateway=RecordedAdmissionGateway())
        assert retry['revision_no']==calculated['revision_no']+1
        assert m8_results.read_report(c,report['id'])==original
        assert m8_results.read_report(c,old_report['id'])==old_report
        assert m8_results.read_results_revision(c,old_results['revision_id'])==old_results
        c.execute("UPDATE m5_cycles SET usage_scope='assessment'")
        c.execute("UPDATE m5_assessment_situations SET usage_scope='assessment'")
        c.commit()
    import Api.routes as routes
    monkeypatch.setattr(routes,'get_connection',factory)
    monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda token:SimpleNamespace(id=99))
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
        response=http.get(f"/users/assessment/m8/reports/{report['id']}")
        assert response.status_code==200 and response.json()['c67']==report['c67']
        pdf=http.get(f"/users/assessment/m8/reports/{report['id']}/pdf")
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
        (tmp_path/'admission.pdf').write_bytes(pdf.content)
        if os.getenv('M81_ARTIFACT_DIR'):
            destination=Path(os.environ['M81_ARTIFACT_DIR']);destination.mkdir(parents=True,exist_ok=True)
            (destination/(mode+'.pdf')).write_bytes(pdf.content)
            (destination/(mode+'.json')).write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n')


def test_saved_material_rejects_wrong_cycle_revision_and_unpresented_refs(database):
    factory,results,_=saved_chain(database)
    observation=next(x for x in results['results']['observations'] if x['outcome']=='L1')
    with factory() as c:
        projection=resolve(c,cycle_id=results['cycle_id'],observations=[observation])[0]
        assert projection['material']['mode']=='final_as'
        for field in ('assessment_revision_id','evidence_revision_id','assessment_situation_id','revision_id'):
            bad={**observation,field:str(uuid4())}
            with pytest.raises(ValueError):resolve(c,cycle_id=results['cycle_id'],observations=[bad])
        with pytest.raises(ValueError):resolve(c,cycle_id=str(uuid4()),observations=[observation])
        bad={**observation,'refs':[{'kind':'material','id':'unpresented','meaning':'not available'}]}
        with pytest.raises(ValueError):resolve(c,cycle_id=results['cycle_id'],observations=[bad])
        with pytest.raises(ValueError):resolve(c,cycle_id=results['cycle_id'],observations=[observation,observation])

"""Actual owner HTTP/auth/worker/DB smoke. No fake connections or result inserts."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
from uuid import uuid4


def smoke(state):
    base=f"http://127.0.0.1:{state['port']}"
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,data=None,code=200,raw=False):
        body=json.dumps(data).encode() if data is not None else None
        req=urllib.request.Request(base+path,data=body,headers={'Content-Type':'application/json'})
        try:
            with client.open(req,timeout=20) as r:status=r.status;value=r.read()
        except urllib.error.HTTPError as e:status=e.code;value=e.read()
        if status!=code:raise RuntimeError(f'{path}: HTTP {status}: {value[:400]!r}')
        return value if raw else json.loads(value)
    ready=request('/health/ready');assert ready['status']=='ready' and ready['gateway_mode']=='synthetic'
    assert b'<html' in request('/',raw=True).lower()
    signed_in=request('/users/auth/email/password-login',{'email':'superadmin@example.test','password':state['password']})
    assert signed_in['admin_dashboard'] is not None
    admin_dashboard=request('/users/admin/dashboard')
    assert any(item['label'] == 'Среднее время прохождения' for item in admin_dashboard['metrics'])
    request('/users/auth/email/password-login',{'email':'participant@example.test','password':state['password']})
    out=Path(state['state_path']).parent
    saved=out/'smoke.json'
    if saved.exists():
        prior=json.loads(saved.read_text());cycle=prior['cycle_id']
        report=request(f'/users/assessment/m8/cycles/{cycle}/reports/latest')
        assert report['id']==prior['report_id']
    else:
        started=request('/users/assessment/cycles/start',{'idempotency_key':'e102-start','selected_skills':['K1','K2','K3','K4']},201)
        cycle=started['runtime']['cycle_id']
        resumed=request('/users/assessment/cycles/start',{'idempotency_key':'e102-resume','selected_skills':['K1','K2','K3','K4']},201)
        assert resumed['runtime']['cycle_id']==cycle
        situation=started['runtime']['current_situation']['assessment_situation_id']
        for n in range(2):
            request(f'/users/assessment/m5/situations/{situation}/turns',{
                'request_id':'e102-turn-'+str(n),'turn_id':str(uuid4()),
                'content':'Синтетический технический ответ: уточняю позиции сторон, предлагаю согласовать следующий шаг и проверить понимание.'})
        request(f'/users/assessment/m7/cycles/{cycle}/completion',{'idempotency_key':'e102-close','action':'complete','reason':'participant_finished'})
        deadline=time.monotonic()+90
        while True:
            status=request(f'/users/assessment/m8/cycles/{cycle}/status')
            if 'report_ready' in str(status):break
            if 'processing_failed' in str(status):raise RuntimeError(str(status))
            if time.monotonic()>deadline:raise RuntimeError('pipeline deadline: '+str(status))
            time.sleep(.5)
        report=request(f'/users/assessment/m8/cycles/{cycle}/reports/latest')
    owner=request('/users/auth/email/password-login',{'email':'participant@example.test','password':state['password']})
    assert owner['dashboard']['active_assessment']['progress_percent']==100
    assert owner['dashboard']['reports_total']>=1
    second=request(f'/users/assessment/m8/cycles/{cycle}/reports/latest')
    assert report==second and report['c67']['contract']=='C-67'
    pdf=request(f"/users/assessment/m8/reports/{report['id']}/pdf",raw=True)
    assert pdf.startswith(b'%PDF') and len(pdf)>1000
    (out/'report.pdf').write_bytes(pdf)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    result={'gateway':'synthetic','cycle_id':cycle,'report_id':report['id'],
        'results_revision_id':report['results_revision_id'],'report_revision':report['revision_no'],
        'report_mechanism':report['c67']['report_mechanism'],'recommendation_status':report['c67']['recommendation_generation']['status']}
    request('/users/auth/email/password-login',{'email':'other@example.test','password':state['password']})
    request(f'/users/assessment/m8/cycles/{cycle}/reports/latest',code=403)
    request(f"/users/assessment/m8/reports/{report['id']}/pdf",code=403)
    saved.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True)
    smoke(json.loads(p.parse_args().state.read_text()))

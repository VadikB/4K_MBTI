"""Rare historical/failure fixtures AFTER a real browser run. Owned stand only."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.test_stand import owned,environment
p=argparse.ArgumentParser()
p.add_argument('--state',type=Path,required=True)
p.add_argument('--cycle',required=True)
p.add_argument('--kind',choices=['legacy','failure','archive-session'],required=True)
p.add_argument('--internal',action='store_true')
a=p.parse_args();state=json.loads(a.state.read_text())
with owned(state):pass
if not a.internal:
    subprocess.run([sys.executable,__file__,'--state',str(a.state),'--cycle',a.cycle,'--kind',a.kind,'--internal'],env=environment(state),check=True)
else:
    from Api.database import get_connection
    from Api import m8_results
    from Api.m5_case_runtime import checksum
    from unittest.mock import patch
    with get_connection() as c:
        report=m8_results.read_latest_report(c,a.cycle,'assessee')
        before=c.execute('SELECT payload_checksum FROM m8_result_revisions WHERE id=%s',(report['results_revision_id'],)).fetchone()
        if a.kind=='archive-session':
            c.execute("""INSERT INTO user_sessions(user_id,session_code,assessment_code,status)
                VALUES(%s,'synthetic-browser-h106-archive','competencies_4k','completed')""", (report['owner_user_id'],))
        elif a.kind=='legacy':
            old=json.loads(json.dumps(report['c67']));old['recommendation_generation']['contract_version']='m8-recommendations/1.0.0'
            old['recommendations'][0]['goal']='Недопустимое историческое проявление — synthetic fixture'
            old_id=str(uuid4());revision=report['revision_no']+1;old['report_id']=old_id;old['report_revision_no']=revision
            c.execute('''INSERT INTO m8_reports(id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,status,request_key,request_hash,created_by)
                VALUES(%s,%s,%s,'assessee','m8-basic-report/1.1.0',%s::jsonb,%s,'ready','browser-old','browser-old',%s)''',
                (old_id,report['results_revision_id'],revision,json.dumps(old,ensure_ascii=False),checksum(old),report['owner_user_id']))
            assert m8_results.read_report(c,old_id)['c67']['recommendations']==[]
            assert c.execute('SELECT c67_json FROM m8_reports WHERE id=%s',(old_id,)).fetchone()['c67_json']==old
        else:
            with patch.object(m8_results,'generate_recommendations',side_effect=ValueError('synthetic recommendation failure')):
                m8_results.create_report(c,results_revision_id=report['results_revision_id'],audience='assessee',key='browser-failure',target_profile=None,created_by=report['owner_user_id'])
        assert c.execute('SELECT payload_checksum FROM m8_result_revisions WHERE id=%s',(report['results_revision_id'],)).fetchone()==before
        c.commit()
    print('Rare fixture prepared:',a.kind)

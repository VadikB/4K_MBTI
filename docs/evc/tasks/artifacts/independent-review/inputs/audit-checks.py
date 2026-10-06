"""Read-only independent audit; fake SQL boundary, exclusively synthetic data."""
import os
os.environ['DB_POOL_MIN_SIZE'] = '0'
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Api import routes, m10_product_flow, m6_admission
from Api.m8_recommendations import profile_projection

root = Path.cwd()
checks = {}
user = dict(id=919191, full_name='Synthetic audit user', email='audit@example.test',
            created_at=datetime.now(timezone.utc), role_id=1,
            job_description='Synthetic specialist', raw_duties='Synthetic tasks')

class Result:
    def __init__(self, one=None, many=None): self.one, self.many = one, many or []
    def fetchone(self): return self.one
    def fetchall(self): return self.many

class Connection:
    def __init__(self): self.queries=[]; self.updates=[]
    def execute(self, sql, params=None):
        self.queries.append(sql)
        if 'UPDATE users' in sql:
            self.updates.append(params)
            return Result()
        if 'FROM user_sessions us' in sql: return Result(many=[])
        if 'COUNT(s.id)' in sql:
            return Result(dict(id=10, status='calculated', total_cases=1, completed_cases=1))
        if 'FROM m8_reports p' in sql:
            return Result(many=[dict(created_at=datetime.now(timezone.utc),revision_no=1)])
        if 'SELECT 1 FROM assessment_personalized_profiles' in sql: return Result({'ready':1})
        if 'SELECT id FROM assessment_personalized_profiles' in sql: return Result()
        if 'FROM users u' in sql: return Result(user)
        raise AssertionError('Unexpected SQL in fake boundary: '+sql[:100])
    def commit(self): pass

connection=Connection()
@contextmanager
def factory(): yield connection

app=FastAPI(); app.include_router(routes.router)
with patch.object(routes,'get_connection',factory), patch.object(routes.web_session_service,'get_user_by_token',return_value=None) as auth:
    with TestClient(app) as http:
        read=http.get('/users/919191/profile-summary')
        update=http.patch('/users/919191/profile', json={'email':'changed@example.test','telegram':'@synthetic'})
    checks['anonymous_profile_access']={
        'expected':'401/403, no UPDATE', 'observed_read':read.status_code,
        'observed_patch':update.status_code, 'fake_updates':len(connection.updates),
        'auth_checks':auth.call_count, 'synthetic_email_returned':read.json().get('user',{}).get('email')=='audit@example.test',
        'boundary':'real FastAPI router; SQL mocked, no main startup or live DB'}
    dashboard=routes._build_dashboard(connection,routes.UserResponse(**user))
    history=routes.get_user_profile_summary(user['id'])
    checks['report_history_split']={'dashboard_m8_reports':dashboard.reports_total,
        'profile_summary_reports':history.total_assessments,
        'history_query_uses_legacy':any('FROM user_sessions us' in q for q in connection.queries)}

try: m10_product_flow._owned_profile(connection,user['id'])
except ValueError as exc: checks['start_without_ready_m4']={'observed':str(exc),'boundary':'real function, empty synthetic M4 query'}

calls=[]
for path in (root/'Api').rglob('*.py'):
    tree=ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
            if name=='create_personalized_profile': calls.append(str(path.relative_to(root)))
checks['m4_creation_api_calls']=calls

results=json.loads((root/'docs/evc/tasks/artifacts/task10-3/scenario-1/08-saved-results.json').read_text())['results']
snapshot=results['personalized_profile_snapshot']; content=snapshot['content']
checks['saved_m4_projection']={
    'projection':profile_projection(snapshot),
    'role_card_mission_present':bool(content['role_profile']['card'].get('mission')),
    'role_card_tasks_present':bool(content['role_profile']['card'].get('typical_tasks')),
    'organization_activity_present':bool(content['organization_context'].get('activity_description')),
    'user_position_present':bool(content['user_context'].get('position_or_status'))}

class AdmissionConnection:
    def execute(self,sql,params):
        if 'observation_requirements_json' in sql:
            return Result({'observation_requirements_json':[{'indicator_id':'I1','distinct_as_required':2}]})
        return Result({'snapshot_json':{'base_role':'same_role','case_ref':{'id':params[0]},
            'authority':'can_decide' if params[0]=='as1' else 'must_escalate',
            'available_materials':['full'] if params[0]=='as1' else []}})
observations=[{'indicator_id':'I1','assessment_situation_id':'as'+str(i),'revision_id':'r'+str(i),
    'm2_version':'v1.1','outcome':'L1','opportunity':'PRESENT',
    'refs':[{'kind':'turn','id':'t'+str(i),'meaning':'synthetic'}],'contradictions':[]} for i in [1,2]]
_,decisions,_=m6_admission.decide(AdmissionConnection(),cycle_id='synthetic',observations=observations)
checks['admission_context_projection']={'numeric_admissible':decisions[0]['numeric_admissible'],
    'saved_context_keys':sorted(decisions[0]['contexts'][0]),
    'limitation':'Does not prove these observations must be rejected; proves authority/material differences are not examined.'}

print(json.dumps(checks,ensure_ascii=False,indent=2))

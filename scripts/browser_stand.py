"""Pre-scenario synthetic preparation only; never writes assessment outputs."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.test_stand import owned,environment
p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--variant',choices=['ordinary','budget','deadline'],default='ordinary');p.add_argument('--internal',action='store_true');a=p.parse_args()
state=json.loads(a.state.read_text())
with owned(state):pass
if not a.internal:
    state['browser_scenario']='acceptance-v1';a.state.write_text(json.dumps(state))
    subprocess.run([sys.executable,__file__,'--state',str(a.state),'--variant',a.variant,'--internal'],env=environment(state),check=True)
elif a.variant!='ordinary':
    from Api.database import get_connection
    from Api.m10_product_flow import prepare
    from Api.m7_cycle_planner import revise_prepared_parameters
    with get_connection() as c:
        uid=c.execute("SELECT id FROM users WHERE email='participant@example.test'").fetchone()['id']
        profile=c.execute("SELECT id FROM assessment_personalized_profiles WHERE user_id=%s AND status='ready'",(uid,)).fetchone()['id']
        prepared=prepare(c,user_id=uid,profile_id=profile,selected_skills=['K1','K2','K3','K4'],key='browser-prepared')
        revise_prepared_parameters(c,cycle_id=str(prepared['plan']['cycle_id']),created_by=uid,
            reason='browser_time_boundary',time_budget_seconds=30 if a.variant=='budget' else 3600,
            calendar_window_seconds=30 if a.variant=='deadline' else 259200)
        c.commit()
print('browser inputs prepared',a.variant)

"""Read-only evidence for task 10.5 on a verified owned synthetic stand."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import owned, environment
parser = argparse.ArgumentParser()
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--internal', action='store_true')
args = parser.parse_args()
state = json.loads(args.state.read_text())
with owned(state):
    pass
if not args.internal:
    subprocess.run([sys.executable, __file__, '--state', str(args.state), '--internal'],
                   env=environment(state), check=True)
else:
    from Api.database import get_connection, close_connection_pool
    from Api.participant_profile import validate_snapshot
    with get_connection() as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        owner = connection.execute("SELECT id FROM users WHERE email='participant@example.test'").fetchone()['id']
        profiles = connection.execute('SELECT * FROM assessment_personalized_profiles WHERE user_id=%s ORDER BY id', (owner,)).fetchall()
        for profile in profiles:
            validate_snapshot(connection, profile)
        contexts = connection.execute('''SELECT count(*) AS n FROM assessment_user_context_versions v
            JOIN assessment_user_contexts c ON c.id=v.user_context_id WHERE c.user_id=%s''', (owner,)).fetchone()['n']
        cycles = connection.execute('''SELECT c.cycle_id,c.owner_user_id,c.organization_id,c.personalized_profile_id,
            c.profile_ref_json,c.selected_role_ref_json,count(s.id) AS situations FROM m5_cycles c
            LEFT JOIN m5_assessment_situations s ON s.cycle_db_id=c.id WHERE c.owner_user_id=%s GROUP BY c.id ORDER BY c.id''', (owner,)).fetchall()
        print(json.dumps({'owner':owner,'user_context_count':contexts,'profiles':[
            {key:p[key] for key in ('id','user_id','organization_id','assessment_configuration_id','role_profile_version_id',
             'organization_context_version_id','user_context_version_id','status','checksum','provenance_json')} for p in profiles],
             'cycles':[dict(c) for c in cycles]},default=str))
    close_connection_pool()

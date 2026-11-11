"""Owned synthetic account setup and independent PostgreSQL receipt readback."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import environment, owned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'readback'])
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--internal', action='store_true')
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        env = environment(state)
        env['PYTHON_DOTENV_DISABLED'] = '1'
        subprocess.run([sys.executable, __file__, args.action, '--state', str(args.state), '--internal'],
                       env=env, cwd=ROOT, check=True, timeout=60)
        return
    if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
        raise RuntimeError('OWNED_ISOLATED_STAND_REQUIRED')
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.routes import SESSION_COOKIE_NAME
    try:
        if args.action == 'prepare':
            users = {}
            with get_connection() as connection:
                for label, email in [('super', 'superadmin@example.test'), ('ordinary', 'ordinary@example.test'),
                                     ('before', 'purge-before@example.test'), ('after', 'purge-after@example.test')]:
                    uid = connection.execute('INSERT INTO users(email,full_name) VALUES(%s,%s) RETURNING id',
                        (email, 'Synthetic purge ' + label)).fetchone()['id']
                    connection.execute("INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at) VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())", (uid, email))
                    users[label] = {'id': uid, 'email': email}
                organization_id = connection.execute("INSERT INTO organizations(code,name) VALUES('purge_current_people','Synthetic current people') RETURNING id").fetchone()['id']
                for label, role in [('super', 'admin'), ('before', 'member'), ('after', 'member')]:
                    connection.execute("INSERT INTO organization_memberships(organization_id,user_id,role,is_participant,admission_source,admitted_at) VALUES(%s,%s,%s,%s,'admin_add',NOW())",
                        (organization_id, users[label]['id'], role, role == 'member'))
                control_organization_id = connection.execute("INSERT INTO organizations(code,name) VALUES('purge_guard_control','Synthetic permission control') RETURNING id").fetchone()['id']
                connection.execute("INSERT INTO organization_memberships(organization_id,user_id,role,is_participant,admission_source,admitted_at) VALUES(%s,%s,'admin',FALSE,'admin_add',NOW())", (control_organization_id, users['ordinary']['id']))
                connection.commit()
            state['remarks_purge'] = users
            args.state.write_text(json.dumps(state, default=str))
            # Private subprocess data only: never export these synthetic session values.
            print(json.dumps({'users': users, 'organization_id': organization_id, 'cookie_name': SESSION_COOKIE_NAME,
                'super_session': web_session_service.create_session(users['super']['id']),
                'ordinary_session': web_session_service.create_session(users['ordinary']['id'])}))
        else:
            with get_connection() as connection:
                rows = {}
                for label, user in state['remarks_purge'].items():
                    rows[label] = {'exists': connection.execute('SELECT 1 FROM users WHERE id=%s', (user['id'],)).fetchone() is not None,
                        'receipts': [dict(row) for row in connection.execute(
                            "SELECT operation_id,target_id,preview_fingerprint FROM data_deletion_receipts WHERE target_type='account' AND target_id=%s", (user['id'],)).fetchall()]}
                print(json.dumps(rows, default=str))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()

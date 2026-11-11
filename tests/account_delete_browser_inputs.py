"""Owned PostgreSQL inputs for the account deletion browser regression."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import environment, owned


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'session', 'detach', 'readback'])
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--email', default='')
    parser.add_argument('--internal', action='store_true')
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        result = subprocess.run(
            [sys.executable, __file__, args.action, '--state', str(args.state),
             '--email', args.email, '--internal'], env=environment(state), cwd=ROOT,
            check=True, capture_output=True, text=True, timeout=60,
        )
        print(result.stdout.strip())
        return
    if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
        raise RuntimeError('ISOLATED_STAND_REQUIRED')

    from Api.database import close_connection_pool, get_connection
    from Api.routes import SESSION_COOKIE_NAME
    from Api.web_session_service import web_session_service
    try:
        with get_connection() as connection:
            if args.action == 'prepare':
                actor = connection.execute(
                    "SELECT id FROM users WHERE email='superadmin@example.test'"
                ).fetchone()
                organization = connection.execute(
                    "SELECT id FROM organizations WHERE code='e102_synthetic'"
                ).fetchone()
                assert actor and organization
                print(json.dumps({
                    'organization_id': organization['id'], 'cookie_name': SESSION_COOKIE_NAME,
                    'session': web_session_service.create_session(actor['id']),
                }))
            else:
                assert args.email.endswith('@example.test')
                user = connection.execute(
                    'SELECT id FROM users WHERE email=%s', (args.email,)
                ).fetchone()
                if args.action == 'session':
                    assert user
                    print(json.dumps({'user_id': user['id'],
                        'session': web_session_service.create_session(user['id'])}))
                elif args.action == 'detach':
                    assert user
                    connection.execute('DELETE FROM organization_memberships WHERE user_id=%s', (user['id'],))
                    connection.commit()
                    print(json.dumps({'user_id': user['id']}))
                else:
                    membership = connection.execute('''SELECT m.role,m.is_participant,o.code
                        FROM organization_memberships m JOIN organizations o ON o.id=m.organization_id
                        WHERE m.user_id=%s''', (user['id'],)).fetchall() if user else []
                    sessions = connection.execute(
                        'SELECT COUNT(*) AS count FROM web_user_sessions WHERE user_id=%s',
                        (user['id'],),
                    ).fetchone()['count'] if user else 0
                    invitations = connection.execute('''SELECT COUNT(*) AS count FROM organization_invitations
                        WHERE LOWER(recipient_email)=%s''', (args.email,)).fetchone()['count']
                    print(json.dumps({'user_id': user['id'] if user else None,
                        'memberships': [dict(row) for row in membership],
                        'sessions': sessions, 'invitations': invitations}))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()

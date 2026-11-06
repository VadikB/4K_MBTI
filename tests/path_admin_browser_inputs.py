"""Synthetic browser setup/readback using the SAME real HTTP/PG test inputs."""
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
        subprocess.run([sys.executable, __file__, args.action, '--state', str(args.state), '--internal'],
                       env=environment(state), cwd=ROOT, check=True, timeout=60)
        return
    if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
        raise RuntimeError('ISOLATED_STAND_REQUIRED')
    from tests.path_admin_contract_checks import create_scope, session, ready, assignment_counts
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.routes import SESSION_COOKIE_NAME
    try:
        if args.action == 'prepare':
            scope = create_scope()
            with session(scope['admin']) as client:
                ready(client, scope)
            with get_connection() as c:
                emails = {str(row['id']): row['email'] for row in c.execute(
                    'SELECT id,email FROM users WHERE id=ANY(%s)', ([scope['member'], scope['second']],)).fetchall()}
            state['path_admin'] = scope
            args.state.write_text(json.dumps(state, default=str))
            # Short-lived synthetic session goes via private child stdout only;
            # caller never writes it into evidence or browser trace.
            print(json.dumps({'organization_id': scope['org'], 'member_emails': emails,
                'cookie_name': SESSION_COOKIE_NAME,
                'super_session': web_session_service.create_session(scope['super']),
                'program_id': scope['program'],
                'session': web_session_service.create_session(scope['admin'])}))
        else:
            print(json.dumps(assignment_counts(state['path_admin'])))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()

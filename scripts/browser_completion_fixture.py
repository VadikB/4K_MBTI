"""Saved pause/interruption fixtures on a verified owned browser stand only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import environment, owned


def prepare(connection, *, cycle_id: str, action: str) -> dict:
    from Api import m7_completion
    if action not in {'pause', 'interrupt_for_continuation'}:
        raise ValueError('BROWSER_SAVED_STATE_ACTION_INVALID')
    cycle = connection.execute("""SELECT c.owner_user_id,c.usage_scope,c.status,u.email
        FROM m5_cycles c JOIN users u ON u.id=c.owner_user_id
        WHERE c.cycle_id=%s FOR UPDATE OF c""", (UUID(cycle_id),)).fetchone()
    if (not cycle or cycle['usage_scope'] != 'qa' or cycle['status'] != 'active'
            or cycle['email'] != 'participant@example.test'):
        raise ValueError('BROWSER_SAVED_STATE_TARGET_INVALID')
    function = m7_completion.control if action == 'pause' else m7_completion.complete
    return function(connection, cycle_id=cycle_id, key=f'browser-historical:{uuid4()}',
                    action=action, reason=f'synthetic_historical_{action}',
                    initiated_by=int(cycle['owner_user_id']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--cycle', required=True)
    parser.add_argument('--action', choices=['pause', 'interrupt_for_continuation'], required=True)
    parser.add_argument('--internal', action='store_true')
    args = parser.parse_args(argv)
    state = json.loads(args.state.read_text())
    if (state.get('provider_mode') == 'real' or not state.get('gateway')
            or state.get('qa_orchestration') is not True):
        raise ValueError('BROWSER_SAVED_STATE_SYNTHETIC_STAND_REQUIRED')
    with owned(state):
        pass
    if not args.internal:
        subprocess.run([sys.executable, __file__, '--state', str(args.state),
                        '--cycle', args.cycle, '--action', args.action, '--internal'],
                       env=environment(state), check=True)
        return
    from Api.database import close_connection_pool, get_connection
    try:
        with get_connection() as connection:
            result = prepare(connection, cycle_id=args.cycle, action=args.action)
            connection.commit()
        print(json.dumps({'fixture': 'historical_completion', 'result': result}, default=str))
    finally:
        close_connection_pool()


if __name__ == '__main__':
    main()

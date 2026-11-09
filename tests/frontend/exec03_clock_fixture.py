"""Explicit elapsed-time input on a marker-owned EXEC03 preview; never changes snapshots."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--as-id', required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.root.resolve()))
from scripts.test_stand import owned
import psycopg
from psycopg.rows import dict_row
state = json.loads(args.state.read_bytes())
if (state.get('p3_a_fixture') != 'p3-a-saved-public-as/1'
        or state.get('provider_mode') != 'disabled' or state.get('gateway') != 1):
    raise ValueError('EXEC03_DISABLED_PROVIDER_PREVIEW_REQUIRED')
with owned(state):
    pass
with psycopg.connect(**{**state['connection'], 'dbname': state['database']}, row_factory=dict_row) as c:
    row = c.execute('''SELECT s.id,s.session_db_id,c.id AS cycle_db_id,c.cycle_id,c.status,
        c.time_budget_seconds,c.calendar_window_seconds FROM m5_assessment_situations s
        JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE s.assessment_situation_id=%s FOR UPDATE OF c,s''',
        (args.as_id,)).fetchone()
    allowed = {target['cycle_id'] for target in state['p3_a_previews'].values()}
    if not row or str(row['cycle_id']) not in allowed or row['status'] != 'active':
        raise ValueError('EXEC03_OWN_ACTIVE_CYCLE_REQUIRED')
    interval = c.execute('''SELECT id FROM m5_cycle_time_intervals WHERE cycle_db_id=%s
        AND interval_type='collecting' AND ended_at IS NULL FOR UPDATE''', (row['cycle_db_id'],)).fetchall()
    if len(interval) != 1:
        raise ValueError('EXEC03_ONE_COLLECTING_INTERVAL_REQUIRED')
    # Controlled clock input: the unchanged frozen budget is consumed. No Turn,
    # question, event, handoff, receipt, policy or budget is inserted/rewritten.
    c.execute("UPDATE m5_cycle_time_intervals SET started_at=NOW()-(%s*INTERVAL '1 second') WHERE id=%s",
              (row['time_budget_seconds'] + 1, interval[0]['id']))
    c.execute("UPDATE m5_cycles SET started_at=LEAST(started_at,NOW()-(%s*INTERVAL '1 second')) WHERE id=%s",
              (row['time_budget_seconds'] + 2, row['cycle_db_id']))
    c.execute("UPDATE m5_cycle_sessions SET started_at=LEAST(started_at,NOW()-(%s*INTERVAL '1 second')) WHERE id=%s",
              (row['time_budget_seconds'] + 2, row['session_db_id']))
    c.commit()
print(json.dumps({'fixture': 'exec03_elapsed_budget_input/1', 'run_id': state['run_id'],
                  'assessment_situation_id': args.as_id, 'time_budget_seconds': row['time_budget_seconds'],
                  'calendar_window_seconds': row['calendar_window_seconds'], 'intervals_adjusted': 1}))

"""Read-only SQL evidence for one EXEC03-owned synthetic AS; never emits state credentials."""
from __future__ import annotations
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
with owned(state):
    pass
with psycopg.connect(**{**state['connection'], 'dbname': state['database']}, row_factory=dict_row) as connection:
    connection.execute('SET TRANSACTION READ ONLY')
    target = connection.execute('SELECT id,status,cycle_db_id FROM m5_assessment_situations WHERE assessment_situation_id=%s',
                                (args.as_id,)).fetchone()
    if target is None:
        raise ValueError('EXEC03_AS_NOT_FOUND')
    result = {'run_id': state['run_id'], 'assessment_situation_id': args.as_id, 'status': target['status']}
    result['turns'] = connection.execute('''SELECT turn_id::text,request_id,sequence_no,speaker_type,content_text
        FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no''', (target['id'],)).fetchall()
    result['events'] = connection.execute('''SELECT event_id::text,sequence_no,event_type,material_id
        FROM m5_scenario_events WHERE assessment_situation_db_id=%s ORDER BY sequence_no''', (target['id'],)).fetchall()
    result['operations'] = connection.execute('''SELECT request_id,turn_id::text,status,attempt_no
        FROM m5_turn_operations WHERE assessment_situation_db_id=%s ORDER BY id''', (target['id'],)).fetchall()
    result['clarifications'] = connection.execute('''SELECT d.id::text,d.status,r.outcome,r.request_id,
        r.answer_turn_id::text,r.handoff_id::text
        FROM m7_clarification_decisions d LEFT JOIN m7_clarification_responses r ON r.decision_id=d.id
        WHERE d.assessment_situation_db_id=%s ORDER BY d.created_at''', (target['id'],)).fetchall()
    result['c45_handoffs'] = connection.execute('''SELECT handoff_id::text,mode,boundary_sequence
        FROM m5_c45_handoffs WHERE assessment_situation_db_id=%s ORDER BY boundary_sequence,mode''', (target['id'],)).fetchall()
    result['evidence_requests'] = connection.execute('''SELECT id::text,handoff_id::text,mode
        FROM m6_processing_requests WHERE as_db_id=%s ORDER BY id''', (target['id'],)).fetchall()
    result['assessment_requests'] = connection.execute('''SELECT id::text,evidence_revision_id::text,mode
        FROM m6_assessment_requests WHERE as_db_id=%s ORDER BY id''', (target['id'],)).fetchall()
    result['pipeline_revision_ids'] = connection.execute('''SELECT revision_no,status,stage
        FROM m10_pipeline_revisions WHERE cycle_db_id=%s ORDER BY revision_no''',
        (target['cycle_db_id'],)).fetchall()
    result['unsettled_jobs'] = sum(connection.execute(
        f"SELECT count(*) AS n FROM {table} WHERE as_db_id=%s AND status IN ('queued','running')",
        (target['id'],)).fetchone()['n'] for table in ('m6_processing_requests','m6_assessment_requests'))
print(json.dumps(result, ensure_ascii=False, indent=2))

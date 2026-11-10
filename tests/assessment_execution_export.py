"""Safe terminal readback shared by owned browser harnesses."""
import json
import os
from pathlib import Path
from fastapi import HTTPException

def execution_export(cycle_id: str):
    """Owned stand readback: identifiers and counters only, never dialogue content."""
    from Api.database import get_connection
    with get_connection() as c:
        state = json.loads(Path(os.environ['STAND_STATE']).read_text())
        row = c.execute("""SELECT id,cycle_id,owner_user_id,status,close_reason,
                collection_closed_at FROM m5_cycles WHERE cycle_id=%s""", (cycle_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'OWNED_CYCLE_NOT_FOUND')
        owner_email = 'path29-new@example.test' if state.get('path29') else 'participant@example.test'
        owner = c.execute("SELECT id FROM users WHERE email=%s", (owner_email,)).fetchone()
        if not owner or row['owner_user_id'] != owner['id']:
            raise HTTPException(403, 'OWNED_CYCLE_REQUIRED')
        situations = c.execute("""SELECT s.id,s.assessment_situation_id,s.status,sess.session_id,
                s.started_at,s.scenario_ended_at,s.closed_at,
                (SELECT COUNT(*) FROM m5_dialogue_turns t WHERE t.assessment_situation_db_id=s.id
                    AND t.speaker_type='assessee') AS assessee_turns,
                (SELECT COUNT(*) FROM m5_c45_handoffs h WHERE h.assessment_situation_db_id=s.id
                    AND h.mode='interim') AS interim_handoffs,
                (SELECT h.handoff_id FROM m5_c45_handoffs h WHERE h.assessment_situation_db_id=s.id
                    AND h.mode='final' ORDER BY h.id DESC LIMIT 1) AS final_handoff_id,
                (SELECT f.status FROM m7_finalization_outbox f WHERE f.assessment_situation_db_id=s.id)
                    AS finalization_status,
                (SELECT COUNT(*) FROM m5_c54_receipts r WHERE r.assessment_situation_db_id=s.id) AS c54_receipts
            FROM m5_assessment_situations s JOIN m5_cycle_sessions sess ON sess.id=s.session_db_id
            WHERE s.cycle_db_id=%s ORDER BY s.id""", (row['id'],)).fetchall()
        pipeline = c.execute("""SELECT status,stage,error_code,latest_calculation_id,
                latest_results_revision_id,latest_report_id
            FROM m10_pipeline_runs WHERE cycle_db_id=%s""", (row['id'],)).fetchone()
        c46 = c.execute("""SELECT id,status,revision_no FROM m7_c46_revisions
            WHERE cycle_db_id=%s ORDER BY revision_no DESC LIMIT 1""", (row['id'],)).fetchone()
        results = c.execute("""SELECT rr.id,rr.revision_no,rr.c46_revision_id
            FROM m8_results r JOIN m8_result_revisions rr ON rr.results_id=r.id
            WHERE r.cycle_db_id=%s ORDER BY rr.revision_no DESC LIMIT 1""", (row['id'],)).fetchone()
        report = c.execute("""SELECT p.id,p.revision_no,p.status,p.audience,p.created_by,
                p.result_revision_id FROM m8_reports p
            JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
            JOIN m8_results r ON r.id=rr.results_id
            WHERE r.cycle_db_id=%s AND p.audience='assessee'
            ORDER BY rr.revision_no DESC,p.revision_no DESC LIMIT 1""", (row['id'],)).fetchone()
        return {'run_id': state['run_id'], 'cycle_id': cycle_id,
                'owner_user_id': row['owner_user_id'], 'collection_status': row['status'],
                'close_reason': row['close_reason'],
                'collection_closed_at': row['collection_closed_at'],
                'situations': [dict(item) for item in situations],
                'pipeline': dict(pipeline) if pipeline else None,
                'c46': dict(c46) if c46 else None,
                'results': dict(results) if results else None,
                'report': dict(report) if report else None}

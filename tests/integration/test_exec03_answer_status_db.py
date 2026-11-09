import pytest
from tests.integration.test_m6_evidence_db import database

pytestmark = pytest.mark.integration


def test_answer_status_reads_closed_as_without_creating_or_replaying_material(database):
    from uuid import UUID, uuid4
    from Api.assessment_answer_status import read
    from Api import m7_clarification_repository

    factory, handoff_id = database
    with factory() as c:
        # The M6 fixture does not need M7 for its normal cases. Install the
        # existing M7 schema in this isolated owned schema before the read.
        m7_clarification_repository.ensure_schema(c)
        source = c.execute('''SELECT s.assessment_situation_id,s.id,s.status,t.turn_id,t.content_text
            FROM m5_c45_handoffs h JOIN m5_assessment_situations s ON s.id=h.assessment_situation_db_id
            JOIN m5_dialogue_turns t ON t.assessment_situation_db_id=s.id
            WHERE h.handoff_id=%s AND t.request_id='synthetic-turn' ''',
            (UUID(handoff_id),)).fetchone()
        assert source['status'] == 'closed'
        c.commit()

        def counts():
            return tuple(c.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                         for table in ('m5_dialogue_turns', 'm5_scenario_events',
                                       'm5_turn_operations', 'm5_c45_handoffs'))

        before = counts()
        key = {'assessment_situation_id': str(source['assessment_situation_id']),
               'request_id': 'synthetic-turn', 'turn_id': str(source['turn_id'])}
        accepted = read(c, **key)
        assert accepted['status'] == 'accepted'
        assert accepted['processing_status'] == 'applied'
        assert accepted['turn']['content_text'] == source['content_text']
        assert read(c, **key) == accepted
        absent = read(c, assessment_situation_id=key['assessment_situation_id'],
                      request_id='never-arrived', turn_id=str(uuid4()))
        assert absent['status'] == 'absent'
        assert absent['turn'] is None
        assert counts() == before
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE id=%s',
                         (source['id'],)).fetchone()['status'] == 'closed'

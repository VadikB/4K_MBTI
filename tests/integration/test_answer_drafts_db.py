"""Mutable drafts use real PostgreSQL, saved runtime and controlled providers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from Api import assessment_drafts as drafts
from Api import m5_scenario_runtime as runtime
from Api.m5_rule_engine import ControlledSemanticAdapter, ControlledCharacterAdapter
from tests.integration.test_m7_cycle_planner_db import active_cycle, db
from tests.integration.test_exec_fix01_clarification_db import current, database

pytestmark = pytest.mark.integration


def setup(factory):
    with factory() as c:
        _plan, shown = active_cycle(c)
        from Api.m6_repository import ensure_schema
        ensure_schema(c)
        situation_id = str(shown['decision']['assessment_situation_id'])
        return {'assessment_situation_id': situation_id, 'owner_user_id': 99}


def put(factory, identity, base, text, revision=None):
    with factory() as c:
        return drafts.save(c, **identity, slot_id=base['slot_id'], expected_version=base['version'],
                           revision=revision or str(uuid4()), text=text)


def read(factory, identity):
    with factory() as c:
        return drafts.read(c, **identity)


def test_raw_server_draft_survives_connections_and_never_creates_material(db):
    identity = setup(db)
    before = read(db, identity)
    with db() as c:
        counts = [c.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                  for table in ('m5_dialogue_turns', 'm5_turn_operations', 'm5_c45_handoffs', 'm5_cycle_time_intervals')]
    raw = '  Неотправленный ответ\nВторая строка\n  '
    saved = put(db, identity, before, raw, 'revision-1')
    assert saved['text'] == raw and saved['version'] == 1
    assert read(db, identity) == saved
    assert put(db, identity, before, raw, 'revision-1') == saved  # lost ACK
    with db() as c:
        assert counts == [c.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                          for table in ('m5_dialogue_turns', 'm5_turn_operations', 'm5_c45_handoffs', 'm5_cycle_time_intervals')]
    with pytest.raises(ValueError, match='OWNER_MISMATCH'):
        read(db, {**identity, 'owner_user_id': 98})


def test_cas_competing_tabs_and_versioned_empty_delete(db):
    identity = setup(db); base = read(db, identity)
    def writer(text):
        try: return put(db, identity, base, text)
        except ValueError as exc: return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, ['first tab', 'second tab']))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert 'DRAFT_VERSION_CONFLICT' in results
    saved = read(db, identity)
    deleted = put(db, identity, saved, '')
    assert deleted['text'] == '' and deleted['version'] == saved['version'] + 1
    with pytest.raises(ValueError, match='VERSION_CONFLICT'):
        put(db, identity, saved, saved['text'])
    assert read(db, identity)['text'] == ''


def test_accepted_turn_invalidates_old_slot_no_resurrection_and_exact_clear(db):
    identity = setup(db); base = read(db, identity)
    saved = put(db, identity, base, 'sent raw', 'sent-revision')
    request_id, turn_id = uuid4().hex, str(uuid4())
    receipt = runtime.submit_turn_detached(assessment_situation_id=identity['assessment_situation_id'],
        request_id=request_id, turn_id=turn_id, content='sent raw', connection_factory=db,
        semantic_adapter=ControlledSemanticAdapter({}), character_adapter=ControlledCharacterAdapter({}))
    assert str(receipt['turn']['turn_id']) == turn_id
    with pytest.raises(ValueError, match='SLOT_CHANGED|UNAVAILABLE'):
        put(db, identity, saved, 'late stale tab')
    with db() as c:
        drafts.consume(c, **identity, slot_id=saved['slot_id'], revision='wrong-newer-revision',
                       request_id=request_id, turn_id=turn_id)
        assert c.execute('SELECT content_text FROM assessment_answer_drafts').fetchone()['content_text'] == 'sent raw'
        drafts.consume(c, **identity, slot_id=saved['slot_id'], revision='sent-revision',
                       request_id=request_id, turn_id=turn_id)
        assert c.execute('SELECT content_text,consumed FROM assessment_answer_drafts').fetchone() == {'content_text': '', 'consumed': True}
    assert runtime.submit_turn_detached(assessment_situation_id=identity['assessment_situation_id'],
        request_id=request_id, turn_id=turn_id, content='sent raw', connection_factory=db)['turn']


@pytest.mark.parametrize('boundary', ['deadline', 'closed', 'paused'])
def test_no_restore_or_autosave_beyond_runtime_admission(db, boundary):
    identity = setup(db); base = read(db, identity)
    put(db, identity, base, 'Private unsent')
    with db() as c:
        if boundary == 'deadline':
            future = datetime.now(timezone.utc) + timedelta(days=365)
            with pytest.raises(ValueError, match='UNAVAILABLE'):
                drafts.scope(c, **identity, now=future)
        elif boundary == 'closed':
            c.execute("UPDATE m5_cycles SET status='collection_closed'")
        else:
            c.execute("UPDATE m5_cycles SET status='paused'")
    if boundary != 'deadline':
        with pytest.raises(ValueError, match='UNAVAILABLE'):
            read(db, identity)


def test_clean_schema_idempotent_and_unaccepted_cannot_clear(db):
    identity = setup(db); saved = put(db, identity, read(db, identity), 'retained')
    with db() as c:
        drafts.ensure_schema(c); drafts.ensure_schema(c)
        with pytest.raises(ValueError, match='NOT_ACCEPTED'):
            drafts.consume(c, **identity, slot_id=saved['slot_id'], revision=saved['revision'],
                           request_id='never-sent', turn_id=str(uuid4()))


def test_ordinary_and_current_m7_question_are_separate_and_replaced_question_unavailable(current):
    from tests.integration.test_exec_fix01_clarification_db import _resolve
    factory = current['factory']
    question = _resolve(current)
    identity = {'assessment_situation_id': current['as_id'], 'owner_user_id': 99}
    base = read(factory, identity)
    assert base['slot_id'] == f"clarification:{question['id']}:{question['question_turn_id']}"
    saved = put(factory, identity, base, '  exact clarification\nraw  ')
    assert read(factory, identity)['text'] == saved['text']
    # A later real C54/ASK rotates the slot; the old draft never moves with it.
    from Api.m5_scenario_runtime import build_c45
    with factory() as c:
        handoff = build_c45(c, current['as_id'], mode='interim')
    latest = _resolve(current, handoff_id=str(handoff['handoff_id']), status='ASK')
    assert latest['id'] != question['id']
    assert read(factory, identity)['text'] == ''
    with pytest.raises(ValueError, match='SLOT_CHANGED'):
        put(factory, identity, saved, 'late old question')

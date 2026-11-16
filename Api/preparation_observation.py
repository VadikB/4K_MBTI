"""Technical progress of existing operations; never a command to prepare or present."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import logging
from uuid import uuid4

from Api.database import get_connection
from Api.config import settings

logger = logging.getLogger('agent4k.preparation')
_active = ContextVar('preparation_observer', default=None)
STAGES = {
    'queued': ('Запрос принят. Ожидаем начала подготовки', 'Выполнение ещё не началось.'),
    'plan': ('Составляем план оценки', 'Определяем последовательность ситуаций для назначенной оценки.'),
    'first': ('Готовим первую ситуацию', 'Подготавливаем условие и материалы, с которых вы начнёте.'),
    'next': ('Готовим следующую ситуацию', 'Подготавливаем условие и материалы следующего задания.'),
    'checking': ('Проверяем материалы ситуации', 'Проверяем, что ситуацию можно открыть для прохождения.'),
    'answers': ('Обрабатываем сохранённые ответы', 'Подготавливаем данные для итоговых результатов.'),
    'results': ('Формируем итоговые результаты', 'Объединяем результаты по сохранённому материалу.'),
    'report': ('Собираем отчёт', 'Оформляем результаты и пояснения.'),
}
OWNERS = {
    'queued': 'Api/product_cycle_preparation_queue.py:ProductCyclePreparationQueue._claim',
    'plan': 'Api/m10_product_flow.py:prepare / Api/m7_cycle_planner.py:create_plan',
    'first': 'Api/m5_functional_generation_service.py:prepare / Api/m10_product_flow.py:_prepare_next',
    'next': 'Api/m5_functional_generation_service.py:prepare / Api/m10_product_flow.py:prepare_next_situation',
    'checking': 'Api/m5_functional_generation_service.py:test_candidate / Api/m7_cycle_planner.py:attach_functional_generated_as',
    'answers': 'Api/m10_orchestration.py:_queue_outbox/_queue_assessment; Api/m6_worker_v2.py; Api/m6_assessment_worker_v2.py',
    'results': 'Api/m6_cycle_aggregation_repository.py:create_substantive_detached; Api/m8_results.py:create_results',
    'report': 'Api/m8_results.py:create_report_detached / Api/m8_descriptive_report.py',
}


def delay_seconds():
    # Infrastructure UX setting, not methodology or worker timeout. Never later than 5min.
    return max(1, min(300, settings.preparation_delay_notice_seconds))


def ensure_schema(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS preparation_observations (
        id BIGSERIAL PRIMARY KEY, source TEXT NOT NULL, operation_id TEXT NOT NULL,
        attempt_token TEXT NOT NULL, kind TEXT NOT NULL, stage TEXT NOT NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), stage_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        heartbeat_at TIMESTAMPTZ, history_json JSONB NOT NULL DEFAULT '[]',
        delay_events TEXT[] NOT NULL DEFAULT '{}',
        scope_json JSONB NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'running', error_category TEXT,
        UNIQUE(source,operation_id,attempt_token))''')


def reference(source, operation_id):
    source = 'report' if source == 'recovery' else source
    return 'P4K-' + hashlib.sha256(f'{source}:{operation_id}'.encode()).hexdigest()[:24].upper()


def read(connection, source, operation_id):
    row = connection.execute('''SELECT * FROM preparation_observations
        WHERE source=%s AND operation_id=%s ORDER BY id DESC LIMIT 1''', (source, str(operation_id))).fetchone()
    return dict(row) if row else None


def begin(source, operation_id, attempt_token, kind, stage, *, factory=None):
    with (factory or get_connection)() as connection:
        started_at = None
        if source == 'cycle':
            current = connection.execute("SELECT status,attempt_token,created_at AT TIME ZONE current_setting('TimeZone') AS operation_started_at FROM product_cycle_preparation_operations WHERE operation_id=%s", (str(operation_id),)).fetchone()
            if not current or current['status'] != 'running' or str(current['attempt_token']) != str(attempt_token):
                raise RuntimeError('PRODUCT_CYCLE_PREPARATION_ATTEMPT_STALE')
            started_at = current['operation_started_at']
        elif source == 'report':
            current = connection.execute('''SELECT 1 FROM m10_report_claims claim JOIN m5_cycles c ON c.id=claim.cycle_db_id
                WHERE c.cycle_id=%s AND claim.token=%s AND claim.lease_until>NOW()''', (str(operation_id), attempt_token)).fetchone()
            if not current:
                raise RuntimeError('M10_REPORT_CLAIM_LOST')
        connection.execute('''INSERT INTO preparation_observations
            (source,operation_id,attempt_token,kind,stage,started_at,heartbeat_at,history_json)
            VALUES (%s,%s,%s,%s,%s,COALESCE((SELECT MIN(started_at) FROM preparation_observations WHERE source=%s AND operation_id=%s),%s,NOW()),NOW(),jsonb_build_array(jsonb_build_object('stage',%s::text,'at',NOW())))
            ON CONFLICT(source,operation_id,attempt_token) DO NOTHING''',
            (source, str(operation_id), str(attempt_token), kind, stage, source, str(operation_id), started_at, stage))
    return (source, str(operation_id), str(attempt_token), factory or get_connection, kind)


def record(observer, stage=None, *, heartbeat=False):
    if observer is None:
        return
    source, operation_id, token, factory, _kind = observer
    with factory() as connection:
        # The latest attempt owns the observation; a late callback cannot rewind it.
        fence = ''
        if source == 'cycle':
            fence = """AND EXISTS(SELECT 1 FROM product_cycle_preparation_operations op
                WHERE op.operation_id=preparation_observations.operation_id AND op.status='running'
                  AND op.attempt_token::text=preparation_observations.attempt_token)"""
        elif source == 'report':
            fence = """AND EXISTS(SELECT 1 FROM m10_report_claims claim JOIN m5_cycles c ON c.id=claim.cycle_db_id
                WHERE c.cycle_id::text=preparation_observations.operation_id AND claim.token::text=preparation_observations.attempt_token
                  AND claim.lease_until>NOW())"""
        elif source == 'sync':
            fence = "AND status='running'"
        elif source == 'recovery':
            fence = '''AND EXISTS(SELECT 1 FROM m10_processing_recoveries r
                WHERE r.id::text=preparation_observations.scope_json->>'recovery_id' AND r.status='running')'''
        row = connection.execute(f'''UPDATE preparation_observations SET
            history_json=CASE WHEN %s::text IS NOT NULL AND stage<>%s THEN history_json ||
                jsonb_build_array(jsonb_build_object('stage',%s::text,'at',NOW())) ELSE history_json END,
            stage_started_at=CASE WHEN %s::text IS NOT NULL AND stage<>%s THEN NOW() ELSE stage_started_at END,
            stage=COALESCE(%s,stage), heartbeat_at=CASE WHEN %s THEN NOW() ELSE heartbeat_at END
            WHERE source=%s AND operation_id=%s AND attempt_token=%s
              AND id=(SELECT MAX(id) FROM preparation_observations WHERE operation_id=%s AND (source=%s OR (source IN ('report','recovery') AND %s IN ('report','recovery'))))
              {fence}
            RETURNING stage,stage_started_at,delay_events''',
            (stage, stage, stage, stage, stage, stage, heartbeat, source, operation_id, token, operation_id, source, source)).fetchone()
        if row:
            # Emitted by worker heartbeat, never by a read/poll, once per stage/attempt.
            event = connection.execute('''UPDATE preparation_observations SET delay_events=array_append(delay_events,stage)
                WHERE source=%s AND operation_id=%s AND attempt_token=%s
                  AND stage_started_at <= NOW() - %s * INTERVAL '1 second'
                  AND NOT stage=ANY(delay_events) RETURNING stage''',
                (source, operation_id, token, delay_seconds())).fetchone()
            if event:
                logger.warning('preparation_delay reference=%s attempt=%s stage=%s owner=%s',
                               reference(source, operation_id), token, event['stage'], OWNERS.get(event['stage']))


@contextmanager
def observing(observer):
    saved = _active.set(observer)
    try:
        yield
    finally:
        _active.reset(saved)


def materials():
    observer = _active.get()
    progress('next' if observer and observer[4] == 'next' else 'first')


def progress(stage):
    if stage not in STAGES:
        raise ValueError('Unknown preparation observation stage')
    record(_active.get(), stage, heartbeat=True)


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def project(operation, observation=None, *, source='cycle', now=None, kind=None):
    now = _utc(now) or datetime.now(timezone.utc)
    status = operation.get('status') or 'unknown'
    kind = kind or (observation or {}).get('kind') or ('next' if (operation.get('request_json') or {}).get('kind') == 'next' else 'assessment')
    stage = (observation or {}).get('stage')
    if status == 'queued':
        stage = 'queued'
    label, explanation = STAGES.get(stage, ('Подготовка выполняется', 'Подробности этапа пока недоступны.'))
    if status in {'completed', 'ready'}:
        label, explanation = (('Отчёт готов' if kind == 'report' else 'Подготовка завершена'), 'Доступность результата определяется условиями его открытия.')
    elif status == 'failed':
        explanation = 'Не удалось завершить подготовку. ' + (label + '.' if stage in STAGES else 'Подробности этапа пока недоступны.')
    started = (_utc((observation or {}).get('started_at')) if source in {'cycle','sync'} else None) or _utc(operation.get('created_at')) or _utc((observation or {}).get('started_at'))
    changed = (_utc(operation.get('updated_at')) or started) if status == 'queued' else _utc((observation or {}).get('stage_started_at'))
    heartbeat = _utc((observation or {}).get('heartbeat_at'))
    active = status in {'queued', 'running', 'processing'}
    notice_start = changed or started
    delayed = bool(active and notice_start and (now-notice_start).total_seconds() >= delay_seconds())
    freshness = ('unconfirmed' if active and status != 'queued' and
                 (not heartbeat or (now-heartbeat).total_seconds() > 90) else 'confirmed')
    actions = ['check'] if active else []
    if operation.get('retry_allowed') is True:
        actions.append('retry')
    return {'operation_id': str(operation['operation_id']), 'kind': kind, 'status': status,
            'stage_label': label, 'explanation': explanation,
            'started_at': started.isoformat() if started else None,
            'stage_started_at': changed.isoformat() if changed else None,
            'last_progress_at': changed.isoformat() if changed else None,
            'finished_at': (_utc(operation.get('completed_at') or operation.get('updated_at')).isoformat() if status in {'completed','ready','failed'} and (operation.get('completed_at') or operation.get('updated_at')) else None),
            'read_at': now.isoformat(), 'freshness': freshness, 'delayed': delayed,
            'delay_notice_seconds': delay_seconds(), 'allowed_actions': actions,
            'reference': reference(source, operation['operation_id'])}


def attach(connection, operation, *, source='cycle', kind=None):
    if operation is None:
        return None
    operation = dict(operation)
    time_fields = ('created_at','updated_at','completed_at')
    if source == 'cycle' and any(isinstance(operation.get(key),datetime) and operation[key].tzinfo is None for key in time_fields):
        # Queue timestamps predate timestamptz. Interpret them in their DB session timezone,
        # not the browser or process timezone; never rewrite the stored row.
        normalized = connection.execute('''SELECT %s::timestamp AT TIME ZONE current_setting('TimeZone') AS created_at,
            %s::timestamp AT TIME ZONE current_setting('TimeZone') AS updated_at,
            %s::timestamp AT TIME ZONE current_setting('TimeZone') AS completed_at''',
            tuple(operation.get(key) for key in time_fields)).fetchone()
        operation.update(normalized)
    if source == 'cycle':
        from Api.product_cycle_preparation_queue import retry_allowed
        operation['retry_allowed'] = retry_allowed(operation)
    observed = read(connection, source, operation['operation_id'])
    if operation.get('status') == 'running' and operation.get('attempt_token') and observed and observed['attempt_token'] != str(operation['attempt_token']):
        observed = None
    operation['preparation'] = project(operation, observed, source=source, kind=kind)
    return operation


def report_status(connection, cycle_id):
    row = connection.execute('''SELECT p.*,c.cycle_id,c.collection_closed_at FROM m10_pipeline_runs p
        JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s''', (cycle_id,)).fetchone()
    if not row:
        return None
    operation = {**dict(row), 'operation_id': str(cycle_id), 'created_at': row['collection_closed_at']}
    ready = connection.execute("SELECT created_at FROM m8_reports WHERE id=%s AND status='ready' AND audience='assessee' AND COALESCE(c67_json->'processing'->>'status','completed')<>'failed'", (row['latest_report_id'],)).fetchone() if row.get('latest_report_id') else None
    if ready:
        operation['status'] = 'ready'
        operation['completed_at'] = ready['created_at']
    observation = connection.execute("SELECT * FROM preparation_observations WHERE source IN ('report','recovery') AND operation_id=%s ORDER BY id DESC LIMIT 1", (str(cycle_id),)).fetchone()
    public = project(operation, observation, source='report', kind='report')
    if operation['status'] == 'processing' and observation and observation['stage'] == 'answers':
        lease = connection.execute('''SELECT bool_or(status='running' AND lease_expires_at>NOW()) AS live,
            bool_or(status='queued') AS queued FROM (
                SELECT q.status,q.lease_expires_at FROM m6_processing_requests q
                JOIN m5_assessment_situations s ON s.id=q.as_db_id WHERE s.cycle_db_id=%s
                UNION ALL SELECT q.status,q.lease_expires_at FROM m6_assessment_requests q
                JOIN m5_assessment_situations s ON s.id=q.as_db_id WHERE s.cycle_db_id=%s
                UNION ALL SELECT 'queued',NULL::timestamptz FROM m7_finalization_outbox o
                JOIN m5_assessment_situations s ON s.id=o.assessment_situation_db_id
                WHERE s.cycle_db_id=%s AND o.status='pending') requests''',
            (row['cycle_db_id'],row['cycle_db_id'],row['cycle_db_id'])).fetchone()
        if lease and lease['live']:
            public['freshness'] = 'confirmed'
        elif lease and lease['queued']:
            public['stage_label'],public['explanation'] = STAGES['queued']
            public['freshness'] = 'confirmed'
    return public


@contextmanager
def synchronous(operation_id, kind, scope, *, factory=None):
    """Observe the released synchronous path without changing its HTTP contract."""
    factory = factory or get_connection
    with factory() as connection:
        previous = read(connection, 'sync', operation_id)
        if previous and previous['scope_json'] != scope:
            raise ValueError('PRODUCT_CYCLE_PREPARATION_IDEMPOTENCY_CONFLICT')
    observer = None if previous and previous['status'] == 'completed' else begin(
        'sync', operation_id, previous['attempt_token'] if previous and previous['status'] == 'running' else uuid4(), kind, 'unknown', factory=factory)
    if observer:
        with factory() as connection:
            connection.execute("UPDATE preparation_observations SET scope_json=%s::jsonb WHERE source='sync' AND operation_id=%s AND attempt_token=%s",
                               (json.dumps(scope), str(operation_id), observer[2]))
    heartbeat = start_heartbeat(observer)
    try:
        with observing(observer):
            yield
    except Exception as exc:
        if observer:
            with factory() as connection:
                connection.execute("UPDATE preparation_observations SET status='failed',error_category=%s WHERE source='sync' AND operation_id=%s AND attempt_token=%s", (type(exc).__name__,str(operation_id),observer[2]))
        raise
    else:
        if observer:
            with factory() as connection:
                connection.execute("UPDATE preparation_observations SET status='completed' WHERE source='sync' AND operation_id=%s AND attempt_token=%s", (str(operation_id),observer[2]))
    finally:
        stop_heartbeat(heartbeat)


def sync_owned(connection, operation_id, user_id):
    observed = read(connection, 'sync', operation_id)
    if not observed or observed['scope_json'].get('user_id') != user_id or observed['status'] == 'completed':
        return None
    operation = {'operation_id': str(operation_id), 'status': observed['status'], 'user_id': user_id,
                 'created_at': observed['started_at']}
    operation['preparation'] = project(operation, observed, source='sync')
    return operation


def sync_for_cycle(connection, cycle_id, user_id):
    row = connection.execute("""SELECT * FROM preparation_observations WHERE source='sync'
        AND scope_json->>'cycle_id'=%s AND scope_json->>'user_id'=%s AND status IN ('running','failed')
        ORDER BY id DESC LIMIT 1""", (str(cycle_id), str(user_id))).fetchone()
    if not row:
        return None
    return sync_owned(connection, row['operation_id'], user_id)


def notice_delays(connection):
    """Worker-side observation only. A status GET never emits or writes an event."""
    has_cycle_queue = connection.execute("SELECT to_regclass(current_schema()||'.product_cycle_preparation_operations') AS relation").fetchone()
    cycle_condition = '''source='cycle' AND EXISTS(SELECT 1 FROM product_cycle_preparation_operations o
        WHERE o.operation_id=p.operation_id AND o.status IN ('queued','running'))''' if has_cycle_queue and has_cycle_queue['relation'] else 'FALSE'
    rows = connection.execute(f'''UPDATE preparation_observations p
        SET delay_events=array_append(delay_events,stage)
        WHERE id=(SELECT MAX(q.id) FROM preparation_observations q WHERE q.source=p.source AND q.operation_id=p.operation_id)
          AND stage_started_at<=NOW() - %s * INTERVAL '1 second' AND NOT stage=ANY(delay_events)
          AND (({cycle_condition})
            OR (source='report' AND EXISTS(SELECT 1 FROM m10_pipeline_runs r JOIN m5_cycles c ON c.id=r.cycle_db_id
                WHERE c.cycle_id::text=p.operation_id AND r.status='processing'))
            OR (source='sync' AND p.status='running')) RETURNING source,operation_id,attempt_token,stage''',
        (delay_seconds(),)).fetchall()
    for row in rows:
        logger.warning('preparation_delay reference=%s attempt=%s stage=%s owner=%s',
            reference(row['source'],row['operation_id']),row['attempt_token'],row['stage'],OWNERS.get(row['stage']))


def start_heartbeat(observer):
    """Evidence that the request worker is alive, independent of stage advancement."""
    if observer is None:
        return None
    import threading
    stop = threading.Event()
    def beat():
        while not stop.wait(30):
            try:
                record(observer, heartbeat=True)
            except Exception:
                logger.exception('preparation heartbeat unavailable reference=%s', reference(observer[0],observer[1]))
    thread = threading.Thread(target=beat,name='preparation-observation-heartbeat',daemon=True)
    thread.start()
    return stop,thread


def stop_heartbeat(heartbeat):
    if heartbeat:
        heartbeat[0].set()
        heartbeat[1].join(timeout=1)

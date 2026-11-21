"""Ограниченное чтение сохранённой подготовки следующей AS для платформы."""
from Api import preparation_observation as observation
from Api.product_cycle_preparation_queue import PUBLIC_FAILURE, PUBLIC_FAILURES_BY_PREFIX
from Api.public_origin import build_public_link


_PAGE_SIZE = 50
_REFERENCE_SQL = "('P4K-' || upper(substr(encode(sha256(convert_to('cycle:' || op.operation_id, 'UTF8')), 'hex'), 1, 24)))"

# Область берётся из исходного Cycle. Текущее назначение пользователя и текущая
# редакция плана не участвуют в поиске. Номер операции вычисляется так же, как у
# участника, администратора и в закрытой инженерной диагностике.
_SELECT = f"""
    SELECT op.id, {_REFERENCE_SQL} AS reference, op.status,
           op.created_at AT TIME ZONE current_setting('TimeZone') AS created_at,
           op.updated_at AT TIME ZONE current_setting('TimeZone') AS updated_at,
           op.completed_at AT TIME ZONE current_setting('TimeZone') AS completed_at,
           CASE WHEN split_part(op.error_message, ':', 1) = ANY(%(failure_prefixes)s)
                THEN split_part(op.error_message, ':', 1) END AS failure_prefix,
           a.id AS assignment_id, a.organization_id,
           CASE WHEN jsonb_typeof(op.request_json #> '{{next_preparation_scope,after_position_no}}') = 'number'
                THEN op.request_json #> '{{next_preparation_scope,after_position_no}}' END AS previous_position,
           seen.stage, seen.started_at,
           seen.stage_started_at, seen.heartbeat_at,
           (op.attempt_token::text IS NOT DISTINCT FROM seen.attempt_token) AS same_attempt,
           ready.created_at AS result_at
    FROM product_cycle_preparation_operations op
    JOIN m5_cycles c ON c.cycle_id::text = op.request_json->>'cycle_id'
                     AND c.owner_user_id = op.user_id AND c.usage_scope = 'assessment'
    JOIN organization_assessment_assignments a ON a.id = c.assignment_id
                                              AND a.recipient_user_id = op.user_id
                                              AND a.organization_id = c.organization_id
    LEFT JOIN LATERAL (
        SELECT stage, started_at, stage_started_at, heartbeat_at, attempt_token
        FROM preparation_observations
        WHERE source = 'cycle' AND operation_id = op.operation_id
        ORDER BY id DESC LIMIT 1
    ) seen ON TRUE
    LEFT JOIN LATERAL (
        SELECT attached.created_at
        FROM m7_next_as_requests next_access
        JOIN m7_route_decisions decision ON decision.id = next_access.decision_id
            AND decision.cycle_db_id = c.id AND decision.status = 'SELECTED'
        JOIN m7_route_assignments attached ON attached.decision_id = decision.id
        JOIN m5_assessment_situations situation ON situation.id = attached.assessment_situation_db_id
            AND situation.cycle_db_id = c.id
        WHERE next_access.cycle_db_id = c.id
          AND next_access.key = 'product-next:' ||
              COALESCE(op.request_json->>'preparation_key', op.request_json->>'idempotency_key')
          AND situation.snapshot_json #> '{{admission,admitted}}' = 'true'::jsonb
          AND attached.created_at >= (op.created_at AT TIME ZONE current_setting('TimeZone'))
    ) ready ON TRUE
    WHERE op.request_json->>'kind' = 'next'
"""


def _project(row):
    stage = row["stage"] if row["stage"] in observation.STAGES else None
    heartbeat = row["heartbeat_at"] if row["status"] != "running" or row["same_attempt"] else None
    fact = observation.project(
        {**row, "operation_id": row["reference"]},
        {"stage": stage, "started_at": row["started_at"], "stage_started_at": row["stage_started_at"],
         "heartbeat_at": heartbeat},
        kind="next",
    )
    result_at = row["result_at"].isoformat() if row["result_at"] else None
    failure = PUBLIC_FAILURES_BY_PREFIX.get(row["failure_prefix"], PUBLIC_FAILURE)["code"] if row["status"] == "failed" else None
    if result_at:
        state = "result_confirmed"
    elif failure == "ASSESSMENT_AS_NOT_ADMITTED":
        state = "admission_denied"
    elif row["status"] == "failed":
        state = "failed"
    elif row["status"] in {"queued", "running"} and fact["freshness"] == "confirmed":
        state = "waiting"
    else:
        state = "unconfirmed"

    last_confirmed_at = result_at or fact["finished_at"] or (
        heartbeat.isoformat() if heartbeat else None) or fact["last_progress_at"] or fact["started_at"]
    if row["status"] == "queued":
        stage = "queued"
    return {
        "reference": row["reference"],
        "organization_id": row["organization_id"],
        "assignment_id": row["assignment_id"],
        "previous_position": row["previous_position"],
        "state": state,
        "operation_status": row["status"],
        "source": "product_cycle_preparation_operations",
        "stage_source": "preparation_observations" if stage and row["status"] != "queued" else None,
        "stage": stage,
        "stage_label": observation.STAGES[stage][0] if stage else None,
        "started_at": fact["started_at"],
        "stage_at": fact["stage_started_at"] if stage else None,
        "last_confirmed_at": last_confirmed_at,
        "read_at": fact["read_at"],
        "failure_class": failure,
        "result_confirmed_at": result_at,
        "result_source": "m7_route_assignments" if result_at else None,
    }


def list_failures(connection, *, before=None, organization_id=None):
    rows = connection.execute(
        _SELECT + """
            AND op.status = 'failed' AND ready.created_at IS NULL
            AND (%(before)s::bigint IS NULL OR op.id < %(before)s)
            AND (%(organization_id)s::bigint IS NULL OR a.organization_id = %(organization_id)s)
            ORDER BY op.id DESC LIMIT %(limit)s
        """,
        {"failure_prefixes": list(PUBLIC_FAILURES_BY_PREFIX), "before": before,
         "organization_id": organization_id, "limit": _PAGE_SIZE + 1},
    ).fetchall()
    return {
        "items": [_project(row) for row in rows[:_PAGE_SIZE]],
        "next_before": rows[_PAGE_SIZE - 1]["id"] if len(rows) > _PAGE_SIZE else None,
    }


def read(connection, reference):
    row = connection.execute(
        _SELECT + f" AND {_REFERENCE_SQL} = %(reference)s",
        {"failure_prefixes": list(PUBLIC_FAILURES_BY_PREFIX), "reference": reference},
    ).fetchone()
    return _project(row) if row else None


def handoff(problem, *, origin, mode, version):
    """Собрать пакет из разрешённых полей. Передача выполняется оператором."""
    organization_url = build_public_link(origin, {"screen": "admin-organizations",
                                                  "org": str(problem["organization_id"])}, mode=mode)
    lines = [
        "Подготовка следующей ситуации",
        f"Контур: {mode} · {origin}",
        f"Версия продукта при чтении: {version}",
        f"Организация: #{problem['organization_id']} · {organization_url}",
        f"Поколение назначения: #{problem['assignment_id']}",
        f"Номер подготовки: {problem['reference']}",
        f"Последний этап: {problem['stage_label'] or 'нет подтверждённых сведений'}",
        f"Время подтверждённого факта: {problem['last_confirmed_at'] or 'нет подтверждённых сведений'}",
    ]
    if problem["failure_class"]:
        lines.append(f"Класс отказа: {problem['failure_class']}")
    return "\n".join(lines)

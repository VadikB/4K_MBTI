"""Read-only platform support projection of one Cycle and its saved M8 publications."""
from uuid import UUID

from Api import m8_report_access, m8_results, preparation_observation
from Api.m10_orchestration import RECOVERABLE_STAGES

_PAGE_SIZE = 50
_STAGE_LABELS = {
    "evidence_enqueue": "Обработка ответов",
    "evidence_queued": "Обработка ответов",
    "assessment_queued": "Оценивание сохранённых ответов",
    "admission_processing_failed": "Обработка результатов оценивания",
    "report_failed": "Сборка отчёта",
    "report_ready": "Отчёт сохранён",
    "processing_failed": "Итоговая обработка",
    "recovery_queued": "Восстановление в очереди",
    "recovery_failed": "Инженерное восстановление",
    "recovered_report_ready": "Отчёт сохранён после восстановления",
}
_SOURCE = """
    SELECT cycle.id,cycle.cycle_id,cycle.organization_id,cycle.collection_closed_at,
           pipeline.status AS pipeline_status,pipeline.stage AS pipeline_stage,
           pipeline.updated_at AS pipeline_at,revision.revision_no AS pipeline_revision,
           observed.stage AS observed_stage,observed.stage_started_at AS observed_at,
           results.id AS results_revision_id,results.created_at AS results_at,
           report.id AS report_id,report.status AS report_status,publication.revision_no AS report_revision,
           publication.result_revision_id AS report_results_revision_id,report.can_open,publication.created_at AS report_at,
           report.c67_json->'partial_result' AS report_partial_result,
           jsonb_typeof(report.c67_json->'skills')='array'
             AND NOT jsonb_path_exists(report.c67_json,
               '$.skills[*] ? (!exists(@.outcome) || @.outcome != "no_result")') AS no_skill_result,
           statement_timestamp() AS read_at
    FROM m5_cycles cycle
    LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
    LEFT JOIN LATERAL (
        SELECT revision_no FROM m10_pipeline_revisions WHERE cycle_db_id=cycle.id
        ORDER BY revision_no DESC LIMIT 1
    ) revision ON TRUE
    LEFT JOIN LATERAL (
        SELECT stage,stage_started_at FROM preparation_observations
        WHERE source IN ('report','recovery') AND operation_id=cycle.cycle_id::text
        ORDER BY id DESC LIMIT 1
    ) observed ON TRUE
    LEFT JOIN LATERAL (
        SELECT rr.id,rr.created_at FROM m8_results r JOIN m8_result_revisions rr ON rr.results_id=r.id
        WHERE r.cycle_db_id=cycle.id ORDER BY rr.revision_no DESC LIMIT 1
    ) results ON TRUE
    LEFT JOIN LATERAL ({report_selection}) report ON TRUE
    LEFT JOIN m8_reports publication ON publication.id=report.id
    WHERE cycle.usage_scope='assessment' AND cycle.collection_closed_at IS NOT NULL
      AND cycle.organization_id IS NOT NULL
"""
_LAST_STAGE_AT = "GREATEST(cycle.collection_closed_at, pipeline.updated_at, observed.stage_started_at)"


def _project(row, *, requested_report=None):
    processing_at = max(value for value in (
        row["collection_closed_at"], row["pipeline_at"], row["observed_at"],
    ) if value is not None)
    pipeline_stage = row["pipeline_stage"]
    observed = preparation_observation.STAGES.get(row["observed_stage"])
    if row["can_open"]:
        state = row["report_status"]
        if row["no_skill_result"]:
            state = "no_result"
        elif state == "ready" and m8_results.is_limited_report(state, row["report_partial_result"]):
            state = "limited"
        stage = "Отчёт сохранён"
    elif row["pipeline_status"] == "failed" or row["report_id"]:
        state = "failed"
        stage = _STAGE_LABELS.get(pipeline_stage) or (observed[0] if observed else "Итоговая обработка")
    elif row["pipeline_status"] == "processing":
        elapsed = (row["read_at"] - processing_at).total_seconds()
        state = "delayed" if elapsed >= preparation_observation.delay_seconds() else "waiting"
        stage = (observed[0] if observed and row["observed_at"] == processing_at
                 else _STAGE_LABELS.get(pipeline_stage, "Итоговая обработка"))
    else:
        state = "unconfirmed"
        stage = "Results сохранены" if row["results_revision_id"] else "Сбор ответов завершён"
    return {
        "kind": "report",
        "reference": "RPT-" + str(row["cycle_id"]).upper(),
        "cycle_id": row["cycle_id"],
        "organization_id": row["organization_id"],
        "state": state,
        "stage_label": stage,
        "collection_closed_at": row["collection_closed_at"],
        "last_confirmed_at": max(value for value in (
            processing_at, row["results_at"], row["report_at"],
        ) if value is not None),
        "read_at": row["read_at"],
        "results_status": ("saved" if row["results_revision_id"] else
                           "failed" if state == "failed" else "not_confirmed"),
        "results_revision_id": row["results_revision_id"],
        "report_status": row["report_status"] or ("not_found" if requested_report else "not_created"),
        "report_id": row["report_id"],
        "requested_report_id": requested_report,
        "report_revision": row["report_revision"],
        "report_results_revision_id": row["report_results_revision_id"],
        "report_openable": bool(row["can_open"]),
        "preparation_reference": preparation_observation.reference("report", row["cycle_id"]),
    }


def list_problems(connection, *, before=None, organization_id=None):
    rows = connection.execute(_SOURCE.format(report_selection=m8_report_access.CUSTOMER_REPORT_FOR_CYCLE_SQL) + f"""
        AND NOT COALESCE(report.can_open,FALSE)
        AND (pipeline.status='failed' OR report.id IS NOT NULL OR
            (pipeline.status='processing' AND
                {_LAST_STAGE_AT} <= statement_timestamp() - %(delay)s * INTERVAL '1 second'))
        AND (%(before)s::bigint IS NULL OR cycle.id < %(before)s)
        AND (%(organization)s::bigint IS NULL OR cycle.organization_id = %(organization)s)
        ORDER BY cycle.id DESC LIMIT %(limit)s
    """, {"before": before, "organization": organization_id, "limit": _PAGE_SIZE + 1,
          "delay": preparation_observation.delay_seconds()}).fetchall()
    return {
        "items": [_project(row) for row in rows[:_PAGE_SIZE]],
        "next_before": rows[_PAGE_SIZE - 1]["id"] if len(rows) > _PAGE_SIZE else None,
    }


def read(connection, cycle_id: UUID, *, report_id: UUID | None, user_id: int, can_recover: bool):
    selection = (m8_report_access.CUSTOMER_REPORT_SELECTION_SQL + " AND p.id=%(report_id)s"
                 if report_id else m8_report_access.CUSTOMER_REPORT_FOR_CYCLE_SQL)
    row = connection.execute(_SOURCE.format(report_selection=selection) + " AND cycle.cycle_id=%(cycle_id)s",
                             {"cycle_id": cycle_id, "report_id": report_id}).fetchone()
    if row is None:
        return None
    result = _project(row, requested_report=report_id)
    result["report_access"] = ("allowed" if m8_report_access.customer_can_read_report(
        connection, report_id=row["report_id"], user_id=user_id) else "denied") if row["can_open"] else "unavailable"
    result["recovery_revision"] = (
        row["pipeline_revision"] if can_recover and report_id is None and not row["can_open"]
        and row["pipeline_status"] == "failed" and row["pipeline_stage"] in RECOVERABLE_STAGES else None
    )
    return result


def handoff(problem, *, mode, origin, version):
    return "\n".join([
        "Проверка подготовки отчёта",
        f"Контур: {mode} · {origin}",
        f"Версия продукта при чтении: {version}",
        f"Организация: #{problem['organization_id']}",
        f"Cycle: {problem['cycle_id']}",
        f"Номер подготовки: {problem['preparation_reference']}",
        f"Этап: {problem['stage_label']} · {problem['state']}",
        f"Results: {problem['results_status']} · {problem['results_revision_id'] or '—'}",
        f"Report: {problem['report_status']} · {problem['report_id'] or problem['requested_report_id'] or '—'}",
        f"Редакция Report: {problem['report_revision'] or '—'}",
        f"Results этой редакции: {problem['report_results_revision_id'] or '—'}",
        f"Последний подтверждённый факт: {problem['last_confirmed_at'].isoformat()}",
        f"Время чтения: {problem['read_at'].isoformat()}",
    ])

"""Role-safe processing facts for the exact Cycle and its current saved answer."""

# Select only the current route position. Legacy Cycles without a route use their
# last situation, as in the participant runtime. C-45 records the exact Turn IDs
# accepted as input, including when the boundary ends at an event.
_INTERIM_FAILURE_FOR_CYCLE_SQL = """
    SELECT answer.turn_id::text AS failed_turn_id
    FROM m5_cycles cycle
    JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
    JOIN m5_assessment_situations situation ON situation.cycle_db_id=cycle.id
    JOIN LATERAL (
        SELECT turn_id, sequence_no FROM m5_dialogue_turns
        WHERE assessment_situation_db_id=situation.id AND speaker_type='assessee'
        ORDER BY sequence_no DESC LIMIT 1
    ) answer ON TRUE
    JOIN LATERAL (
        SELECT handoff_id, boundary_sequence, envelope_json FROM m5_c45_handoffs
        WHERE assessment_situation_db_id=situation.id AND mode='interim'
        ORDER BY boundary_sequence DESC LIMIT 1
    ) handoff ON answer.sequence_no<=handoff.boundary_sequence
        AND (handoff.envelope_json->'boundary'->'turn_ids') ? answer.turn_id::text
    JOIN LATERAL (
        SELECT id, status FROM m6_processing_requests
        WHERE as_db_id=situation.id AND handoff_id=handoff.handoff_id AND mode='interim'
        ORDER BY created_at DESC, id DESC LIMIT 1
    ) evidence ON TRUE
    LEFT JOIN LATERAL (
        SELECT request.status FROM m6_analysis_revisions revision
        JOIN m6_assessment_requests request ON request.evidence_revision_id=revision.id
        WHERE revision.request_id=evidence.id AND request.as_db_id=situation.id AND request.mode='interim'
        ORDER BY request.created_at DESC, request.id DESC LIMIT 1
    ) assessment ON TRUE
    WHERE cycle.cycle_id=%s
      AND cycle.collection_closed_at IS NULL
      AND cycle.status IN ('active','paused','interrupted')
      AND situation.status IN ('active','scenario_ended')
      AND situation.id=CASE WHEN EXISTS (
          SELECT 1 FROM m7_route_positions WHERE cycle_db_id=cycle.id
      ) THEN (
          SELECT current_as_db_id FROM m7_route_positions
          WHERE cycle_db_id=cycle.id AND state IN ('not_presented','in_progress','awaiting_replacement')
            AND current_as_db_id IS NOT NULL
          ORDER BY position_no LIMIT 1
      ) ELSE (
          SELECT id FROM m5_assessment_situations WHERE cycle_db_id=cycle.id ORDER BY id DESC LIMIT 1
      ) END
      AND pipeline.status='failed' AND pipeline.stage='processing_failed'
      AND ((pipeline.error_code='M6_EVIDENCE_FAILED' AND evidence.status='failed')
        OR (pipeline.error_code='M6_ASSESSMENT_FAILED' AND assessment.status='failed'))
"""


def read_interim_failed_turn_id(connection, cycle: dict) -> str | None:
    # Only a failed interim pipeline needs to look up the saved C-45 and M6 requests.
    if (
        not cycle.get("cycle_id")
        or cycle.get("collection_closed_at") is not None
        or cycle.get("cycle_status") not in {"active", "paused", "interrupted"}
        or cycle.get("pipeline_status") != "failed"
        or cycle.get("pipeline_stage") != "processing_failed"
        or cycle.get("pipeline_error_code") not in {"M6_EVIDENCE_FAILED", "M6_ASSESSMENT_FAILED"}
    ):
        return None
    answer = connection.execute(_INTERIM_FAILURE_FOR_CYCLE_SQL, (cycle["cycle_id"],)).fetchone()
    return answer["failed_turn_id"] if answer else None


def failure_stage(*, collection_closed_at, cycle_status, pipeline_status, pipeline_stage, failed_turn_id=None):
    if failed_turn_id:
        return "answer"
    if pipeline_status == "failed" and collection_closed_at is not None:
        if pipeline_stage == "report_failed":
            return "report"
        if pipeline_stage == "calculation_failed":
            return "calculation"
    if pipeline_status == "failed" or cycle_status == "failed":
        return "unknown"
    return None


PARTICIPANT_MESSAGES = {
    "answer": "Ответ сохранён, но обработать его не удалось. Отправлять ответ повторно не нужно. Обратитесь к администратору оценки.",
    "report": "Прохождение завершено. Не удалось сформировать итоговый отчёт.",
    "calculation": "Не удалось рассчитать итоговый результат",
    "unknown": "Произошла ошибка обработки. Подробности пока недоступны",
}


def read_processing_status(connection, cycle_id: str) -> tuple[dict | None, str | None, str | None]:
    row = connection.execute("""
        SELECT cycle.cycle_id, cycle.status AS cycle_status, cycle.collection_closed_at,
               pipeline.status AS pipeline_status, pipeline.stage AS pipeline_stage,
               pipeline.error_code AS pipeline_error_code, pipeline.latest_report_id
        FROM m5_cycles cycle
        LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
        WHERE cycle.cycle_id=%s
    """, (cycle_id,)).fetchone()
    if not row:
        return None, None, None
    failed_turn_id = read_interim_failed_turn_id(connection, row)
    pipeline = {
        "status": row["pipeline_status"], "stage": row["pipeline_stage"],
        "error_code": row["pipeline_error_code"], "latest_report_id": row["latest_report_id"],
    } if row["pipeline_status"] else None
    failure = failure_stage(collection_closed_at=row["collection_closed_at"], cycle_status=row["cycle_status"],
                            pipeline_status=row["pipeline_status"], pipeline_stage=row["pipeline_stage"],
                            failed_turn_id=failed_turn_id)
    return pipeline, failure, failed_turn_id

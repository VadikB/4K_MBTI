"""Role-safe processing facts for the exact Cycle and its current saved answer."""

# Select only the current route position. Legacy Cycles without a route use their
# last situation, as in the participant runtime. C-45 records the exact Turn IDs
# accepted as input, including when the boundary ends at an event.
INTERIM_FAILURE_FOR_CYCLE_SQL = """
    SELECT answer.turn_id
    FROM m5_assessment_situations situation
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
    WHERE situation.cycle_db_id=cycle.id
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
    row = connection.execute(f"""
        SELECT cycle.status AS cycle_status, cycle.collection_closed_at,
               pipeline.status, pipeline.stage, pipeline.error_code, pipeline.latest_report_id,
               interim.turn_id::text AS failed_turn_id
        FROM m5_cycles cycle
        LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
        LEFT JOIN LATERAL ({INTERIM_FAILURE_FOR_CYCLE_SQL}) interim ON TRUE
        WHERE cycle.cycle_id=%s
    """, (cycle_id,)).fetchone()
    if not row:
        return None, None, None
    pipeline = {key: row[key] for key in ("status", "stage", "error_code", "latest_report_id")} if row["status"] else None
    failure = failure_stage(collection_closed_at=row["collection_closed_at"], cycle_status=row["cycle_status"],
                            pipeline_status=row["status"], pipeline_stage=row["stage"],
                            failed_turn_id=row["failed_turn_id"])
    return pipeline, failure, row["failed_turn_id"]

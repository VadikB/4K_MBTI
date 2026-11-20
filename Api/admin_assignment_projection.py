"""Shared read-only assignment lineage for admin rows and questionnaire summaries."""

PREPARATION_JOINS_SQL = """
LEFT JOIN LATERAL (
    SELECT runtime.id,runtime.cycle_id,runtime.status,runtime.personalized_profile_id,
           runtime.collection_closed_at
    FROM m5_cycles runtime
    WHERE runtime.owner_user_id=assignment.recipient_user_id
      AND runtime.organization_id=assignment.organization_id
      AND runtime.assignment_id=assignment.id
      AND runtime.usage_scope='assessment'
    ORDER BY runtime.created_at DESC,runtime.id DESC
    LIMIT 1
) cycle ON TRUE
LEFT JOIN LATERAL (
    SELECT profile.id
    FROM assessment_personalized_profiles profile
    JOIN questionnaire_response_revisions revision
      ON revision.id=binding.questionnaire_revision_id
     AND revision.organization_context_version_id=profile.organization_context_version_id
    WHERE profile.user_id=assignment.recipient_user_id
      AND profile.organization_id=assignment.organization_id
      AND profile.assessment_configuration_id=binding.assessment_configuration_id
      AND profile.role_profile_version_id=binding.role_profile_version_id
      AND profile.status='ready'
      AND (profile.id=cycle.personalized_profile_id OR (cycle.id IS NULL AND EXISTS (
          SELECT 1 FROM (
                SELECT * FROM participant_acquaintance_confirmations
                WHERE user_id=assignment.recipient_user_id
                  AND organization_id=assignment.organization_id
                  AND assignment_ref=assignment.assignment_ref
                  AND questionnaire_revision_id=binding.questionnaire_revision_id
                ORDER BY confirmed_at DESC,id DESC LIMIT 1
            ) confirmation
          WHERE confirmation.user_id=assignment.recipient_user_id
            AND confirmation.organization_id=assignment.organization_id
            AND confirmation.assignment_ref=assignment.assignment_ref
            AND confirmation.questionnaire_revision_id=binding.questionnaire_revision_id
            AND confirmation.personalized_profile_id=profile.id
      )))
    ORDER BY profile.frozen_at DESC, profile.id DESC
    LIMIT 1
) profile ON TRUE
LEFT JOIN LATERAL (
    SELECT job.operation_id,job.status
    FROM assessment_preparation_jobs job
    WHERE job.user_id=assignment.recipient_user_id
      AND job.personalized_profile_id=profile.id
      -- A legacy job has no assignment ID. Shared sources across generations
      -- cannot prove which assignment owns it; keep the operation readable by ID.
      AND NOT EXISTS (
          SELECT 1 FROM organization_assessment_assignments other_assignment
          JOIN organization_assessment_source_bindings other_binding
            ON other_binding.assignment_id=other_assignment.id
          WHERE other_assignment.id<>assignment.id
            AND other_assignment.recipient_user_id=assignment.recipient_user_id
            AND other_assignment.organization_id=assignment.organization_id
            AND other_binding.questionnaire_revision_id=binding.questionnaire_revision_id
            AND other_binding.assessment_configuration_id=binding.assessment_configuration_id
            AND other_binding.role_profile_version_id=binding.role_profile_version_id
      )
    ORDER BY job.created_at DESC,job.id DESC
    LIMIT 1
) preparation ON TRUE
LEFT JOIN LATERAL (
    SELECT job.operation_id,job.status
    FROM product_cycle_preparation_operations job
    WHERE job.user_id=assignment.recipient_user_id
      AND job.request_json->>'personalized_profile_id'=profile.id::text
      AND job.request_json->>'organization_id'=assignment.organization_id::text
      AND job.request_json->>'assignment_ref'=assignment.assignment_ref
      AND job.request_json->>'questionnaire_revision_id'=binding.questionnaire_revision_id::text
      AND (job.request_json->>'assignment_id'=assignment.id::text
           OR (NOT job.request_json ? 'assignment_id' AND job.status='completed'
               AND job.result_json->'plan'->>'cycle_id'=cycle.cycle_id::text))
    ORDER BY job.created_at DESC,job.id DESC
    LIMIT 1
) product_preparation ON TRUE
"""

ADMIN_ASSIGNMENT_STAGES_SQL = """
SELECT assignment.organization_id, assignment.recipient_user_id,
       assignment.id AS assignment_id, assignment.assignment_ref,
       assignment.status AS assignment_status, assignment.created_at AS assignment_created_at,
       assignment.revoked_at,
       acquaintance.status AS acquaintance_status,
       COALESCE(product_preparation.operation_id,preparation.operation_id) AS preparation_operation_id,
       COALESCE(product_preparation.status,preparation.status) AS preparation_status,
       cycle.cycle_id, cycle.status AS cycle_status,
       EXISTS (SELECT 1 FROM m5_assessment_situations first_situation
               WHERE first_situation.cycle_db_id=cycle.id
                 AND first_situation.status='admitted') AS admitted_situation,
       plan.status AS plan_status,
       COALESCE(plan_progress.planned_positions, 0) AS planned_positions,
       COALESCE(plan_progress.completed_positions, 0) AS completed_positions,
       result_revision.payload_json AS results_payload,
       pipeline.status AS pipeline_status,
       CASE WHEN ready_report.can_open AND cycle.collection_closed_at IS NOT NULL
            THEN ready_report.id END AS report_id,
       COALESCE(ready_report.can_open AND cycle.collection_closed_at IS NOT NULL,FALSE) AS report_ready,
       COALESCE(ready_report.can_open AND cycle.collection_closed_at IS NOT NULL,FALSE) AS report_access,
       'customer' AS report_access_kind
FROM organization_assessment_assignments assignment
JOIN LATERAL (
    SELECT b.* FROM organization_assessment_source_bindings b
    WHERE b.assignment_id=assignment.id ORDER BY b.id DESC LIMIT 1
) binding ON TRUE
""" + PREPARATION_JOINS_SQL + """LEFT JOIN LATERAL (
    SELECT report.id,
           report.status IN ('ready','limited','no_result')
             AND COALESCE(report.c67_json->'processing'->>'status','') <> 'failed' AS can_open
    FROM m8_results result
    JOIN m8_result_revisions revision ON revision.results_id=result.id
    JOIN m8_reports report ON report.result_revision_id=revision.id
    WHERE result.cycle_db_id=cycle.id AND report.audience='assessee'
    ORDER BY (report.id=(SELECT published.report_id FROM m8_published_reports published
                         WHERE published.cycle_db_id=cycle.id)) DESC,
             revision.revision_no DESC,report.revision_no DESC
    LIMIT 1
) ready_report ON TRUE
LEFT JOIN m7_cycle_plans plan ON plan.cycle_db_id=cycle.id
LEFT JOIN LATERAL (
    SELECT
        COALESCE(jsonb_array_length(revision.content_json->'route'), 0)::int AS planned_positions,
        (
            SELECT COUNT(*)::int
            FROM m5_assessment_situations situation
            WHERE situation.cycle_db_id=cycle.id
              AND situation.status='closed'
              AND NOT EXISTS (
                  SELECT 1 FROM m7_route_position_as_history history
                  WHERE history.assessment_situation_db_id=situation.id
                    AND history.disposition='replaced'
              )
        ) AS completed_positions
    FROM m7_plan_revisions revision
    WHERE revision.plan_id=plan.id
    ORDER BY revision.revision_no DESC
    LIMIT 1
) plan_progress ON TRUE
LEFT JOIN LATERAL (
    SELECT revision.payload_json
    FROM m8_results result
    JOIN m8_result_revisions revision ON revision.results_id=result.id
    WHERE result.cycle_db_id=cycle.id
    ORDER BY revision.revision_no DESC
    LIMIT 1
) result_revision ON TRUE
LEFT JOIN LATERAL (
    SELECT run.status
    FROM m10_pipeline_runs run
    WHERE run.cycle_db_id=cycle.id
    ORDER BY run.updated_at DESC
    LIMIT 1
) pipeline ON TRUE
LEFT JOIN participant_acquaintance_states acquaintance
  ON acquaintance.user_id=assignment.recipient_user_id
 AND acquaintance.organization_id=assignment.organization_id
 AND acquaintance.assignment_ref=assignment.assignment_ref
WHERE assignment.organization_id=ANY(%s)
ORDER BY assignment.id DESC
"""


def preparation_for_assignment(connection, *, assignment_id: int) -> dict:
    return dict(connection.execute(
        """SELECT COALESCE(product_preparation.operation_id,preparation.operation_id) AS operation_id,
                  COALESCE(product_preparation.status,preparation.status) AS status
           FROM organization_assessment_assignments assignment
           JOIN LATERAL (
               SELECT b.* FROM organization_assessment_source_bindings b
               WHERE b.assignment_id=assignment.id ORDER BY b.id DESC LIMIT 1
           ) binding ON TRUE
        """ + PREPARATION_JOINS_SQL + " WHERE assignment.id=%s",
        (assignment_id,),
    ).fetchone() or {})

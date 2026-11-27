"""Shared read-only assignment lineage for admin rows and questionnaire summaries."""

from Api.assessment_assignment_cancellation import UNBOUND_ASSIGNMENT_CYCLE_SQL
from Api.assessment_processing_status import INTERIM_FAILURE_FOR_CYCLE_SQL
from Api.assessment_assignment_sources import CONFIRMATION_ASSIGNMENT_SCOPE_SQL
from Api.m8_report_access import CUSTOMER_REPORT_FOR_CYCLE_SQL

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
    SELECT profile.id, profile.status
    FROM assessment_personalized_profiles profile
    JOIN questionnaire_response_revisions revision
      ON revision.id=binding.questionnaire_revision_id
     AND revision.organization_context_version_id=profile.organization_context_version_id
    WHERE profile.user_id=assignment.recipient_user_id
      AND profile.organization_id=assignment.organization_id
      AND profile.assessment_configuration_id=binding.assessment_configuration_id
      AND profile.role_profile_version_id=binding.role_profile_version_id
      AND profile.frozen_at IS NOT NULL
      AND (profile.id=cycle.personalized_profile_id OR (cycle.id IS NULL AND EXISTS (
          SELECT 1 FROM (
                SELECT * FROM participant_acquaintance_confirmations confirmation
                WHERE user_id=assignment.recipient_user_id
                  AND organization_id=assignment.organization_id
                  AND assignment_ref=assignment.assignment_ref
                  AND questionnaire_revision_id=binding.questionnaire_revision_id
                  AND """ + CONFIRMATION_ASSIGNMENT_SCOPE_SQL + """
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
      AND profile.status='ready'
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
      AND profile.status='ready'
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

ADMIN_ASSIGNMENT_STAGES_SQL = f"""
SELECT assignment.organization_id, assignment.recipient_user_id,
       assignment.id AS assignment_id, assignment.assignment_ref,
       assignment.status AS assignment_status, assignment.created_at AS assignment_created_at,
       assignment.revoked_at,
       (assignment.status='active' AND assignment.revoked_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM m5_cycles started_cycle
                        WHERE started_cycle.assignment_id=assignment.id
                          AND (started_cycle.started_at IS NOT NULL OR started_cycle.status<>'prepared'))
        AND (EXISTS (SELECT 1 FROM m5_cycles linked_cycle WHERE linked_cycle.assignment_id=assignment.id)
             OR NOT EXISTS ({UNBOUND_ASSIGNMENT_CYCLE_SQL}))) AS can_cancel,
       acquaintance.status AS acquaintance_status,
       profile.id AS personalized_profile_id, profile.status AS profile_status,
       COALESCE(product_preparation.operation_id,preparation.operation_id) AS preparation_operation_id,
       COALESCE(product_preparation.status,preparation.status) AS preparation_status,
       cycle.cycle_id, cycle.status AS cycle_status,
       EXISTS (SELECT 1 FROM m5_assessment_situations first_situation
               WHERE first_situation.cycle_db_id=cycle.id
                 AND first_situation.status='admitted') AS admitted_situation,
       plan.status AS plan_status,
       COALESCE(plan_progress.planned_positions, 0) AS planned_positions,
       COALESCE(plan_progress.completed_positions, 0) AS completed_positions,
       CASE WHEN ready_report.can_open AND cycle.collection_closed_at IS NOT NULL
            THEN ready_report.payload_json END AS results_payload,
       cycle.collection_closed_at, pipeline.status AS pipeline_status, pipeline.stage AS pipeline_stage,
       interim.turn_id AS failed_turn_id,
       CASE WHEN ready_report.can_open AND cycle.collection_closed_at IS NOT NULL
            THEN ready_report.id END AS report_id,
       CASE WHEN ready_report.can_open AND cycle.collection_closed_at IS NOT NULL
            THEN ready_report.status END AS report_status,
       COALESCE(ready_report.can_open AND cycle.collection_closed_at IS NOT NULL,FALSE) AS report_ready,
       COALESCE(ready_report.can_open AND cycle.collection_closed_at IS NOT NULL,FALSE) AS report_access,
       'customer' AS report_access_kind
FROM organization_assessment_assignments assignment
JOIN LATERAL (
    SELECT b.* FROM organization_assessment_source_bindings b
    WHERE b.assignment_id=assignment.id ORDER BY b.id DESC LIMIT 1
) binding ON TRUE
""" + PREPARATION_JOINS_SQL + f"""
LEFT JOIN LATERAL ({CUSTOMER_REPORT_FOR_CYCLE_SQL}) ready_report ON TRUE
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
LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
LEFT JOIN LATERAL ({INTERIM_FAILURE_FOR_CYCLE_SQL}) interim ON TRUE
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

from __future__ import annotations

import argparse

from Api.assessment_authoring_service import assessment_authoring_service
from Api.database import get_connection


OWNER_EMAIL = "bogachevv@mail.ru"
SHADOW_AGENT_CODE = "communication_shadow"
SHADOW_CONFIGURATION_CODE = "4k_standard_shadow_v1"


def publish() -> dict:
    with get_connection() as connection:
        owner = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s)", (OWNER_EMAIL,)
        ).fetchone()
        if owner is None:
            raise RuntimeError("Designated platform owner does not exist.")
        owner_id = int(owner["id"])
        connection.execute(
            """
            INSERT INTO user_platform_roles (user_id, platform_role_id, granted_by)
            SELECT %s, role.id, %s
            FROM platform_roles role
            WHERE role.code IN ('methodologist', 'assessment_publisher')
              AND NOT EXISTS (
                  SELECT 1 FROM user_platform_roles assignment
                  WHERE assignment.user_id = %s
                    AND assignment.platform_role_id = role.id
                    AND assignment.organization_id IS NULL
                    AND assignment.revoked_at IS NULL
              )
            """,
            (owner_id, owner_id, owner_id),
        )

        shadow = connection.execute(
            """
            SELECT version_row.id, version_row.status, version_row.version
            FROM assessment_agent_definitions parent
            JOIN assessment_agent_definition_versions version_row
              ON version_row.agent_definition_id = parent.id
            WHERE parent.code = %s
            ORDER BY version_row.version DESC LIMIT 1
            """,
            (SHADOW_AGENT_CODE,),
        ).fetchone()
        if shadow is None:
            official = connection.execute(
                """
                SELECT version_row.definition_json
                FROM assessment_agent_definitions parent
                JOIN assessment_agent_definition_versions version_row
                  ON version_row.agent_definition_id = parent.id
                WHERE parent.code = 'communication' AND version_row.status = 'published'
                ORDER BY version_row.version DESC LIMIT 1
                """
            ).fetchone()
            definition = dict(official["definition_json"])
            definition["instruction_markdown"] = (
                definition["instruction_markdown"]
                + "\n\n## Shadow execution\nEvaluate only the frozen skills and evidence supplied in the input contract."
            )
            definition["runtime"] = {
                "mode": "universal_llm", "model_profile": "assessment_strict",
                "temperature": 0, "max_attempts": 2, "timeout_seconds": 120,
                "max_output_tokens": 1200, "fallback": "fail",
            }
            shadow = assessment_authoring_service.create_definition(
                connection, entity_type="agent", code=SHADOW_AGENT_CODE,
                name="Communication universal shadow",
                description="First controlled universal shadow evaluator.",
                definition=definition, actor_user_id=owner_id,
                comment="Create first frozen shadow agent.",
            )
        if shadow["status"] == "draft":
            shadow = assessment_authoring_service.submit_for_review(
                connection, entity_type="agent", version_id=int(shadow["id"]),
                actor_user_id=owner_id, comment="Owner review for controlled rollout.",
            )
        if shadow["status"] == "ready_for_review":
            shadow = assessment_authoring_service.publish(
                connection, entity_type="agent", version_id=int(shadow["id"]),
                actor_user_id=owner_id, comment="Publish controlled shadow agent.",
            )

        methodology = connection.execute(
            """
            SELECT version_row.id, version_row.status, version_row.version, version_row.definition_json
            FROM assessment_methodologies parent
            JOIN assessment_methodology_versions version_row ON version_row.methodology_id = parent.id
            WHERE parent.code = 'competencies_4k' AND version_row.version = 2
            """
        ).fetchone()
        if methodology is None:
            source = connection.execute(
                """
                SELECT version_row.id
                FROM assessment_methodologies parent
                JOIN assessment_methodology_versions version_row ON version_row.methodology_id = parent.id
                WHERE parent.code = 'competencies_4k' AND version_row.status = 'published'
                ORDER BY version_row.version DESC LIMIT 1
                """
            ).fetchone()
            methodology = assessment_authoring_service.clone_version(
                connection, entity_type="methodology", source_version_id=int(source["id"]),
                actor_user_id=owner_id, description="Communication shadow rollout.",
            )
        if methodology["status"] == "draft":
            definition = dict(methodology["definition_json"])
            competencies = [dict(item) for item in definition["competencies"]]
            communication = next(item for item in competencies if item["code"] == "communication")
            communication["agent_definition"] = {"code": "communication", "version": 1}
            communication["shadow_evaluation"] = {
                "agent_definition": {"code": SHADOW_AGENT_CODE, "version": 1},
                "skill_codes": ["K1.1", "K1.2", "K1.3"],
            }
            definition["competencies"] = competencies
            methodology = assessment_authoring_service.update_draft(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                definition=definition, description="Communication shadow rollout.",
                actor_user_id=owner_id, comment="Add frozen communication shadow scope.",
            )
            methodology = assessment_authoring_service.submit_for_review(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                actor_user_id=owner_id, comment="Owner review for controlled rollout.",
            )
        if methodology["status"] == "ready_for_review":
            methodology = assessment_authoring_service.publish(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                actor_user_id=owner_id, comment="Publish communication shadow methodology.",
            )

        configuration = connection.execute(
            "SELECT * FROM assessment_configurations WHERE code = %s",
            (SHADOW_CONFIGURATION_CODE,),
        ).fetchone()
        if configuration is None:
            scenario = connection.execute(
                """
                SELECT version_row.id FROM assessment_scenarios parent
                JOIN assessment_scenario_versions version_row ON version_row.scenario_id = parent.id
                WHERE parent.code = 'standard_4k_interview' AND version_row.status = 'published'
                ORDER BY version_row.version DESC LIMIT 1
                """
            ).fetchone()
            configuration = assessment_authoring_service.create_configuration(
                connection, code=SHADOW_CONFIGURATION_CODE,
                name="4K standard with communication shadow",
                methodology_version_id=int(methodology["id"]), scenario_version_id=int(scenario["id"]),
                actor_user_id=owner_id, comment="Bind first frozen shadow configuration.",
            )
        if configuration["status"] == "draft":
            configuration = assessment_authoring_service.publish_configuration(
                connection, configuration_id=int(configuration["id"]), make_default=True,
                actor_user_id=owner_id, comment="Publish first shadow configuration as default.",
            )
        elif not configuration["is_default"]:
            connection.execute("UPDATE assessment_configurations SET is_default = FALSE")
            connection.execute(
                "UPDATE assessment_configurations SET is_default = TRUE WHERE id = %s",
                (configuration["id"],),
            )
        return {
            "owner_id": owner_id,
            "agent_version_id": int(shadow["id"]),
            "methodology_version_id": int(methodology["id"]),
            "configuration_id": int(configuration["id"]),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Refusing mutation without --apply")
    print(publish())

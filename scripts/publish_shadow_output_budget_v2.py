from __future__ import annotations

from Api.assessment_authoring_service import assessment_authoring_service
from Api.database import get_connection


def publish() -> dict:
    with get_connection() as connection:
        owner = connection.execute(
            "SELECT id FROM users WHERE lower(email)=lower('bogachevv@mail.ru')"
        ).fetchone()
        owner_id = int(owner["id"])

        agent = connection.execute(
            """
            SELECT v.* FROM assessment_agent_definitions p
            JOIN assessment_agent_definition_versions v ON v.agent_definition_id=p.id
            WHERE p.code='communication_shadow' AND v.version=2
            """
        ).fetchone()
        if agent is None:
            source = connection.execute(
                """
                SELECT v.id FROM assessment_agent_definitions p
                JOIN assessment_agent_definition_versions v ON v.agent_definition_id=p.id
                WHERE p.code='communication_shadow' AND v.version=1
                """
            ).fetchone()
            agent = assessment_authoring_service.clone_version(
                connection, entity_type="agent", source_version_id=int(source["id"]),
                actor_user_id=owner_id, description="Increase complete JSON output budget.",
            )
        if agent["status"] == "draft":
            definition = dict(agent["definition_json"])
            definition["runtime"] = {**definition["runtime"], "max_output_tokens": 4096}
            agent = assessment_authoring_service.update_draft(
                connection, entity_type="agent", version_id=int(agent["id"]),
                definition=definition, description="Increase complete JSON output budget.",
                actor_user_id=owner_id, comment="Three-skill output requires full contract budget.",
            )
            agent = assessment_authoring_service.submit_for_review(
                connection, entity_type="agent", version_id=int(agent["id"]),
                actor_user_id=owner_id, comment="Owner review.",
            )
        if agent["status"] == "ready_for_review":
            agent = assessment_authoring_service.publish(
                connection, entity_type="agent", version_id=int(agent["id"]),
                actor_user_id=owner_id, comment="Publish shadow v2 output budget.",
            )

        methodology = connection.execute(
            """
            SELECT v.* FROM assessment_methodologies p
            JOIN assessment_methodology_versions v ON v.methodology_id=p.id
            WHERE p.code='competencies_4k' AND v.version=3
            """
        ).fetchone()
        if methodology is None:
            source = connection.execute(
                """
                SELECT v.id FROM assessment_methodologies p
                JOIN assessment_methodology_versions v ON v.methodology_id=p.id
                WHERE p.code='competencies_4k' AND v.version=2
                """
            ).fetchone()
            methodology = assessment_authoring_service.clone_version(
                connection, entity_type="methodology", source_version_id=int(source["id"]),
                actor_user_id=owner_id, description="Use communication shadow v2.",
            )
        if methodology["status"] == "draft":
            definition = dict(methodology["definition_json"])
            competencies = [dict(item) for item in definition["competencies"]]
            communication = next(item for item in competencies if item["code"] == "communication")
            communication["shadow_evaluation"] = {
                **communication["shadow_evaluation"],
                "agent_definition": {"code": "communication_shadow", "version": 2},
            }
            definition["competencies"] = competencies
            methodology = assessment_authoring_service.update_draft(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                definition=definition, description="Use communication shadow v2.",
                actor_user_id=owner_id, comment="Freeze shadow v2.",
            )
            methodology = assessment_authoring_service.submit_for_review(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                actor_user_id=owner_id, comment="Owner review.",
            )
        if methodology["status"] == "ready_for_review":
            methodology = assessment_authoring_service.publish(
                connection, entity_type="methodology", version_id=int(methodology["id"]),
                actor_user_id=owner_id, comment="Publish methodology with shadow v2.",
            )

        configuration = connection.execute(
            "SELECT * FROM assessment_configurations WHERE code='4k_standard_shadow_v2'"
        ).fetchone()
        if configuration is None:
            scenario = connection.execute(
                """
                SELECT v.id FROM assessment_scenarios p
                JOIN assessment_scenario_versions v ON v.scenario_id=p.id
                WHERE p.code='standard_4k_interview' AND v.status='published'
                ORDER BY v.version DESC LIMIT 1
                """
            ).fetchone()
            configuration = assessment_authoring_service.create_configuration(
                connection, code="4k_standard_shadow_v2", name="4K standard communication shadow v2",
                methodology_version_id=int(methodology["id"]), scenario_version_id=int(scenario["id"]),
                actor_user_id=owner_id, comment="Bind shadow v2.",
            )
        if configuration["status"] == "draft":
            configuration = assessment_authoring_service.publish_configuration(
                connection, configuration_id=int(configuration["id"]), make_default=True,
                actor_user_id=owner_id, comment="Publish shadow v2 configuration as default.",
            )
        return {"agent_version": 2, "methodology_version": 3, "configuration_id": int(configuration["id"])}


if __name__ == "__main__":
    print(publish())

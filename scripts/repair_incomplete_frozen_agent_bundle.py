from __future__ import annotations

import argparse
import json

from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import load_default_execution_configuration
from Api.database import get_connection


CONFIGURATION_CODE = "4k_standard_baseline_v1"


def _missing_agent_codes(snapshot: dict) -> list[str]:
    methodology = dict(snapshot.get("methodology") or {}).get("definition") or {}
    prompts = dict(snapshot.get("prompts") or {})
    frozen = dict(prompts.get("agent_definitions") or {})
    required = []
    for competency in methodology.get("competencies") or []:
        evaluator = str(competency.get("evaluator") or "")
        reference = competency.get("agent_definition") or {}
        code = str(reference.get("code") or evaluator.removeprefix("evaluation.")).strip()
        if code and code not in required:
            required.append(code)
    return [code for code in required if code not in frozen]


def publish_complete_configuration(connection, *, actor_user_id: int) -> dict:
    current = load_default_execution_configuration(connection)
    existing = connection.execute(
        "SELECT * FROM assessment_configurations WHERE code = %s",
        (CONFIGURATION_CODE,),
    ).fetchone()
    if existing is None:
        existing = assessment_authoring_service.create_configuration(
            connection,
            code=CONFIGURATION_CODE,
            name="Стандартная оценка 4K — baseline 1",
            methodology_version_id=int(current["methodology_version_id"]),
            scenario_version_id=int(current["scenario_version_id"]),
            actor_user_id=actor_user_id,
            comment="Замена неполного frozen agent bundle без изменения методологии.",
        )
    if existing["status"] == "draft":
        existing = assessment_authoring_service.publish_configuration(
            connection,
            configuration_id=int(existing["id"]),
            make_default=True,
            actor_user_id=actor_user_id,
            comment="Публикация полного frozen agent bundle baseline 1.",
        )
    elif not existing["is_default"]:
        raise RuntimeError("Baseline configuration already exists but is not default; manual review is required.")
    complete = load_default_execution_configuration(connection)
    missing = _missing_agent_codes(complete["snapshot"])
    if missing:
        raise RuntimeError("Published baseline configuration is incomplete: " + ", ".join(missing))
    return complete


def repair_failed_session(connection, *, session_id: int, configuration: dict) -> None:
    row = connection.execute(
        """
        SELECT id, status, execution_snapshot_json, error_message
        FROM user_sessions
        WHERE id = %s
        FOR UPDATE
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("Assessment session was not found.")
    if row["status"] != "failed":
        raise RuntimeError("Only a failed assessment session can be repaired.")
    old_snapshot = dict(row["execution_snapshot_json"] or {})
    missing = _missing_agent_codes(old_snapshot)
    if not missing or "Frozen agent definition is missing" not in str(row["error_message"] or ""):
        raise RuntimeError("Session did not fail because of an incomplete frozen agent bundle.")
    new_snapshot = configuration["snapshot"]
    for section in ("methodology", "scenario"):
        old_ref = old_snapshot.get(section) or {}
        new_ref = new_snapshot.get(section) or {}
        if (old_ref.get("code"), old_ref.get("version")) != (new_ref.get("code"), new_ref.get("version")):
            raise RuntimeError(f"Refusing repair: {section} version differs from the failed session.")
    connection.execute(
        """
        UPDATE user_sessions
        SET assessment_configuration_id = %s,
            methodology_version_id = %s,
            scenario_version_id = %s,
            execution_snapshot_json = %s::jsonb,
            execution_checksum = %s
        WHERE id = %s
        """,
        (
            configuration["configuration_id"],
            configuration["methodology_version_id"],
            configuration["scenario_version_id"],
            json.dumps(new_snapshot, ensure_ascii=False),
            configuration["checksum"],
            session_id,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Публикация полного agent bundle и ремонт failed test-сессии.")
    parser.add_argument("--actor-email", required=True)
    parser.add_argument("--session-id", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Refusing mutation without --apply")
    with get_connection() as connection:
        database_name = str(connection.execute("SELECT current_database() AS name").fetchone()["name"])
        if "test" not in database_name.lower() and "pytest" not in database_name.lower():
            raise RuntimeError("Repair is allowed only in a database whose name contains test or pytest.")
        actor = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s)",
            (args.actor_email,),
        ).fetchone()
        if actor is None:
            raise RuntimeError("Actor user was not found.")
        configuration = publish_complete_configuration(connection, actor_user_id=int(actor["id"]))
        if args.session_id is not None:
            repair_failed_session(connection, session_id=args.session_id, configuration=configuration)
        connection.commit()
        print(
            {
                "configuration_id": configuration["configuration_id"],
                "configuration_code": configuration["snapshot"]["configuration"]["code"],
                "repaired_session_id": args.session_id,
            }
        )


if __name__ == "__main__":
    main()

"""Owned synthetic data and numeric readback for the combined browser contract."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import environment, owned


def readback(connection, state):
    data = state["f23_f10_f11"]
    organization_id = data["organization_id"]
    user_id = data["user_id"]
    membership = connection.execute("""SELECT role,is_participant FROM organization_memberships
        WHERE organization_id=%s AND user_id=%s""", (organization_id, user_id)).fetchone()
    connections = connection.execute("""SELECT program_definition_id,is_current,operation_id,
        superseded_at IS NOT NULL AS superseded FROM organization_assessment_program_connections
        WHERE organization_id=%s ORDER BY id""", (organization_id,)).fetchall()
    assignment = connection.execute("""SELECT id,assignment_ref,questionnaire_revision_id
        FROM organization_assessment_assignments WHERE organization_id=%s AND recipient_user_id=%s
        ORDER BY id DESC LIMIT 1""", (organization_id, user_id)).fetchone()
    binding = connection.execute("""SELECT assessment_configuration_id,role_profile_version_id,
        questionnaire_revision_id FROM organization_assessment_source_bindings
        WHERE assignment_id=%s ORDER BY id DESC LIMIT 1""", (assignment["id"],)).fetchone() if assignment else None
    cycles = connection.execute("""SELECT assignment_id,personalized_profile_id,
        profile_ref_json,selected_role_ref_json,target_set_json,parameter_sources_json,status
        FROM m5_cycles WHERE owner_user_id=%s AND organization_id=%s ORDER BY id""",
        (user_id, organization_id)).fetchall()
    return {
        "membership": dict(membership) if membership else None,
        "connections": [dict(row) for row in connections],
        "control_connections": connection.execute("""SELECT COUNT(*) AS n
            FROM organization_assessment_program_connections WHERE organization_id=%s""",
            (data["control_organization_id"],)).fetchone()["n"],
        "assignment": dict(assignment) if assignment else None,
        "binding": dict(binding) if binding else None,
        "cycles": [dict(row) for row in cycles],
        "superadmin_memberships": connection.execute("""SELECT COUNT(*) AS n
            FROM organization_memberships WHERE user_id=%s""", (data["superadmin_id"],)).fetchone()["n"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publish", "readback", "seed-cycle"])
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        from Api.database import get_connection
        if args.action == "publish":
            with get_connection() as connection:
                org = connection.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()
                control = connection.execute("SELECT id FROM organizations WHERE code='e102_other'").fetchone()
                user = connection.execute("SELECT id FROM users WHERE email='participant@example.test'").fetchone()
                superadmin = connection.execute("SELECT id FROM users WHERE email='superadmin@example.test'").fetchone()
                state["f23_f10_f11"] = {"organization_id": org["id"],
                    "control_organization_id": control["id"], "user_id": user["id"],
                    "superadmin_id": superadmin["id"]}
            for version in ("1.0", "2.0"):
                command = [sys.executable, "scripts/publish_assessment_program.py",
                    "--code", "f23-f10-f11-synthetic", "--version", version,
                    "--name", "Синтетическая программа " + version,
                    "--assignment-ref", "f23-f10-f11-synthetic", "--mode", "dialogue",
                    "--configuration-code", "e102_controlled_catalog",
                    "--role-code", "specialist_expert", "--publisher-user-id",
                    str(state["f23_f10_f11"]["superadmin_id"]), "--publish"]
                subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                    env=environment(state), check=True, capture_output=True, text=True)
            with get_connection() as connection:
                rows = connection.execute("""SELECT id,version,definition_checksum FROM assessment_program_definitions
                    WHERE code='f23-f10-f11-synthetic' ORDER BY version""").fetchall()
                state["f23_f10_f11"]["programs"] = [dict(row) for row in rows]
            args.state.write_text(json.dumps(state))
            print(json.dumps({"program_versions": [row["version"] for row in rows],
                              "published": len(rows) == 2}))
        elif args.action == "readback":
            with get_connection() as connection:
                print(json.dumps(readback(connection, state), default=str))
        else:
            with get_connection() as connection:
                data = readback(connection, state)
                if not data["assignment"] or not data["binding"]:
                    raise RuntimeError("EXACT_ASSIGNMENT_AND_BINDING_REQUIRED")
                profile = connection.execute("""SELECT id FROM assessment_personalized_profiles
                    WHERE user_id=%s AND organization_id=%s ORDER BY id DESC LIMIT 1""",
                    (state["f23_f10_f11"]["user_id"], state["f23_f10_f11"]["organization_id"])).fetchone()
                if profile is None:
                    raise RuntimeError("OWNED_PROFILE_REQUIRED")
                connection.execute("""INSERT INTO m5_cycles(cycle_id,owner_user_id,organization_id,
                    assignment_id,personalized_profile_id,profile_ref_json,selected_role_ref_json,
                    target_set_json,target_set_checksum,time_budget_seconds,calendar_window_seconds,
                    parameter_sources_json,usage_scope,status,created_by)
                    VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,600,3600,%s::jsonb,
                        'qa','prepared',%s)""",
                    (uuid4(), state["f23_f10_f11"]["user_id"],
                     state["f23_f10_f11"]["organization_id"], data["assignment"]["id"],
                     profile["id"], json.dumps({"synthetic": True,
                         "assessment_configuration_id": data["binding"]["assessment_configuration_id"]}),
                     json.dumps({"role_profile_version_id": data["binding"]["role_profile_version_id"]}),
                     json.dumps({"synthetic": True}), "synthetic-frozen-target",
                     json.dumps({"synthetic": True}), state["f23_f10_f11"]["superadmin_id"]))
                connection.commit()
            print(json.dumps({"synthetic_saved_cycle": True}))


if __name__ == "__main__":
    if os.getenv("AGENT4K_ISOLATED_STAND") != "1":
        state_arg = Path(sys.argv[sys.argv.index("--state") + 1])
        state_value = json.loads(state_arg.read_text())
        subprocess.run([sys.executable, __file__, *sys.argv[1:]],
            cwd=ROOT, env=environment(state_value), check=True)
        raise SystemExit(0)
    main()

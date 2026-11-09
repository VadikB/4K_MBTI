"""Prepare reproducible ADM-1C visual states in an owned disposable stand only."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.test_stand import environment, owned


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--internal", action="store_true")
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        subprocess.run(
            [sys.executable, __file__, "--state", str(args.state), "--internal"],
            cwd=ROOT,
            env=environment(state),
            check=True,
        )
        return

    from Api.auth_service import _hash_password
    from Api.database import get_connection

    now = datetime.now(UTC).replace(tzinfo=None)
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM organizations WHERE code='adm1c_visual'").fetchone():
            print("ADM-1C visual fixture already present; no data changed")
            return

        source_org = connection.execute(
            "SELECT id FROM organizations WHERE code='e102_synthetic'"
        ).fetchone()["id"]
        actor = connection.execute(
            "SELECT id FROM users WHERE email='superadmin@example.test'"
        ).fetchone()["id"]
        source_profile = connection.execute(
            "SELECT * FROM assessment_personalized_profiles ORDER BY id LIMIT 1"
        ).fetchone()
        configuration_id = source_profile["assessment_configuration_id"]
        role_version_id = source_profile["role_profile_version_id"]
        organization_context_version_id = source_profile["organization_context_version_id"]
        source_role_profile = connection.execute(
            "SELECT * FROM user_role_profiles ORDER BY id LIMIT 1"
        ).fetchone()

        organization_id = connection.execute(
            """INSERT INTO organizations(code,name,invitation_intro,notes)
               VALUES('adm1c_visual','ADM-1C · визуальная приёмка',
                      'Только синтетические данные @example.test',
                      'Owned disposable stand; LLM and external mail disabled') RETURNING id"""
        ).fetchone()["id"]
        questionnaire = {"fixture": "ADM-1C", "organization": "synthetic"}
        questionnaire_id = connection.execute(
            """INSERT INTO questionnaire_response_revisions(
                 organization_id,assignment_ref,template_variant,template_version,channel,status,
                 answers_json,validation_json,source_checksum,uploaded_by_user_id,source_author,
                 idempotency_key,request_hash,confirmed_by_user_id,confirmed_at,
                 organization_context_version_id)
               VALUES(%s,'adm1c-visual','corporate','1.0','product_form','confirmed',%s::jsonb,
                      '{"valid":true}'::jsonb,%s,%s,'synthetic-fixture','adm1c-visual',%s,%s,NOW(),%s)
               RETURNING id""",
            (organization_id, json.dumps(questionnaire), digest(questionnaire), actor,
             digest({"request": "adm1c-visual"}), actor, organization_context_version_id),
        ).fetchone()["id"]
        catalog_version_id = connection.execute(
            "SELECT catalog_version_id FROM assessment_configurations WHERE id=%s",
            (configuration_id,),
        ).fetchone()["catalog_version_id"]
        program_definition = {
            "code": "adm1c_visual",
            "version": "1.0",
            "assignment_ref": "adm1c-visual",
            "fixture": True,
        }
        program_id = connection.execute(
            """INSERT INTO assessment_program_definitions(
                 code,version,name,assignment_ref,mode,status,assessment_configuration_id,
                 catalog_version_id,source_refs_json,definition_checksum,published_by_user_id,published_at)
               VALUES('adm1c_visual','1.0','ADM-1C · визуальная программа','adm1c-visual',
                      'assessment','draft',%s,%s,%s::jsonb,%s,%s,NULL) RETURNING id""",
            (configuration_id, catalog_version_id, json.dumps({"synthetic": True}),
             digest(program_definition), actor),
        ).fetchone()["id"]
        connection.execute(
            """INSERT INTO assessment_program_allowed_roles(
                 program_definition_id,role_profile_version_id,display_order) VALUES(%s,%s,0)""",
            (program_id, role_version_id),
        )
        connection.execute(
            "UPDATE assessment_program_definitions SET status='published',published_at=NOW() WHERE id=%s",
            (program_id,),
        )
        connection.execute(
            """INSERT INTO organization_assessment_program_connections(
                 organization_id,program_definition_id,connected_by_user_id,operation_id,
                 request_fingerprint,is_current) VALUES(%s,%s,%s,'adm1c-connect',%s,TRUE)""",
            (organization_id, program_id, actor, digest({"connection": "adm1c-visual"})),
        )

        def member(key: str, name: str, *, registered: bool = False) -> tuple[int, str]:
            email = f"adm1c-{key}@example.test"
            user_id = connection.execute(
                "INSERT INTO users(full_name,email,company_industry,job_description) VALUES(%s,%s,'Синтетика','Визуальная проверка') RETURNING id",
                (name, email),
            ).fetchone()["id"]
            connection.execute(
                "INSERT INTO organization_memberships(organization_id,user_id,role,admission_source,admitted_at) VALUES(%s,%s,'member','admin_add',NOW())",
                (organization_id, user_id),
            )
            role_profile_id = connection.execute(
                """INSERT INTO user_role_profiles(user_id,role_id,raw_position,raw_duties,
                     normalized_duties,profile_metadata,raw_input,normalized_input,profile_quality,
                     user_context_vars,profile_version,profile_updated_at)
                   VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,1,NOW()) RETURNING id""",
                (user_id, source_role_profile["role_id"], "Синтетический специалист",
                 "Проверять статусы", "Проверять статусы", json.dumps(source_role_profile["profile_metadata"]),
                 json.dumps(source_role_profile["raw_input"]), json.dumps(source_role_profile["normalized_input"]),
                 json.dumps(source_role_profile["profile_quality"]), json.dumps(source_role_profile["user_context_vars"])),
            ).fetchone()["id"]
            connection.execute(
                "UPDATE users SET role_id=%s,active_profile_id=%s WHERE id=%s",
                (source_role_profile["role_id"], role_profile_id, user_id),
            )
            if registered:
                salt, password_hash = _hash_password(state["password"])
                connection.execute(
                    "INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)",
                    (user_id, email, password_hash, salt),
                )
            return user_id, email

        def invitation(user_key: str, label: str, delivery: str, *, expires: int = 48,
                       used: bool = False, revoked: bool = False, registered: bool = False) -> None:
            user_id, email = member(user_key, label, registered=registered)
            connection.execute(
                """INSERT INTO organization_invitations(
                     organization_id,token_hash,expires_at,revoked_at,created_by_user_id,created_at,
                     recipient_email,purpose,used_at,delivery_status,delivery_error,sent_at,request_id)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,'personal_registration',%s,%s,%s,%s,%s)""",
                (organization_id, digest({"invite": user_key}), now + timedelta(hours=expires),
                 now - timedelta(hours=1) if revoked else None, actor, now - timedelta(hours=3), email,
                 now - timedelta(hours=2) if used else None, delivery,
                 "controlled_delivery_error" if delivery == "error" else None,
                 now - timedelta(hours=2) if delivery in {"sent", "accepted"} else None,
                 f"adm1c-invite-{user_key}"),
            )

        invitation("01-queued", "01 · Письмо в очереди", "queued")
        invitation("02-sending", "02 · Письмо отправляется", "sending")
        invitation("03-error", "03 · Ошибка доставки", "error")
        invitation("04-expired", "04 · Ссылка истекла", "accepted", expires=-2)
        invitation("05-revoked", "05 · Ссылка отозвана", "accepted", revoked=True)
        invitation("06-used", "06 · Ссылка использована", "accepted", used=True, registered=True)

        def assigned(key: str, label: str, *, acquaintance: str = "not_started",
                     preparation: str | None = None, cycle_status: str | None = None,
                     pipeline: str | None = None, report: bool = False, history: bool = False) -> None:
            user_id, email = member(key, label, registered=True)
            if history:
                old_id = connection.execute(
                    """INSERT INTO organization_assessment_assignments(
                         organization_id,recipient_user_id,assignment_ref,created_by_user_id,
                         questionnaire_revision_id,status,operation_id,request_fingerprint,created_at,revoked_at)
                       VALUES(%s,%s,'adm1c-visual',%s,%s,'revoked',%s,%s,%s,%s) RETURNING id""",
                    (organization_id, user_id, actor, questionnaire_id, f"old-{key}", digest({"old": key}),
                     now - timedelta(days=10), now - timedelta(days=5)),
                ).fetchone()["id"]
                connection.execute(
                    """INSERT INTO organization_assessment_source_bindings(
                         assignment_id,questionnaire_revision_id,assessment_configuration_id,
                         role_profile_version_id,assigned_by_user_id,operation_id)
                       VALUES(%s,%s,%s,%s,%s,%s)""",
                    (old_id, questionnaire_id, configuration_id, role_version_id, actor, f"old-{key}"),
                )
            assignment_ref = "adm1c-visual"
            assignment_id = connection.execute(
                """INSERT INTO organization_assessment_assignments(
                     organization_id,recipient_user_id,assignment_ref,created_by_user_id,
                     questionnaire_revision_id,status,operation_id,request_fingerprint,created_at)
                   VALUES(%s,%s,%s,%s,%s,'active',%s,%s,%s) RETURNING id""",
                (organization_id, user_id, assignment_ref, actor, questionnaire_id,
                 f"assign-{key}", digest({"assignment": key}), now - timedelta(days=2)),
            ).fetchone()["id"]
            connection.execute(
                """INSERT INTO organization_assessment_source_bindings(
                     assignment_id,questionnaire_revision_id,assessment_configuration_id,
                     role_profile_version_id,assigned_by_user_id,operation_id)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (assignment_id, questionnaire_id, configuration_id, role_version_id, actor, f"assign-{key}"),
            )
            profile_id = connection.execute(
                """INSERT INTO assessment_personalized_profiles(
                     user_id,organization_id,assessment_configuration_id,organization_context_version_id,
                     role_profile_version_id,user_context_version_id,status,content_json,provenance_json,
                     conflicts_json,checksum,frozen_at)
                   VALUES(%s,%s,%s,%s,%s,%s,'ready',%s::jsonb,%s::jsonb,%s::jsonb,%s,NOW()) RETURNING id""",
                (user_id, organization_id, configuration_id, organization_context_version_id,
                 role_version_id, source_profile["user_context_version_id"], json.dumps(source_profile["content_json"]),
                 json.dumps(source_profile["provenance_json"]), json.dumps(source_profile["conflicts_json"]), digest({"profile": key})),
            ).fetchone()["id"]
            connection.execute(
                """INSERT INTO participant_acquaintance_states(
                     user_id,organization_id,organization_context_version_id,assignment_ref,
                     questionnaire_revision_id,status,current_step,answers_json)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb)""",
                (user_id, organization_id, organization_context_version_id, assignment_ref,
                 questionnaire_id, acquaintance, 3 if acquaintance != "not_started" else 0),
            )
            if preparation:
                connection.execute(
                    """INSERT INTO assessment_preparation_jobs(
                         operation_id,user_id,user_payload_json,status,result_json,error_code,error_message,
                         personalized_profile_id,completed_at)
                       VALUES(%s,%s,'{}'::jsonb,%s,%s::jsonb,%s,%s,%s,%s)""",
                    (f"prepare-{key}", user_id, preparation,
                     json.dumps({"synthetic": True}) if preparation == "completed" else None,
                     "SYNTHETIC_FAILURE" if preparation == "failed" else None,
                     "Синтетическая техническая ошибка" if preparation == "failed" else None,
                     profile_id, now if preparation in {"completed", "failed"} else None),
                )
            if not cycle_status:
                return
            cycle_id = uuid4()
            cycle_db_id = connection.execute(
                """INSERT INTO m5_cycles(
                     cycle_id,owner_user_id,organization_id,assignment_id,personalized_profile_id,
                     profile_ref_json,selected_role_ref_json,target_set_json,target_set_checksum,
                     time_budget_seconds,calendar_window_seconds,parameter_sources_json,usage_scope,
                     status,created_by,started_at,collection_closed_at)
                   VALUES(%s,%s,%s,%s,%s,'{}','{}','[]',%s,7200,259200,'{}','assessment',%s,%s,%s,%s)
                   RETURNING id""",
                (cycle_id, user_id, organization_id, assignment_id, profile_id, digest({"targets": key}),
                 cycle_status, actor, now - timedelta(hours=2),
                 now - timedelta(minutes=30) if cycle_status in {"collection_closed", "calculated"} else None),
            ).fetchone()["id"]
            if pipeline:
                connection.execute(
                    "INSERT INTO m10_pipeline_runs(cycle_db_id,status,stage,error_code) VALUES(%s,%s,'synthetic_visual',%s)",
                    (cycle_db_id, pipeline, "SYNTHETIC_FAILURE" if pipeline == "failed" else None),
                )
            if report:
                result_id, revision_id, report_id = uuid4(), uuid4(), uuid4()
                connection.execute("SET LOCAL session_replication_role=replica")
                connection.execute("INSERT INTO m8_results(id,cycle_db_id) VALUES(%s,%s)", (result_id, cycle_db_id))
                connection.execute(
                    """INSERT INTO m8_result_revisions(
                         id,results_id,revision_no,calculation_id,c46_revision_id,composition_checksum,
                         payload_json,payload_checksum,reason,created_by)
                       VALUES(%s,%s,1,%s,%s,%s,'{}',%s,'synthetic_visual',%s)""",
                    (revision_id, result_id, uuid4(), uuid4(), digest({"composition": key}),
                     digest({"payload": key}), actor),
                )
                connection.execute(
                    """INSERT INTO m8_reports(
                         id,result_revision_id,revision_no,audience,template_version,c67_json,c67_checksum,
                         status,request_key,request_hash,created_by)
                       VALUES(%s,%s,1,'assessee','synthetic-visual/1','{}',%s,'ready',%s,%s,%s)""",
                    (report_id, revision_id, digest({"report": key}), f"report-{key}", digest({"request": key}), actor),
                )
                connection.execute(
                    "INSERT INTO m8_cycle_report_recipients(cycle_db_id,user_id) VALUES(%s,%s)",
                    (cycle_db_id, actor),
                )
                connection.execute("SET LOCAL session_replication_role=origin")

        assigned("07-assigned", "07 · Оценка назначена")
        assigned("08-acquaintance", "08 · Проходит знакомство", acquaintance="in_progress")
        assigned("09-preparing", "09 · Идёт подготовка", acquaintance="completed", preparation="running", cycle_status="prepared")
        assigned("10-prep-failed", "10 · Ошибка подготовки", acquaintance="completed", preparation="failed", cycle_status="prepared")
        assigned("11-active", "11 · Оценка выполняется", acquaintance="completed", preparation="completed", cycle_status="active")
        assigned("12-processing", "12 · Готовится отчёт", acquaintance="completed", preparation="completed", cycle_status="collection_closed", pipeline="running")
        assigned("13-pipeline-failed", "13 · Ошибка обработки", acquaintance="completed", preparation="completed", cycle_status="collection_closed", pipeline="failed")
        assigned("14-report", "14 · Отчёт готов · новая генерация", acquaintance="completed", preparation="completed", cycle_status="calculated", pipeline="completed", report=True, history=True)

        connection.commit()
    print("ADM-1C visual fixture ready: 14 participants, isolated PostgreSQL, no mail/LLM")


if __name__ == "__main__":
    main()

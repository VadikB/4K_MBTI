from __future__ import annotations

import json
import secrets
import time
from datetime import datetime
from threading import Lock

from Api.config import settings
from Api.database import get_connection
from Api.mbti.service import mbti_assessment_service
from Api.schemas import AdminRegressionTestRunResponse, AdminRegressionTestStatusResponse, AdminRegressionTestStep


AUTOTEST_ORG_CODE = "__autotest__smoke"
AUTOTEST_ORG_NAME = "__autotest__ Smoke Regression"
AUTOTEST_DOMAIN = "autotest.local"
AUTOTEST_EMAIL_PREFIX = "__autotest__"

_last_run: AdminRegressionTestRunResponse | None = None
_lock = Lock()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _step(name: str, status: str, message: str) -> AdminRegressionTestStep:
    return AdminRegressionTestStep(name=name, status=status, message=message)


def _role_payload(role_code: str) -> dict:
    fixtures = {
        "linear_employee": {
            "full_name": "__autotest__ Linear Support",
            "position": "Специалист технической поддержки первой линии",
            "duties": "Принимает обращения клиентов, проводит первичную диагностику, фиксирует заявки в CRM и эскалирует сложные инциденты.",
        },
        "manager": {
            "full_name": "__autotest__ Support Manager",
            "position": "Руководитель департамента клиентской технической поддержки",
            "duties": "Организует работу команд поддержки, контролирует SLA, распределяет нагрузку и согласует действия с эксплуатацией сервисов.",
        },
        "leader": {
            "full_name": "__autotest__ Service Leader",
            "position": "Руководитель крупного департамента клиентского опыта",
            "duties": "Управляет стратегией клиентского опыта, надежностью сервисов, метриками качества и межфункциональными изменениями.",
        },
    }
    return fixtures[role_code]


def _cleanup_autotest_data(connection) -> dict[str, int]:
    user_rows = connection.execute(
        """
        SELECT id
        FROM users
        WHERE LOWER(email) LIKE %s ESCAPE %s
        """,
        (r"\_\_autotest\_\_%@autotest.local", "\\"),
    ).fetchall()
    user_ids = [int(row["id"]) for row in user_rows]
    counts = {"users": len(user_ids), "organizations": 0, "sessions": 0}
    if user_ids:
        session_rows = connection.execute("SELECT id FROM user_sessions WHERE user_id = ANY(%s)", (user_ids,)).fetchall()
        counts["sessions"] = len(session_rows)
        sessions_sql = "SELECT id FROM user_sessions WHERE user_id = ANY(%s)"
        cases_sql = "SELECT id FROM session_cases WHERE user_id = ANY(%s) OR session_id IN (" + sessions_sql + ")"
        connection.execute(
            "DELETE FROM session_case_messages WHERE session_case_id IN (" + cases_sql + ") OR session_id IN (" + sessions_sql + ")",
            (user_ids, user_ids, user_ids),
        )
        connection.execute(
            "DELETE FROM session_case_results WHERE user_id = ANY(%s) OR session_case_id IN (" + cases_sql + ") OR session_id IN (" + sessions_sql + ")",
            (user_ids, user_ids, user_ids, user_ids),
        )
        connection.execute(
            "DELETE FROM session_case_skill_analysis WHERE user_id = ANY(%s) OR session_case_id IN (" + cases_sql + ")",
            (user_ids, user_ids, user_ids),
        )
        connection.execute("DELETE FROM session_case_skills WHERE session_case_id IN (" + cases_sql + ")", (user_ids, user_ids))
        connection.execute(
            "DELETE FROM session_prompts WHERE session_case_id IN (" + cases_sql + ") OR session_id IN (" + sessions_sql + ")",
            (user_ids, user_ids, user_ids),
        )
        connection.execute("DELETE FROM session_skill_assessments WHERE user_id = ANY(%s) OR session_id IN (" + sessions_sql + ")", (user_ids, user_ids))
        connection.execute("DELETE FROM session_skills WHERE session_id IN (" + sessions_sql + ")", (user_ids,))
        connection.execute("DELETE FROM session_mbti_refinements WHERE user_id = ANY(%s) OR session_id IN (" + sessions_sql + ")", (user_ids, user_ids))
        connection.execute("DELETE FROM session_cases WHERE user_id = ANY(%s) OR session_id IN (" + sessions_sql + ")", (user_ids, user_ids))
        connection.execute("DELETE FROM agent_conversation_sessions WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM user_skill_coverage WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM user_case_assignments WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM web_user_sessions WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM organization_memberships WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM user_identities WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute(
            "DELETE FROM auth_magic_links WHERE LOWER(email) LIKE %s ESCAPE %s",
            (r"\_\_autotest\_\_%@autotest.local", "\\"),
        )
        connection.execute("DELETE FROM user_sessions WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("UPDATE users SET active_profile_id = NULL WHERE id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM user_role_profiles WHERE user_id = ANY(%s)", (user_ids,))
        connection.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))

    org_row = connection.execute("SELECT id FROM organizations WHERE code = %s", (AUTOTEST_ORG_CODE,)).fetchone()
    if org_row is not None:
        counts["organizations"] = 1
        connection.execute("DELETE FROM organization_email_domains WHERE organization_id = %s", (int(org_row["id"]),))
        connection.execute("DELETE FROM organizations WHERE id = %s", (int(org_row["id"]),))
    return counts


def cleanup_autotest_data() -> dict[str, int]:
    with get_connection() as connection:
        counts = _cleanup_autotest_data(connection)
        connection.commit()
        return counts


def _create_profile(connection, *, user_id: int, role_id: int, role_name: str, role_code: str, fixture: dict) -> int:
    company = "Ростелеком-like контекст: телеком, цифровые сервисы, техническая поддержка, SLA, CRM и клиентский опыт."
    profile_quality = {"completeness": "complete", "confidence": 0.9, "needs_clarification": False}
    profile_row = connection.execute(
        """
        INSERT INTO user_role_profiles (
            user_id, role_id, detected_role, raw_position, raw_duties, normalized_duties,
            role_selected, role_selected_code, role_confidence, role_rationale,
            role_consistency_status, role_consistency_comment,
            profile_build_instruction_code, profile_build_summary, profile_build_trace,
            company_context, profile_metadata, raw_input, normalized_input, role_interpretation, user_work_context,
            role_limits, role_vocabulary, domain_profile, role_skill_profile, adaptation_rules_for_cases, user_domain,
            user_processes, user_tasks, user_stakeholders, user_risks, user_constraints,
            user_artifacts, user_systems, user_success_metrics, data_quality_notes,
            domain_resolution_status, domain_confidence, profile_quality,
            user_context_vars, profile_version, profile_updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s::jsonb,
            %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
            %s, %s, %s::jsonb,
            %s::jsonb, 1, CURRENT_TIMESTAMP
        )
        RETURNING id
        """,
        (
            user_id,
            role_id,
            role_name,
            fixture["position"],
            fixture["duties"],
            fixture["duties"],
            role_name,
            role_code,
            0.95,
            "__autotest__ профиль",
            "consistent",
            "Роль согласована с должностью и обязанностями.",
            "__autotest__smoke",
            "Автотестовый профиль",
            _json({"source": "__autotest__"}),
            company,
            _json({"source": "__autotest__", "status": "created"}),
            _json({"position": fixture["position"], "duties": fixture["duties"], "company_industry": company}),
            _json({"position": fixture["position"], "duties": fixture["duties"], "selected_role_code": role_code}),
            _json({"selected_role_code": role_code, "selected_role_name": role_name, "role_confidence": 0.95}),
            _json({"domain": "telecom_support", "company": "__autotest__"}),
            _json({"scope": role_name, "decision_level": role_code}),
            _json({"verbs": ["диагностировать", "приоритизировать", "эскалировать"], "objects": ["SLA", "CRM", "инцидент"]}),
            _json({"domain_code": "telecom_support", "domain_label": "Телеком и техническая поддержка"}),
            _json({"expected_scope": role_name, "role_code": role_code}),
            _json({"prefer": ["SLA", "CRM", "эскалация", "клиентский опыт"]}),
            "Телеком и техническая поддержка",
            _json(["прием обращений", "контроль SLA", "эскалация"]),
            _json([fixture["duties"]]),
            _json(["клиенты", "поддержка", "эксплуатация сервисов"]),
            _json(["нарушение SLA", "повторные обращения"]),
            _json(["регламенты", "ресурсы команды"]),
            _json(["заявка CRM", "отчет SLA"]),
            _json(["CRM", "сервис-деск"]),
            _json(["соблюдение SLA", "снижение повторных обращений"]),
            _json([]),
            "exact_match",
            0.9,
            _json(profile_quality),
            _json({"autotest": True, "role_code": role_code}),
        ),
    ).fetchone()
    profile_id = int(profile_row["id"])
    connection.execute("UPDATE users SET active_profile_id = %s WHERE id = %s", (profile_id, user_id))
    return profile_id


def run_smoke_regression() -> AdminRegressionTestRunResponse:
    global _last_run

    with _lock:
        started_at = datetime.utcnow()
        start_time = time.monotonic()
        steps: list[AdminRegressionTestStep] = []
        user_ids: list[int] = []
        session_ids: list[int] = []
        organization_id: int | None = None
        status = "passed"

        try:
            with get_connection() as connection:
                _cleanup_autotest_data(connection)
                steps.append(_step("cleanup", "passed", "Предыдущие __autotest__ данные удалены."))

                org_row = connection.execute(
                    """
                    INSERT INTO organizations (code, name, is_active)
                    VALUES (%s, %s, TRUE)
                    RETURNING id
                    """,
                    (AUTOTEST_ORG_CODE, AUTOTEST_ORG_NAME),
                ).fetchone()
                organization_id = int(org_row["id"])
                connection.execute(
                    "INSERT INTO organization_email_domains (organization_id, domain) VALUES (%s, %s)",
                    (organization_id, AUTOTEST_DOMAIN),
                )
                steps.append(_step("organization", "passed", f"Создана организация {AUTOTEST_ORG_NAME}."))

                roles = {
                    row["code"]: {"id": int(row["id"]), "name": row["name"]}
                    for row in connection.execute("SELECT id, code, name FROM roles WHERE code IN ('linear_employee', 'manager', 'leader')").fetchall()
                }
                if len(roles) != 3:
                    raise RuntimeError("Не найдены все системные роли для автотеста.")

                run_suffix = secrets.token_hex(4)
                for role_code in ("linear_employee", "manager", "leader"):
                    fixture = _role_payload(role_code)
                    email = f"{AUTOTEST_EMAIL_PREFIX}{role_code}.{run_suffix}@{AUTOTEST_DOMAIN}"
                    role = roles[role_code]
                    user_row = connection.execute(
                        """
                        INSERT INTO users (
                            full_name, email, role_id, job_description, company_industry,
                            personal_data_consent_accepted_at, personal_data_consent_version, personal_data_consent_text
                        )
                        VALUES (%s, %s, %s, %s, %s, NOW(), 1, %s)
                        RETURNING id
                        """,
                        (
                            fixture["full_name"],
                            email,
                            role["id"],
                            fixture["position"],
                            "Автотест: телеком, поддержка, SLA",
                            "__autotest__ consent",
                        ),
                    ).fetchone()
                    user_id = int(user_row["id"])
                    user_ids.append(user_id)
                    _create_profile(connection, user_id=user_id, role_id=role["id"], role_name=role["name"], role_code=role_code, fixture=fixture)
                    connection.execute(
                        """
                        INSERT INTO user_identities (
                            user_id, provider, provider_subject, email,
                            is_primary, is_verified, verified_at, updated_at
                        )
                        VALUES (%s, 'email_magic_link', %s, %s, TRUE, TRUE, NOW(), NOW())
                        """,
                        (user_id, email, email),
                    )
                    connection.execute(
                        "INSERT INTO organization_memberships (organization_id, user_id, role) VALUES (%s, %s, 'member')",
                        (organization_id, user_id),
                    )

                    mbti_summary = {
                        "общий_итог": {
                            "оценка": 50,
                            "темперамент": "__autotest__",
                            "краткий_вывод": "Автотестовая MBTI-сводка создана для проверки отображения отчетов.",
                        }
                    }
                    session_row = connection.execute(
                        """
                        INSERT INTO user_sessions (
                            session_code, user_id, role_id, status, source, notes,
                            assessment_code, started_at, finished_at, mbti_summary_json
                        )
                        VALUES (%s, %s, %s, 'completed', '__autotest__', 'Smoke regression session', 'competencies_4k', NOW(), NOW(), %s::jsonb)
                        RETURNING id
                        """,
                        (f"__autotest__{secrets.token_hex(12)}", user_id, role["id"], _json(mbti_summary)),
                    ).fetchone()
                    session_ids.append(int(session_row["id"]))
                steps.append(_step("users", "passed", "Созданы 3 пользователя: linear_employee, manager, leader."))
                steps.append(_step("sessions", "passed", "Созданы завершенные технические сессии для проверки отчетов и MBTI."))

                membership_count = connection.execute(
                    "SELECT COUNT(*)::int AS count FROM organization_memberships WHERE organization_id = %s",
                    (organization_id,),
                ).fetchone()["count"]
                report_count = connection.execute(
                    "SELECT COUNT(*)::int AS count FROM user_sessions WHERE id = ANY(%s) AND status = 'completed'",
                    (session_ids,),
                ).fetchone()["count"]
                if int(membership_count) != 3 or int(report_count) != 3:
                    raise RuntimeError("Проверка membership/report count не прошла.")
                steps.append(_step("assertions", "passed", "Проверены membership, completed sessions и MBTI payload."))
                connection.commit()
        except Exception as exc:
            status = "failed"
            steps.append(_step("failure", "failed", str(exc)))

        finished_at = datetime.utcnow()
        run = AdminRegressionTestRunResponse(
            status=status,
            title="Smoke regression",
            summary=(
                "Быстрый регрессионный тест прошел успешно."
                if status == "passed"
                else "Регрессионный тест завершился с ошибкой."
            ),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - start_time, 2),
            organization_id=organization_id,
            user_ids=user_ids,
            session_ids=session_ids,
            steps=steps,
        )
        _last_run = run
        return run


def get_regression_status() -> AdminRegressionTestStatusResponse:
    store_available = False
    if settings.mbti_enabled:
        try:
            store_available = mbti_assessment_service._get_store() is not None
        except Exception:
            store_available = False
    return AdminRegressionTestStatusResponse(
        title="Регрессионные тесты",
        subtitle="Быстрые суперадминские проверки организации, пользователей, отчетов и MBTI readiness.",
        mbti_enabled=bool(settings.mbti_enabled),
        mbti_store_available=store_available,
        last_run=_last_run,
        cleanup_hint="Удаляются только данные с префиксом __autotest__.",
    )

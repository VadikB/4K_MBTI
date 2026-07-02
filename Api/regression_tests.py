from __future__ import annotations

import json
import secrets
import time
from datetime import datetime
from threading import Lock

from Api.agent import interviewer_agent
from Api.config import settings
from Api.database import get_connection
from Api.mbti.service import mbti_assessment_service
from Api.schemas import AdminRegressionTestRunResponse, AdminRegressionTestStatusResponse, AdminRegressionTestStep, UserResponse
from Api.web_session_service import USER_SELECT_SQL


AUTOTEST_ORG_CODE = "__autotest__smoke"
AUTOTEST_ORG_NAME = "__autotest__ Smoke Regression"
AUTOTEST_DOMAIN = "autotest.local"
AUTOTEST_EMAIL_PREFIX = "__autotest__"

_last_run: AdminRegressionTestRunResponse | None = None
_lock = Lock()
FULL_RUN_MAX_TURNS_PER_USER = 24
FULL_RUN_STEP_NAMES = [
    "cleanup",
    "organization",
    "assessment_linear_employee",
    "assessment_manager",
    "assessment_leader",
    "assertions",
    "summary",
]


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _step(name: str, status: str, message: str) -> AdminRegressionTestStep:
    return AdminRegressionTestStep(name=name, status=status, message=message)


def _full_run_initial_steps() -> list[AdminRegressionTestStep]:
    return [
        _step(name, "pending", "Ожидает запуска.")
        for name in FULL_RUN_STEP_NAMES
    ]


def _set_step_status(steps: list[AdminRegressionTestStep], name: str, status: str, message: str) -> None:
    for step in steps:
        if step.name == name:
            step.status = status
            step.message = message
            return
    steps.append(_step(name, status, message))


def _publish_full_run_progress(
    *,
    started_at: datetime,
    start_time: float,
    steps: list[AdminRegressionTestStep],
    summary: str,
    organization_id: int | None = None,
    user_ids: list[int] | None = None,
    session_ids: list[int] | None = None,
) -> None:
    global _last_run
    _last_run = AdminRegressionTestRunResponse(
        status="running",
        title="Full regression",
        summary=summary,
        started_at=started_at,
        finished_at=None,
        duration_seconds=round(time.monotonic() - start_time, 2),
        organization_id=organization_id,
        user_ids=list(user_ids or []),
        session_ids=list(session_ids or []),
        steps=list(steps),
    )


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


def _create_autotest_users(connection) -> tuple[int, list[int], dict[int, str]]:
    _cleanup_autotest_data(connection)
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

    roles = {
        row["code"]: {"id": int(row["id"]), "name": row["name"]}
        for row in connection.execute("SELECT id, code, name FROM roles WHERE code IN ('linear_employee', 'manager', 'leader')").fetchall()
    }
    if len(roles) != 3:
        raise RuntimeError("Не найдены все системные роли для автотеста.")

    user_ids: list[int] = []
    role_by_user_id: dict[int, str] = {}
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
        role_by_user_id[user_id] = role_code
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
    return organization_id, user_ids, role_by_user_id


def _fetch_user(user_id: int) -> UserResponse:
    with get_connection() as connection:
        row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"Autotest user {user_id} not found")
    return UserResponse(**dict(row))


def _autotest_case_answer(role_code: str, case_title: str | None = None) -> str:
    fixture = _role_payload(role_code)
    title = str(case_title or "кейсу").strip()
    return (
        f"Автотестовый ответ по кейсу «{title}». "
        f"Роль: {fixture['position']}. "
        "Я фиксирую проблему, выделяю влияние на клиента и SLA, проверяю факты в CRM и сервис-деске, "
        "приоритизирую действия, назначаю ответственных, эскалирую риски и описываю ожидаемый результат. "
        "Критерии успеха: восстановление сервиса, прозрачная коммуникация, контроль сроков и предотвращение повторения."
    )


def _autotest_mbti_followup_answer(role_code: str) -> str:
    fixture = _role_payload(role_code)
    return (
        f"Для роли «{fixture['position']}» я обычно действую структурно: сначала собираю факты, затем сверяю риски, "
        "договариваюсь о плане и контролирую результат. В стрессовой ситуации предпочитаю ясные приоритеты, "
        "короткую коммуникацию и проверку гипотез на данных."
    )


def _run_full_assessment_for_user(user_id: int, role_code: str) -> tuple[int, int, int]:
    user = _fetch_user(user_id)
    response = interviewer_agent.start_case_interview(user=user)
    session_id = int(response.session_id)
    answered_cases: set[int] = set()
    completed_cases = 0

    for _ in range(FULL_RUN_MAX_TURNS_PER_USER):
        if response.assessment_completed:
            break
        case_id = int(response.session_case_id or 0)
        if response.case_completed:
            completed_cases += 1
        if response.mbti_followup_pending:
            message = _autotest_mbti_followup_answer(role_code)
        elif response.pending_auto_finish:
            message = "__auto_finish_case__"
        elif case_id and case_id in answered_cases:
            message = "__finish_case__"
        else:
            if case_id:
                answered_cases.add(case_id)
            message = _autotest_case_answer(role_code, response.case_title)

        response = interviewer_agent.continue_case_interview(session_code=response.session_code, message=message)

    if not response.assessment_completed:
        raise RuntimeError(f"Полный прогон для пользователя {user_id} не завершился за {FULL_RUN_MAX_TURNS_PER_USER} ходов.")

    with get_connection() as connection:
        case_count = int(
            connection.execute(
                "SELECT COUNT(*)::int AS count FROM session_cases WHERE session_id = %s AND status = 'completed'",
                (session_id,),
            ).fetchone()["count"]
            or 0
        )
        has_mbti = bool(
            connection.execute(
                "SELECT mbti_summary_json IS NOT NULL AS has_mbti FROM user_sessions WHERE id = %s",
                (session_id,),
            ).fetchone()["has_mbti"]
        )
    if case_count <= 0:
        raise RuntimeError(f"Для пользователя {user_id} не найдено завершенных кейсов.")
    if settings.mbti_enabled and not has_mbti:
        raise RuntimeError(f"Для пользователя {user_id} не сформирован MBTI summary.")
    return session_id, case_count, completed_cases


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
                organization_id, user_ids, _role_by_user_id = _create_autotest_users(connection)
                steps.append(_step("cleanup", "passed", "Предыдущие __autotest__ данные удалены."))
                steps.append(_step("organization", "passed", f"Создана организация {AUTOTEST_ORG_NAME}."))

                roles_by_id = {
                    int(row["id"]): int(row["role_id"])
                    for row in connection.execute("SELECT id, role_id FROM users WHERE id = ANY(%s)", (user_ids,)).fetchall()
                }
                for user_id in user_ids:
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
                        (f"__autotest__{secrets.token_hex(12)}", user_id, roles_by_id[user_id], _json(mbti_summary)),
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


def run_full_regression() -> AdminRegressionTestRunResponse:
    global _last_run

    with _lock:
        started_at = datetime.utcnow()
        start_time = time.monotonic()
        steps: list[AdminRegressionTestStep] = _full_run_initial_steps()
        user_ids: list[int] = []
        session_ids: list[int] = []
        organization_id: int | None = None
        status = "passed"

        try:
            _set_step_status(steps, "cleanup", "running", "Удаляем предыдущие __autotest__ данные и готовим организацию.")
            _publish_full_run_progress(
                started_at=started_at,
                start_time=start_time,
                steps=steps,
                summary="Полный регрессионный прогон запущен.",
            )
            with get_connection() as connection:
                organization_id, user_ids, role_by_user_id = _create_autotest_users(connection)
                connection.commit()
            _set_step_status(steps, "cleanup", "passed", "Предыдущие __autotest__ данные удалены.")
            _set_step_status(steps, "organization", "passed", f"Создана организация {AUTOTEST_ORG_NAME} и 3 пользователя.")
            _publish_full_run_progress(
                started_at=started_at,
                start_time=start_time,
                steps=steps,
                summary="Организация и пользователи созданы. Запускаем assessment-сессии.",
                organization_id=organization_id,
                user_ids=user_ids,
                session_ids=session_ids,
            )

            total_completed_cases = 0
            for user_id in user_ids:
                role_code = role_by_user_id[user_id]
                step_name = f"assessment_{role_code}"
                _set_step_status(steps, step_name, "running", f"Пользователь {user_id}: идет assessment-прогон.")
                _publish_full_run_progress(
                    started_at=started_at,
                    start_time=start_time,
                    steps=steps,
                    summary=f"Идет assessment-прогон для пользователя {user_id}.",
                    organization_id=organization_id,
                    user_ids=user_ids,
                    session_ids=session_ids,
                )
                session_id, case_count, _completed_during_loop = _run_full_assessment_for_user(user_id, role_code)
                session_ids.append(session_id)
                total_completed_cases += case_count
                _set_step_status(steps, step_name, "passed", f"Пользователь {user_id}: завершена сессия {session_id}, кейсов: {case_count}.")
                _publish_full_run_progress(
                    started_at=started_at,
                    start_time=start_time,
                    steps=steps,
                    summary=f"Пользователь {user_id} завершен. Продолжаем полный прогон.",
                    organization_id=organization_id,
                    user_ids=user_ids,
                    session_ids=session_ids,
                )

            _set_step_status(steps, "assertions", "running", "Проверяем completed-сессии и результаты кейсов.")
            _publish_full_run_progress(
                started_at=started_at,
                start_time=start_time,
                steps=steps,
                summary="Assessment-сессии завершены. Проверяем результаты.",
                organization_id=organization_id,
                user_ids=user_ids,
                session_ids=session_ids,
            )
            with get_connection() as connection:
                completed_sessions = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM user_sessions WHERE id = ANY(%s) AND status = 'completed'",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
                report_rows = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM session_case_results WHERE session_id = ANY(%s)",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
            if completed_sessions != len(user_ids):
                raise RuntimeError("Не все assessment-сессии завершены.")
            if report_rows <= 0:
                raise RuntimeError("Не сформированы результаты кейсов для отчетов.")
            _set_step_status(steps, "assertions", "passed", f"Проверены completed sessions: {completed_sessions}, case results: {report_rows}.")
            _set_step_status(steps, "summary", "passed", f"Полный прогон завершен: пользователей {len(user_ids)}, кейсов {total_completed_cases}.")
        except Exception as exc:
            status = "failed"
            running_step = next((step for step in steps if step.status == "running"), None)
            if running_step is not None:
                running_step.status = "failed"
                running_step.message = str(exc)
            else:
                steps.append(_step("failure", "failed", str(exc)))

        finished_at = datetime.utcnow()
        run = AdminRegressionTestRunResponse(
            status=status,
            title="Full regression",
            summary=(
                "Полный регрессионный прогон прошел успешно."
                if status == "passed"
                else "Полный регрессионный прогон завершился с ошибкой."
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
        subtitle="Smoke-проверки и полный прогон assessment-сценариев для автотестовых пользователей.",
        mbti_enabled=bool(settings.mbti_enabled),
        mbti_store_available=store_available,
        last_run=_last_run,
        cleanup_hint="Удаляются только данные с префиксом __autotest__.",
    )

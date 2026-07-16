from __future__ import annotations

import json
import secrets
import time
from datetime import datetime
from pathlib import Path
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
BASE_DIR = Path(__file__).resolve().parent.parent

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
OFFLINE_CASES_PER_USER = 2
OFFLINE_SKILLS_PER_USER = 3
OFFLINE_RUN_STEP_NAMES = [
    "cleanup",
    "organization",
    "fixtures",
    "sessions",
    "assertions",
    "summary",
]
TECHNICAL_TABLE_CHECKS = [
    "users",
    "user_identities",
    "web_user_sessions",
    "organizations",
    "organization_memberships",
    "roles",
    "skills",
    "assessment_level_weights",
    "user_role_profiles",
    "user_sessions",
    "session_cases",
    "session_case_messages",
    "session_case_results",
    "session_skill_assessments",
    "session_case_skill_analysis",
    "session_case_skills",
    "session_skills",
    "cases_registry",
    "case_texts",
    "case_type_passports",
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


def _offline_run_initial_steps() -> list[AdminRegressionTestStep]:
    return [
        _step(name, "pending", "Ожидает запуска.")
        for name in OFFLINE_RUN_STEP_NAMES
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


def _load_offline_skill_fixtures(connection, limit: int = OFFLINE_SKILLS_PER_USER) -> list[dict]:
    rows = connection.execute(
        """
        SELECT
            s.id AS skill_id,
            s.skill_code,
            s.skill_name,
            COALESCE(s.competency_name, '4K компетенции') AS competency_name,
            cs.id AS competency_skill_id
        FROM skills s
        LEFT JOIN competency_skills cs ON cs.skill_code = s.skill_code
        ORDER BY s.competency_name ASC NULLS LAST, s.id ASC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    fixtures = [dict(row) for row in rows]
    if not fixtures:
        raise RuntimeError("Не найдены skills для offline-регрессии.")
    return fixtures


def _offline_case_fixture(role_code: str, case_number: int) -> dict[str, str]:
    fixture = _role_payload(role_code)
    if case_number == 1:
        title = "Сбой клиентского сервиса и риск нарушения SLA"
        task = "Опишите решение по восстановлению сервиса, коммуникации с клиентом и контролю SLA."
        context = (
            "В телеком-сервисе Ростелеком-like возник массовый сбой. "
            "Клиенты обращаются в поддержку, SLA близок к нарушению, команда эксплуатации просит приоритизацию."
        )
    else:
        title = "Оценка идеи улучшения клиентского опыта"
        task = "Примите решение по идее улучшения и опишите план ограниченного внедрения."
        context = (
            "Команда предложила изменить процесс обработки повторных обращений. "
            "Нужно оценить влияние на клиентов, нагрузку команды, метрики качества и риски внедрения."
        )
    answer = (
        f"Роль: {fixture['position']}. "
        f"По кейсу «{title}» я фиксирую факты, выделяю влияние на клиента и SLA, назначаю ответственных, "
        "согласую короткий план действий, задаю контрольные точки, прозрачно коммуницирую риски и проверяю результат по данным CRM."
    )
    return {"title": title, "task": task, "context": context, "answer": answer}


def _insert_offline_case(
    connection,
    *,
    session_id: int,
    user_id: int,
    role_id: int,
    role_code: str,
    case_number: int,
    skill_fixtures: list[dict],
) -> int:
    fixture = _offline_case_fixture(role_code, case_number)
    session_case_row = connection.execute(
        """
        INSERT INTO session_cases (
            session_id, user_id, role_id, status, selection_reason,
            planned_duration_minutes, started_at, completed_at, actual_duration_seconds
        )
        VALUES (%s, %s, %s, 'answered', %s, 10, NOW(), NOW(), 120)
        RETURNING id
        """,
        (session_id, user_id, role_id, "__autotest__ offline fixture"),
    ).fetchone()
    session_case_id = int(session_case_row["id"])
    connection.execute(
        """
        INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
        VALUES (%s, %s, 'assistant', %s), (%s, %s, 'user', %s)
        """,
        (
            session_case_id,
            session_id,
            fixture["context"] + "\n\n" + fixture["task"],
            session_case_id,
            session_id,
            fixture["answer"],
        ),
    )
    connection.execute(
        """
        INSERT INTO session_case_results (
            session_case_id, session_id, user_id, result_status, completion_score, evaluator_summary, passed_at
        )
        VALUES (%s, %s, %s, 'passed', 0.82, %s, NOW())
        ON CONFLICT (session_case_id) DO UPDATE SET
            result_status = EXCLUDED.result_status,
            completion_score = EXCLUDED.completion_score,
            evaluator_summary = EXCLUDED.evaluator_summary,
            passed_at = EXCLUDED.passed_at
        """,
        (session_case_id, session_id, user_id, "__autotest__ offline case result"),
    )
    for skill in skill_fixtures:
        skill_id = int(skill["skill_id"])
        connection.execute(
            """
            INSERT INTO session_case_skills (session_case_id, skill_id, coverage_status)
            VALUES (%s, %s, 'covered')
            ON CONFLICT (session_case_id, skill_id) DO UPDATE SET coverage_status = EXCLUDED.coverage_status
            """,
            (session_case_id, skill_id),
        )
        connection.execute(
            """
            INSERT INTO session_case_skill_analysis (
                session_id, user_id, session_case_id, skill_id, competency_name,
                artifact_compliance_percent, structural_elements, detected_required_blocks,
                missing_required_blocks, block_coverage_percent, red_flags, found_evidence,
                detected_signals, evidence_excerpt, source_message_count
            )
            VALUES (%s, %s, %s, %s, %s, 82, %s, %s, %s, 85, %s, %s, %s, %s, 1)
            ON CONFLICT (session_case_id, skill_id) DO UPDATE SET
                artifact_compliance_percent = EXCLUDED.artifact_compliance_percent,
                structural_elements = EXCLUDED.structural_elements,
                detected_required_blocks = EXCLUDED.detected_required_blocks,
                missing_required_blocks = EXCLUDED.missing_required_blocks,
                block_coverage_percent = EXCLUDED.block_coverage_percent,
                red_flags = EXCLUDED.red_flags,
                found_evidence = EXCLUDED.found_evidence,
                detected_signals = EXCLUDED.detected_signals,
                evidence_excerpt = EXCLUDED.evidence_excerpt,
                source_message_count = EXCLUDED.source_message_count,
                updated_at = NOW()
            """,
            (
                session_id,
                user_id,
                session_case_id,
                skill_id,
                skill["competency_name"],
                _json({"offline": True, "has_decision": True, "has_plan": True}),
                _json(["решение", "план", "контроль SLA"]),
                _json([]),
                _json([]),
                _json(["фиксирует факты", "назначает ответственных", "контролирует результат"]),
                _json(["decision", "communication", "control"]),
                fixture["answer"][:240],
            ),
        )
    return session_case_id


def _insert_offline_skill_assessments(
    connection,
    *,
    session_id: int,
    user_id: int,
    skill_fixtures: list[dict],
    session_case_ids: list[int],
) -> None:
    for index, skill in enumerate(skill_fixtures):
        level_code = "L3" if index == 0 else "L2"
        level_name = "Уверенный уровень" if level_code == "L3" else "Рабочий уровень"
        connection.execute(
            """
            INSERT INTO session_skill_assessments (
                session_id, user_id, skill_id, competency_skill_id, competency_name, skill_code, skill_name,
                assessed_level_code, assessed_level_name, rubric_match_scores, structural_elements,
                red_flags, found_evidence, detected_required_blocks, missing_required_blocks,
                block_coverage_percent, rationale, evidence_excerpt, source_session_case_ids
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, skill_id)
            DO UPDATE SET
                competency_skill_id = EXCLUDED.competency_skill_id,
                competency_name = EXCLUDED.competency_name,
                skill_code = EXCLUDED.skill_code,
                skill_name = EXCLUDED.skill_name,
                assessed_level_code = EXCLUDED.assessed_level_code,
                assessed_level_name = EXCLUDED.assessed_level_name,
                rubric_match_scores = EXCLUDED.rubric_match_scores,
                structural_elements = EXCLUDED.structural_elements,
                red_flags = EXCLUDED.red_flags,
                found_evidence = EXCLUDED.found_evidence,
                detected_required_blocks = EXCLUDED.detected_required_blocks,
                missing_required_blocks = EXCLUDED.missing_required_blocks,
                block_coverage_percent = EXCLUDED.block_coverage_percent,
                rationale = EXCLUDED.rationale,
                evidence_excerpt = EXCLUDED.evidence_excerpt,
                source_session_case_ids = EXCLUDED.source_session_case_ids,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                user_id,
                int(skill["skill_id"]),
                int(skill["competency_skill_id"]) if skill.get("competency_skill_id") is not None else None,
                skill["competency_name"],
                skill["skill_code"],
                skill["skill_name"],
                level_code,
                level_name,
                _json({"L1": 1, "L2": 2, "L3": 1 if level_code == "L3" else 0}),
                _json({"offline": True, "has_structure": True, "has_evidence": True}),
                _json([]),
                _json(["Фикстурный ответ содержит решение, коммуникацию, контроль сроков и критерии результата."]),
                _json(["решение", "план", "контроль"]),
                _json([]),
                85,
                "__autotest__ offline оценка без вызова LLM.",
                "Фикстурный ответ: решение, план, ответственные, контроль результата.",
                _json(session_case_ids),
            ),
        )


def _technical_file_step(name: str, relative_path: str) -> AdminRegressionTestStep:
    path = BASE_DIR / relative_path
    if path.is_file() and path.stat().st_size > 0:
        return _step(name, "passed", f"{relative_path}: найден, размер {path.stat().st_size} байт.")
    return _step(name, "failed", f"{relative_path}: файл не найден или пустой.")


def _technical_table_step(connection, table_name: str) -> AdminRegressionTestStep:
    exists_row = connection.execute("SELECT to_regclass(%s) AS reg", (table_name,)).fetchone()
    if not exists_row or not exists_row["reg"]:
        return _step(f"table_{table_name}", "failed", f"Таблица {table_name} не найдена.")
    count_row = connection.execute(f"SELECT COUNT(*)::int AS count FROM {table_name}").fetchone()
    return _step(f"table_{table_name}", "passed", f"Таблица {table_name}: строк {int(count_row['count'] or 0)}.")


def _technical_data_step(connection, name: str, sql: str, success_message: str, failure_message: str) -> AdminRegressionTestStep:
    row = connection.execute(sql).fetchone()
    value = int(row["count"] or 0) if row and "count" in row else 0
    if value > 0:
        return _step(name, "passed", f"{success_message}: {value}.")
    return _step(name, "failed", failure_message)


def run_technical_regression() -> AdminRegressionTestRunResponse:
    global _last_run

    with _lock:
        started_at = datetime.utcnow()
        start_time = time.monotonic()
        steps: list[AdminRegressionTestStep] = [
            _technical_file_step("file_index_html", "web/index.html"),
            _technical_file_step("file_dist_main_js", "web/dist/main.js"),
            _technical_file_step("file_chat_css", "web/styles/screens/chat.css"),
            _technical_file_step("file_admin_css", "web/styles/screens/admin.css"),
            _technical_file_step("file_personal_data_consent_pdf", "web/assets/docs/personal-data-consent.pdf"),
        ]
        try:
            with get_connection() as connection:
                steps.extend(_technical_table_step(connection, table_name) for table_name in TECHNICAL_TABLE_CHECKS)
                steps.extend(
                    [
                        _technical_data_step(
                            connection,
                            "data_roles",
                            "SELECT COUNT(*)::int AS count FROM roles WHERE code IN ('linear_employee', 'manager', 'leader')",
                            "Базовые роли assessment найдены",
                            "Не найдены все базовые роли assessment.",
                        ),
                        _technical_data_step(
                            connection,
                            "data_skills",
                            "SELECT COUNT(*)::int AS count FROM skills WHERE COALESCE(skill_code, '') <> ''",
                            "Skills с кодами найдены",
                            "Не найдены skills с кодами.",
                        ),
                        _technical_data_step(
                            connection,
                            "data_level_weights",
                            "SELECT COUNT(*)::int AS count FROM assessment_level_weights WHERE level_code IN ('L1', 'L2', 'L3')",
                            "Веса уровней оценки найдены",
                            "Не найдены веса уровней L1/L2/L3.",
                        ),
                        _technical_data_step(
                            connection,
                            "data_case_registry",
                            "SELECT COUNT(*)::int AS count FROM cases_registry",
                            "Кейсы в registry найдены",
                            "В cases_registry нет кейсов.",
                        ),
                        _technical_data_step(
                            connection,
                            "data_prompt_profiles",
                            "SELECT COUNT(*)::int AS count FROM assessment_agent_prompt_profiles WHERE is_active IS TRUE",
                            "Активные prompt profiles найдены",
                            "Не найдены активные prompt profiles.",
                        ),
                    ]
                )
        except Exception as exc:
            steps.append(_step("technical_failure", "failed", str(exc)))

        failed_steps = [step for step in steps if str(step.status).lower() != "passed"]
        status = "failed" if failed_steps else "passed"
        finished_at = datetime.utcnow()
        run = AdminRegressionTestRunResponse(
            status=status,
            title="Technical regression 30",
            summary=(
                "Техническая проверка 30 контуров прошла успешно."
                if status == "passed"
                else f"Техническая проверка нашла проблем: {len(failed_steps)}."
            ),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - start_time, 2),
            steps=steps,
        )
        _last_run = run
        return run


def run_offline_regression() -> AdminRegressionTestRunResponse:
    global _last_run

    with _lock:
        started_at = datetime.utcnow()
        start_time = time.monotonic()
        steps: list[AdminRegressionTestStep] = _offline_run_initial_steps()
        user_ids: list[int] = []
        session_ids: list[int] = []
        organization_id: int | None = None
        status = "passed"
        total_cases = 0

        try:
            _set_step_status(steps, "cleanup", "running", "Удаляем старые __autotest__ данные.")
            with get_connection() as connection:
                organization_id, user_ids, role_by_user_id = _create_autotest_users(connection)
                _set_step_status(steps, "cleanup", "passed", "Предыдущие __autotest__ данные удалены.")
                _set_step_status(steps, "organization", "passed", f"Создана организация {AUTOTEST_ORG_NAME} и 3 пользователя.")

                skill_fixtures = _load_offline_skill_fixtures(connection)
                _set_step_status(steps, "fixtures", "passed", f"Загружено skills для offline-оценок: {len(skill_fixtures)}.")

                roles_by_id = {
                    int(row["id"]): int(row["role_id"])
                    for row in connection.execute("SELECT id, role_id FROM users WHERE id = ANY(%s)", (user_ids,)).fetchall()
                }
                _set_step_status(steps, "sessions", "running", "Создаем completed-сессии, кейсы, ответы и оценки без LLM.")
                for user_id in user_ids:
                    role_id = roles_by_id[user_id]
                    role_code = role_by_user_id[user_id]
                    mbti_summary = {
                        "общий_итог": {
                            "оценка": 62,
                            "темперамент": "__autotest__ offline",
                            "краткий_вывод": "Offline-регрессия создала MBTI-сводку без вызова LLM.",
                        }
                    }
                    session_row = connection.execute(
                        """
                        INSERT INTO user_sessions (
                            session_code, user_id, role_id, status, source, notes,
                            assessment_code, started_at, finished_at, mbti_summary_json
                        )
                        VALUES (%s, %s, %s, 'completed', '__autotest__offline', 'Offline regression fixture session', 'competencies_4k', NOW(), NOW(), %s::jsonb)
                        RETURNING id
                        """,
                        (f"__autotest__offline{secrets.token_hex(12)}", user_id, role_id, _json(mbti_summary)),
                    ).fetchone()
                    session_id = int(session_row["id"])
                    session_ids.append(session_id)
                    for skill in skill_fixtures:
                        connection.execute(
                            """
                            INSERT INTO session_skills (session_id, skill_id, status, assigned_case_count, completed_case_count, covered_at)
                            VALUES (%s, %s, 'covered', %s, %s, NOW())
                            ON CONFLICT (session_id, skill_id) DO UPDATE SET
                                status = EXCLUDED.status,
                                assigned_case_count = EXCLUDED.assigned_case_count,
                                completed_case_count = EXCLUDED.completed_case_count,
                                covered_at = EXCLUDED.covered_at
                            """,
                            (session_id, int(skill["skill_id"]), OFFLINE_CASES_PER_USER, OFFLINE_CASES_PER_USER),
                        )
                    session_case_ids = [
                        _insert_offline_case(
                            connection,
                            session_id=session_id,
                            user_id=user_id,
                            role_id=role_id,
                            role_code=role_code,
                            case_number=case_number,
                            skill_fixtures=skill_fixtures,
                        )
                        for case_number in range(1, OFFLINE_CASES_PER_USER + 1)
                    ]
                    total_cases += len(session_case_ids)
                    _insert_offline_skill_assessments(
                        connection,
                        session_id=session_id,
                        user_id=user_id,
                        skill_fixtures=skill_fixtures,
                        session_case_ids=session_case_ids,
                    )

                _set_step_status(steps, "sessions", "passed", f"Созданы completed-сессии: {len(session_ids)}, кейсов: {total_cases}.")

                completed_sessions = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM user_sessions WHERE id = ANY(%s) AND status = 'completed'",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
                completed_cases = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM session_cases WHERE session_id = ANY(%s) AND status = 'answered'",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
                result_rows = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM session_case_results WHERE session_id = ANY(%s)",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
                skill_rows = int(
                    connection.execute(
                        "SELECT COUNT(*)::int AS count FROM session_skill_assessments WHERE session_id = ANY(%s)",
                        (session_ids,),
                    ).fetchone()["count"]
                    or 0
                )
                if completed_sessions != len(user_ids):
                    raise RuntimeError("Offline-проверка completed sessions не прошла.")
                if completed_cases != len(user_ids) * OFFLINE_CASES_PER_USER or result_rows != completed_cases:
                    raise RuntimeError("Offline-проверка кейсов/результатов не прошла.")
                if skill_rows < len(user_ids):
                    raise RuntimeError("Offline-проверка skill assessments не прошла.")
                _set_step_status(steps, "assertions", "passed", f"Проверены sessions={completed_sessions}, cases={completed_cases}, results={result_rows}, skills={skill_rows}.")
                _set_step_status(steps, "summary", "passed", "Offline-регрессия без LLM и генерации кейсов прошла успешно.")
                connection.commit()
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
            title="Offline regression",
            summary=(
                "Быстрый offline-прогон без LLM прошел успешно."
                if status == "passed"
                else "Offline-прогон завершился с ошибкой."
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
        case_summary = connection.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE sc.status IN ('completed', 'answered', 'assessed'))::int AS completed_count,
                COUNT(scr.id)::int AS result_count,
                COALESCE(
                    jsonb_object_agg(sc.status, status_counts.count) FILTER (WHERE sc.status IS NOT NULL),
                    '{}'::jsonb
                ) AS status_counts
            FROM session_cases sc
            LEFT JOIN session_case_results scr ON scr.session_case_id = sc.id
            LEFT JOIN (
                SELECT status, COUNT(*)::int AS count
                FROM session_cases
                WHERE session_id = %s
                GROUP BY status
            ) status_counts ON status_counts.status = sc.status
            WHERE sc.session_id = %s
            """,
            (session_id, session_id),
        ).fetchone()
        case_count = int(case_summary["completed_count"] or 0)
        result_count = int(case_summary["result_count"] or 0)
        status_counts = dict(case_summary["status_counts"] or {})
        session_row = connection.execute(
            "SELECT status, mbti_summary_json IS NOT NULL AS has_mbti FROM user_sessions WHERE id = %s",
            (session_id,),
        ).fetchone()
        if session_row is None:
            raise RuntimeError(f"Для пользователя {user_id} не найдена assessment-сессия {session_id}.")
        session_status = str(session_row["status"] or "")
        has_mbti = bool(session_row["has_mbti"])
        if case_count <= 0 and session_status == "completed" and result_count > 0:
            case_count = result_count
        if case_count <= 0:
            raw_case_count = int(
                connection.execute(
                    "SELECT COUNT(*)::int AS count FROM session_cases WHERE session_id = %s",
                    (session_id,),
                ).fetchone()["count"]
                or 0
            )
            raise RuntimeError(
                f"Для пользователя {user_id} не найдено завершенных кейсов. "
                f"session_id={session_id}, session_status={session_status}, "
                f"cases_total={raw_case_count}, case_statuses={status_counts}, results={result_count}."
            )
        if result_count <= 0:
            raise RuntimeError(
                f"Для пользователя {user_id} не сформированы результаты кейсов. "
                f"session_id={session_id}, session_status={session_status}, case_statuses={status_counts}."
            )
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

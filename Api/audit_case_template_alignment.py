from __future__ import annotations

import argparse
import json
import re
from typing import Any

from Api.database import get_connection
from Api.deepseek_client import deepseek_client
from Api.schemas import UserResponse


BROKEN_PATTERNS: tuple[tuple[str, str], ...] = (
    ("leftover_placeholders", r"\{[^{}]+\}"),
    ("broken_role_marker", r"исполнителяeader|leader\b"),
    ("bad_deadline", r"\bк до \d{1,2}:\d{2}\b"),
    ("broken_stakeholder_phrase", r"\bот пользователи\b|\bот пользователь\b"),
    ("broken_channel_phrase", r"\bчерез в\b"),
    ("broken_access_phrase", r"\bкарточка заявки, истор(?:ия|ии)\b"),
    ("broken_escalation_phrase", r"\bэскалировать вопрос вторая\b"),
    ("dangling_now", r"(?:,|\s)и сейчас\.$"),
)


def _load_user(phone: str) -> tuple[UserResponse, str | None, dict[str, Any] | None]:
    with get_connection() as connection:
        user_row = connection.execute(
            """
            SELECT u.id, u.full_name, u.email, u.created_at, u.role_id, u.job_description,
                   p.raw_position, p.raw_duties, p.normalized_duties,
                   p.role_confidence, p.role_rationale,
                   u.active_profile_id, u.phone, u.company_industry, u.avatar_data_url
            FROM users u
            LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
            WHERE u.phone = %s
            LIMIT 1
            """,
            (phone,),
        ).fetchone()
        if not user_row:
            raise SystemExit(f"User with phone {phone} not found")
        user = UserResponse(**dict(user_row))

        role_row = connection.execute(
            "SELECT name FROM roles WHERE id = %s",
            (user.role_id,),
        ).fetchone()
        role_name = role_row["name"] if role_row else None

        profile_row = connection.execute(
            """
            SELECT user_domain, user_processes, user_tasks, user_stakeholders,
                   user_risks, user_constraints, user_context_vars, role_limits,
                   role_vocabulary, role_skill_profile
            FROM user_role_profiles
            WHERE id = %s
            """,
            (user.active_profile_id,),
        ).fetchone() if user.active_profile_id else None
        user_profile = dict(profile_row) if profile_row else None
        return user, role_name, user_profile


def _load_templates(limit_type: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT
            ct.case_text_code,
            ct.intro_context,
            ct.task_for_user,
            cr.case_id_code,
            cr.title,
            p.type_code
        FROM case_texts ct
        LEFT JOIN cases_registry cr ON cr.id = ct.cases_registry_id
        LEFT JOIN case_type_passports p ON p.id = cr.case_type_passport_id
    """
    params: tuple[Any, ...] = ()
    if limit_type:
        query += " WHERE p.type_code = %s"
        params = (limit_type.upper(),)
    query += " ORDER BY p.type_code, ct.case_text_code"
    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def _generate_for_template(user: UserResponse, role_name: str | None, user_profile: dict[str, Any] | None, template_row: dict[str, Any]) -> tuple[dict[str, str], str, str]:
    return deepseek_client.build_personalized_case_materials(
        full_name=user.full_name,
        position=user.raw_position or user.job_description,
        duties=user.normalized_duties or user.raw_duties,
        company_industry=user.company_industry,
        role_name=role_name,
        user_profile=user_profile,
        case_type_code=template_row.get("type_code"),
        case_title=template_row.get("title") or template_row.get("case_id_code") or template_row.get("case_text_code"),
        case_context=template_row.get("intro_context") or "",
        case_task=template_row.get("task_for_user") or "",
    )


def _find_issues(*, type_code: str | None, template_text: str, generated_text: str, generated_task: str, template_task: str) -> list[str]:
    issues: list[str] = []
    lower_generated = generated_text.lower()

    for code, pattern in BROKEN_PATTERNS:
        if re.search(pattern, generated_text, flags=re.IGNORECASE):
            issues.append(code)

    if not generated_text.strip():
        issues.append("empty_context")

    if not generated_task.strip():
        issues.append("empty_task")

    if template_task.strip() and generated_task.strip() != template_task.strip():
        issues.append("task_mismatch")

    if str(type_code or "").upper() == "F02":
        if "«" not in generated_text or "»" not in generated_text:
            issues.append("missing_request_quote")
        if not any(marker in lower_generated for marker in ("неясно", "нет ясного", "не определено")):
            issues.append("missing_ambiguity_block")
    if str(type_code or "").upper() == "F09":
        if "узкое место" not in lower_generated and "столкнулись с проблемой" not in lower_generated:
            issues.append("missing_bottleneck_block")
        if "огранич" not in lower_generated and "жёстких рамках" not in lower_generated and "жестких рамках" not in lower_generated:
            issues.append("missing_constraint_block")
    if str(type_code or "").upper() == "F11":
        if "эскал" not in lower_generated:
            issues.append("missing_escalation")
        if not any(marker in lower_generated for marker in ("не совпадают", "противореч", "не подтвержд")):
            issues.append("missing_mismatch")
        if not any(marker in lower_generated for marker in ("нельзя передавать дальше", "нельзя закрывать", "нельзя продолжать")):
            issues.append("missing_blocking_rule")

    # Flag overly short outputs for templates that should keep multi-block structure.
    if len(generated_text.strip()) < 160 and str(type_code or "").upper() in {"F05", "F08", "F09", "F10", "F11"}:
        issues.append("too_short_for_template")

    return sorted(set(issues))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", default="89874911124")
    parser.add_argument("--type", dest="type_code", default=None)
    parser.add_argument("--only-broken", action="store_true")
    parser.add_argument("--fallback-only", action="store_true")
    args = parser.parse_args()

    if args.fallback_only:
        deepseek_client.api_key = ""

    user, role_name, user_profile = _load_user(args.phone)
    templates = _load_templates(args.type_code)

    report: list[dict[str, Any]] = []
    for template_row in templates:
        _, context_text, task_text = _generate_for_template(user, role_name, user_profile, template_row)
        issues = _find_issues(
            type_code=template_row.get("type_code"),
            template_text=template_row.get("intro_context") or "",
            generated_text=context_text,
            generated_task=task_text,
            template_task=template_row.get("task_for_user") or "",
        )
        item = {
            "type_code": template_row.get("type_code"),
            "case_id_code": template_row.get("case_id_code"),
            "case_text_code": template_row.get("case_text_code"),
            "title": template_row.get("title"),
            "issues": issues,
            "generated_context": context_text,
            "generated_task": task_text,
        }
        if not args.only_broken or issues:
            report.append(item)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

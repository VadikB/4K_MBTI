"""Read-only participant projection; no preparation, presentation or time commands."""
from Api import m7_planning_repository


def assignment_contact(connection, *, user_id: int, organization_id: int | None) -> dict | None:
    if organization_id is None:
        return None
    row = connection.execute("""SELECT organization.name AS organization_name,
            NULLIF(BTRIM(contact.full_name), '') AS name, contact.email
        FROM organization_memberships admin
        JOIN organizations organization ON organization.id=admin.organization_id AND organization.is_active
        JOIN users contact ON contact.id=admin.user_id
        WHERE admin.organization_id=%s AND admin.role='admin'
          AND EXISTS (SELECT 1 FROM organization_memberships participant
            WHERE participant.organization_id=organization.id AND participant.user_id=%s)
        ORDER BY COALESCE(admin.admitted_at,admin.created_at),admin.id
        LIMIT 1""", (organization_id, user_id)).fetchone()
    return dict(row) if row else None


def assessment_rules(source: dict) -> dict | None:
    rules = {key: source[key] for key in ('time_budget_seconds', 'calendar_window_seconds')
             if type(source.get(key)) is int and source[key] > 0}
    notice = source.get('participant_notice')
    if isinstance(notice, str) and notice.strip():
        rules['participant_notice'] = notice
    return rules or None


def saved_cycle_plan(connection, cycle: dict) -> tuple[dict, list[dict]] | None:
    try:
        saved = m7_planning_repository.read_plan(connection, str(cycle["cycle_id"]))
    except ValueError:
        # A missing/invalid saved plan is unknown, never a materialized-AS fallback.
        return None
    content = saved["content_json"]
    route = content.get("route") if isinstance(content, dict) else None
    if (saved["cycle_db_id"] != cycle["id"] or not isinstance(route, list) or not route
            or not all(isinstance(item, dict) for item in route)
            or saved["profile_ref_json"] != cycle["profile_ref_json"]):
        return None
    return saved, route


def cycle_progress(connection, cycle: dict) -> dict:
    result = {"planned_total": None, "current_position_no": None,
              "last_completed_position_no": None, "completed_positions": None,
              "plan_revision_id": None, "between_situations": False, "rules": None}
    plan = saved_cycle_plan(connection, cycle)
    if plan is None:
        return result
    saved, route = plan
    content = saved["content_json"]
    result.update(planned_total=len(route), plan_revision_id=str(saved["revision_id"]),
                  completed_positions=0, rules=assessment_rules(content))
    positions = connection.execute("""SELECT p.position_no,p.state,p.plan_revision_id,
            p.case_id,p.case_version,s.status AS as_status,s.started_at,s.scenario_ended_at
        FROM m7_route_positions p
        LEFT JOIN m5_assessment_situations s ON s.id=p.current_as_db_id AND s.cycle_db_id=p.cycle_db_id
        WHERE p.cycle_db_id=%s ORDER BY p.position_no""", (cycle["id"],)).fetchall()
    for position in positions:
        number = position["position_no"]
        valid = (type(number) is int and 1 <= number <= len(route)
                 and str(position["plan_revision_id"]) == result["plan_revision_id"]
                 and position["started_at"] is not None)
        if valid:
            planned = route[number - 1]
            valid = (position["case_id"], str(position["case_version"])) == (
                planned.get("case_id"), str(planned.get("case_version")))
        if not valid:
            if position["state"] == "completed":
                result["completed_positions"] = None
            continue
        if position["as_status"] == "closed":
            result["last_completed_position_no"] = number
            # Finish closes the AS before the next command advances its route position.
            confirmed = (position["state"] == "completed" or
                         (position["state"] == "in_progress" and position["scenario_ended_at"] is not None))
            if confirmed and result["completed_positions"] is not None:
                result["completed_positions"] += 1
        elif position["state"] == "completed":
            result["completed_positions"] = None
        elif (position["state"] in {"in_progress", "awaiting_replacement"}
              and position["as_status"] in {"active", "paused", "scenario_ended"}
              and result["current_position_no"] is None):
            result["current_position_no"] = number
    # An unresolvable current AS is unknown, not proof of a between-AS break.
    result["between_situations"] = bool(result["last_completed_position_no"] and not any(
        row["started_at"] is not None and row["as_status"] in {"active", "paused", "scenario_ended"}
        for row in positions))
    return result


def preparation_state(model: dict) -> tuple[str, str, str, str | None, str | None]:
    """Use the same saved acquaintance/readiness projection as the ready screen."""
    early = model["readiness"]
    if early["status"] == "waiting_for_assignment":
        return ("unassigned", "Оценка пока не назначена",
                "Когда вам назначат оценку, она появится здесь.", None, None)
    if str(early.get("reason", "")).startswith("participant_fields:"):
        return ("participant_details_required", "Нужно уточнить сведения участника",
                "Организация дополняет необходимые сведения для вашей оценки.", None, None)
    if early["status"] != "ready":
        return ("organization_preparing", "Нужны сведения организации",
                "Организация завершает подготовку вашей оценки.", None, None)
    if not model.get("mandatory_complete"):
        return ("acquaintance", "Знакомство с оценкой",
                "Перед началом познакомьтесь с форматом оценки.", "acquaintance", "Продолжить знакомство")
    if model.get("late_readiness", {}).get("status") != "ready_to_prepare":
        return ("organization_preparing", "Нужны сведения организации",
                "Организация завершает настройку вашей оценки.", "open_readiness", "Проверить готовность")
    operation = model.get("preparation_operation") or {}
    if operation.get("status") == "failed":
        return ("preparation_failed", "Не удалось подготовить оценку",
                "Ваши ответы сохранены. Откройте готовность, чтобы проверить состояние.",
                "open_readiness", "Проверить состояние")
    return ("preparing", "Подготовка оценки",
            "Готовим план и первую ситуацию. Ваши ответы знакомства сохранены. Время оценки ещё не идёт.",
            "open_readiness", "Посмотреть состояние")

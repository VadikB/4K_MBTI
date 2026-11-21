from __future__ import annotations

from copy import deepcopy
from uuid import UUID


ACCESS_CONTRACT_VERSION = "m8-report-access/1.1.0"

# Keep the customer registry and the participant row on the same saved publication.
CUSTOMER_REPORT_FOR_CYCLE_SQL = """
    SELECT p.id,p.status,p.c67_json,rr.payload_json,
           p.status IN ('ready','limited','no_result')
             AND COALESCE(p.c67_json->'processing'->>'status','') <> 'failed' AS can_open
    FROM m8_results r JOIN m8_result_revisions rr ON rr.results_id=r.id
    JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
    WHERE r.cycle_db_id=cycle.id
    ORDER BY (p.id=(SELECT current.report_id FROM m8_published_reports current
                    WHERE current.cycle_db_id=cycle.id)) DESC NULLS LAST,
             rr.revision_no DESC,p.revision_no DESC
    LIMIT 1
"""


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_access_events (
        id BIGSERIAL PRIMARY KEY,
        report_id UUID NOT NULL REFERENCES m8_reports(id) ON DELETE RESTRICT,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        channel TEXT NOT NULL CHECK (channel IN ('api','pdf')),
        accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        contract_version TEXT NOT NULL)""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m8_report_access_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M8 report access history is immutable'; END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_m8_report_access_events ON m8_report_access_events")
    connection.execute("""CREATE TRIGGER immutable_m8_report_access_events BEFORE UPDATE OR DELETE
        ON m8_report_access_events FOR EACH ROW EXECUTE FUNCTION prevent_m8_report_access_history_change()""")


def customer_can_read_report(connection, *, report_id: str, user_id: int) -> bool:
    row = connection.execute("""SELECT 1 FROM m8_reports p
        JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
        JOIN m8_results r ON r.id=rr.results_id
        JOIN m5_cycles cycle ON cycle.id=r.cycle_db_id
        JOIN organization_memberships membership ON membership.organization_id=cycle.organization_id
            AND membership.user_id=%s AND membership.role='admin'
        JOIN organizations organization ON organization.id=cycle.organization_id AND organization.is_active=TRUE
        WHERE p.id=%s AND p.audience='assessee' AND p.status IN ('ready','limited','no_result')
          AND cycle.collection_closed_at IS NOT NULL
          AND COALESCE(p.c67_json->'processing'->>'status','') <> 'failed'""",
        (user_id, UUID(str(report_id)))).fetchone()
    return bool(row)


def record_access(connection, *, report_id: str, user_id: int, channel: str) -> None:
    if channel not in {"api", "pdf"}:
        raise ValueError("REPORT_ACCESS_CHANNEL_INVALID")
    connection.execute("""INSERT INTO m8_report_access_events(report_id,user_id,channel,contract_version)
        VALUES(%s,%s,%s,%s)""", (UUID(str(report_id)), user_id, channel, ACCESS_CONTRACT_VERSION))


def page_customer_reports(connection, *, user_id: int, organization_id: int | None = None,
                          query: str = "", program: str = "", program_definition_id: int | None = None,
                          status: str = "",
                          page: int = 1, page_size: int = 12) -> dict:
    """Closed assessment Cycles in one authorized organization; one row per Cycle."""
    if status not in {"", "preparing", "ready", "failed"}:
        raise ValueError("REPORT_STATUS_INVALID")
    organizations = [dict(row) for row in connection.execute("""SELECT organization.id,organization.name
        FROM organizations organization JOIN organization_memberships membership
          ON membership.organization_id=organization.id
        WHERE membership.user_id=%s AND membership.role='admin' AND organization.is_active=TRUE
        ORDER BY organization.name,organization.id""", (user_id,)).fetchall()]
    allowed = {int(item["id"]) for item in organizations}
    selected = organization_id if organization_id is not None else (int(organizations[0]["id"]) if organizations else None)
    if selected is not None and selected not in allowed:
        raise PermissionError("REPORT_ORGANIZATION_FORBIDDEN")
    if selected is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size,
                "organization_id": None, "organizations": organizations, "programs": []}

    base = f"""FROM m5_cycles cycle
        JOIN users u ON u.id=cycle.owner_user_id
        JOIN organization_memberships membership ON membership.organization_id=cycle.organization_id
          AND membership.user_id=%s AND membership.role='admin'
        JOIN organizations organization ON organization.id=cycle.organization_id AND organization.is_active=TRUE
        LEFT JOIN m10_pipeline_runs pipeline ON pipeline.cycle_db_id=cycle.id
        LEFT JOIN LATERAL ({CUSTOMER_REPORT_FOR_CYCLE_SQL}) report ON TRUE
        WHERE cycle.organization_id=%s AND cycle.usage_scope='assessment' AND cycle.collection_closed_at IS NOT NULL"""
    program_expr = "COALESCE(report.c67_json->'display'->>'program_name',cycle.display_snapshot_json->>'program_name','')"
    name_expr = "COALESCE(to_jsonb(u)->>'full_name','')"
    status_expr = """CASE WHEN report.can_open THEN 'ready' WHEN pipeline.status='failed' OR cycle.status='failed'
            OR report.c67_json->'processing'->>'status'='failed'
          THEN 'failed' ELSE 'preparing' END"""
    source = f"SELECT cycle.id,cycle.cycle_id,cycle.collection_closed_at,{name_expr} AS full_name,\n" \
        f"{program_expr} AS program_name,{status_expr} AS status,\n" \
        "report.id AS report_id " + base
    programs = [row["program_name"] for row in connection.execute(
        f"SELECT DISTINCT program_name FROM ({source}) cycles WHERE program_name<>'' ORDER BY program_name",
        (user_id, selected)).fetchall()]
    conditions = []
    params: list = [user_id, selected]
    if query.strip():
        conditions.append("full_name ILIKE %s")
        params.append("%" + query.strip() + "%")
    if program:
        conditions.append("program_name=%s")
        params.append(program)
    if program_definition_id is not None:
        # The initial plan freezes the program. Later parameter revisions can
        # drop the binding, and the organization's current connection can change.
        conditions.append("""EXISTS (
            SELECT 1 FROM m7_cycle_plans plan
            JOIN m7_plan_revisions revision ON revision.plan_id=plan.id AND revision.revision_no=1
            WHERE plan.cycle_db_id=cycles.id
              AND revision.content_json->'pilot_plan_binding'->>'contract'='m7_pilot_plan_binding/1'
              AND revision.content_json->'pilot_plan_binding'->'program_ref'->>'id'=%s
        )""")
        params.append(str(program_definition_id))
    if status:
        conditions.append("status=%s")
        params.append(status)
    filtered = f"FROM ({source}) cycles" + (" WHERE " + " AND ".join(conditions) if conditions else "")
    total = int(connection.execute("SELECT COUNT(*) AS total " + filtered, tuple(params)).fetchone()["total"])
    rows = connection.execute("SELECT * " + filtered +
        " ORDER BY collection_closed_at DESC,id DESC LIMIT %s OFFSET %s",
        (*params, page_size, (page - 1) * page_size)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item.pop("id")
        for key in ("cycle_id", "report_id"):
            if item[key] is not None:
                item[key] = str(item[key])
        if item["status"] != "ready":
            item["report_id"] = None
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "organization_id": selected, "organizations": organizations, "programs": programs}


def _select(value, fields: tuple[str, ...]) -> dict:
    return {key: deepcopy(value[key]) for key in fields if isinstance(value, dict) and key in value}


def _cut(value) -> dict:
    return _select(value, ("numerator", "denominator", "ratio"))


def _strings(value) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def present_public_copy(source: dict) -> dict:
    """Compatible display copy; never changes a saved outcome, score or C-67."""
    level_explanation = "Числовой показатель не определяет общий уровень владения навыком"
    replacements = {
        "Skill Level is not derived from numeric Score": level_explanation,
        "Полный результат со Score": "Результат по полному составу навыка",
        "Частный результат со Score": "Результат по части навыка",
        "Результат без общего Score": "Есть наблюдения без общего балла по навыку",
        "Нет Skill Result": "Недостаточно оснований для результата",
        "Results готовы, базовый Report и экспорт ещё готовятся.": "Оценка завершена. Готовим ваш отчёт",
    }

    def copy(value):
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [copy(item) for item in value]
        if isinstance(value, dict):
            result = {key: copy(item) for key, item in value.items()}
            if isinstance(result.get("limitations"), list):
                result["limitations"] = [item for index, item in enumerate(result["limitations"])
                                          if item not in result["limitations"][:index]]
            return result
        return deepcopy(value)

    result = copy(source)
    labels = {
        "full_score": "Результат по полному составу навыка",
        "partial_score": "Результат по части навыка",
        "result_without_score": "Есть наблюдения без общего балла по навыку",
        "no_result": "Недостаточно оснований для результата",
    }
    label_outcomes = {label: outcome for outcome, label in labels.items()}
    label_outcomes.update({
        "Полный показатель по навыку": "full_score",
        "Показатель по части состава навыка": "partial_score",
        "Есть наблюдения без общего показателя": "result_without_score",
        "По навыку пока нет обоснованного результата": "no_result",
    })
    for skill in result.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        outcome = skill.get("outcome")
        presentation = skill.get("presentation") or {}
        conflicts = []
        if presentation.get("outcome") not in (None, outcome):
            conflicts.append("presentation.outcome")
        if presentation.get("label") in label_outcomes and label_outcomes[presentation["label"]] != outcome:
            conflicts.append("presentation.label")
        completeness = skill.get("completeness")
        if completeness is not None and completeness != {"full_score": "full", "partial_score": "partial"}.get(outcome):
            conflicts.append("completeness")
        numeric = (skill.get("score") or {}).get("value") is not None
        if outcome in labels and numeric != (outcome in {"full_score", "partial_score"}):
            conflicts.append("score")
        if conflicts:
            presentation["consistency"] = {"status": "conflict", "fields": conflicts}
            presentation["label"] = "Сведения о результате требуют проверки. Показаны сохранённые данные."
        elif not presentation.get("label") or presentation["label"] in {*labels, "full", "partial", "null"}:
            presentation["label"] = labels.get(outcome, "Результат требует проверки")
        skill["presentation"] = presentation
    return result


def public_projection(report: dict, *, audience: str = "assessee") -> dict:
    """Project saved C-67 for HTTP without leaking its nested provenance or prompts."""
    source = present_public_copy(report["c67"])
    c67 = _select(source, ("schema_version", "contract", "message_version", "results_id",
                           "results_revision_id", "cycle_id",
                           "report_id", "report_revision_no", "results_revision_no",
                           "template_version"))
    c67["audience"] = audience
    c67["disclosure"] = "summary_with_coverage" if audience == "customer" else "personal"
    c67["report_mechanism"] = _select(source.get("report_mechanism"), ("id", "version"))
    c67["limitations"] = _strings(source.get("limitations"))
    if "test_result" in source:
        c67["test_result"] = _select(source["test_result"], ("synthetic", "usage_scope"))
    c67["skills"] = []
    for value in source.get("skills") or []:
        skill = _select(value, ("skill_id", "skill_code", "skill_name", "skill_description",
                                "competency_id", "competency_name", "outcome", "completeness"))
        skill["score"] = _select(value.get("score"), ("value", "numerator", "denominator")) if value.get("score") is not None else None
        skill["comparison"] = (_select(value.get("comparison"), ("status", "reason"))
                               if value.get("comparison") is not None else None)
        skill["limitations"] = _strings(value.get("limitations"))
        presentation = value.get("presentation")
        if isinstance(presentation, dict):
            skill["presentation"] = _select(presentation, ("outcome", "label", "remaining_plan_relevant"))
            skill["presentation"]["reasons"] = [_select(item, ("code", "message"))
                for item in presentation.get("reasons") or []]
            if presentation.get("consistency"):
                skill["presentation"]["consistency"] = _select(presentation["consistency"], ("status", "fields"))
        c67["skills"].append(skill)
    c67["competencies"] = []
    for value in source.get("competencies") or []:
        competency = _select(value, ("competency_id", "competency_name"))
        competency["skill_ids"] = _strings(value.get("skill_ids"))
        competency["score"] = (_select(value.get("score"), ("value", "numerator", "denominator"))
                               if value.get("score") is not None else None)
        c67["competencies"].append(competency)
    c67["coverage"] = {scope: {name: _cut(cut) for name, cut in cuts.items() if isinstance(cut, dict)}
                       for scope, cuts in (source.get("coverage") or {}).items() if scope in {"full_m2", "cycle_plan"} and isinstance(cuts, dict)}
    context = source.get("coverage_context") or {}
    c67["coverage_context"] = _select(context, ("contract_version", "not_a_score"))
    for key in ("catalog_possibility", "cycle_plan"):
        if key in context:
            c67["coverage_context"][key] = _cut(context[key])
    c67["reliability"] = _select(source.get("reliability"), ("status",))
    c67["confidence"] = _select(source.get("confidence"), ("kind",))
    c67["time"] = _select(source.get("time"), ("started_at", "budget_seconds", "calendar_window_seconds", "calendar_deadline"))
    c67["collection"] = _select(source.get("collection"), ("closed_at", "reason"))
    c67["sessions"] = [_select(value, ("started_at", "ended_at")) for value in source.get("sessions") or []]
    partial = source.get("partial_result")
    if isinstance(partial, dict):
        c67["partial_result"] = _select(partial, ("contract_version", "is_incomplete", "plan_completed", "plan_scope_limited",
            "observation_limited", "context_limited", "source_limited", "technical_failure", "close_reason"))
        c67["partial_result"]["progress"] = _select(partial.get("progress"),
            ("completed", "planned", "presented", "interrupted", "not_presented"))
        c67["partial_result"]["messages"] = _select(partial.get("messages"), ("title", "confirmed", "not_inferred"))
        c67["partial_result"]["limitation_reasons"] = [_select(value, ("code", "message"))
            for value in partial.get("limitation_reasons") or []]
    c67["processing"] = _select(source.get("processing"), ("status", "message"))
    descriptive = source.get("descriptive") or {}
    c67["descriptive"] = _select(descriptive, ("status",))
    c67["descriptive"]["summary"] = _strings(descriptive.get("summary"))
    c67["descriptive"]["claims"] = []
    for value in descriptive.get("claims") or []:
        claim = _select(value, ("kind", "text"))
        claim["skill_ids"] = _strings(value.get("skill_ids"))
        claim["limitations"] = _strings(value.get("limitations"))
        c67["descriptive"]["claims"].append(claim)
    if source.get("recommendation_presentation"):
        c67["recommendation_presentation"] = _select(source["recommendation_presentation"], ("status", "message"))
    return {**_select(report, ("id", "revision_no", "status", "cycle_id", "owner_user_id", "created_at",
                               "results_revision_id", "program_name", "collection_closed_at")),
            "audience": audience, "c67": c67}


def customer_projection(report: dict) -> dict:
    projected = public_projection(report, audience="customer")
    projected["participant_name"] = report.get("participant_name")
    return projected

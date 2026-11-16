from __future__ import annotations

from copy import deepcopy
from uuid import UUID


ACCESS_CONTRACT_VERSION = "m8-report-access/1.1.0"


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
        WHERE p.id=%s AND p.audience='assessee'""",
        (user_id, UUID(str(report_id)))).fetchone()
    return bool(row)


def record_access(connection, *, report_id: str, user_id: int, channel: str) -> None:
    if channel not in {"api", "pdf"}:
        raise ValueError("REPORT_ACCESS_CHANNEL_INVALID")
    connection.execute("""INSERT INTO m8_report_access_events(report_id,user_id,channel,contract_version)
        VALUES(%s,%s,%s,%s)""", (UUID(str(report_id)), user_id, channel, ACCESS_CONTRACT_VERSION))


def list_customer_reports(connection, *, user_id: int) -> list[dict]:
    rows = connection.execute("""SELECT DISTINCT ON (r.cycle_db_id)
        p.id AS report_id,p.revision_no,p.created_at,c.cycle_id,c.owner_user_id,
        c.started_at,c.collection_closed_at,configuration.name AS program_name,
        to_jsonb(u)->>'full_name' AS full_name,rr.revision_no AS results_revision_no
        FROM m5_cycles c
        JOIN organization_memberships membership ON membership.organization_id=c.organization_id
            AND membership.user_id=%s AND membership.role='admin'
        JOIN organizations organization ON organization.id=c.organization_id AND organization.is_active=TRUE
        JOIN users u ON u.id=c.owner_user_id
        LEFT JOIN assessment_personalized_profiles profile ON profile.id=c.personalized_profile_id
        LEFT JOIN assessment_configurations configuration ON configuration.id=profile.assessment_configuration_id
        JOIN m8_results r ON r.cycle_db_id=c.id
        JOIN m8_result_revisions rr ON rr.results_id=r.id
        JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
        ORDER BY r.cycle_db_id,rr.revision_no DESC,p.revision_no DESC""", (user_id,)).fetchall()
    return [{key: (str(value) if key in {"report_id", "cycle_id"} else value)
             for key, value in dict(row).items()} for row in rows]


def _select(value, fields: tuple[str, ...]) -> dict:
    return {key: deepcopy(value[key]) for key in fields if isinstance(value, dict) and key in value}


def _cut(value) -> dict:
    return _select(value, ("numerator", "denominator", "ratio"))


def _strings(value) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def public_projection(report: dict, *, audience: str = "assessee") -> dict:
    """Project saved C-67 for HTTP without leaking its nested provenance or prompts."""
    source = report["c67"]
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
        c67["partial_result"] = _select(partial, ("is_incomplete", "close_reason"))
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

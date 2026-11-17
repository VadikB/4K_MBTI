"""Addressed publication of a correction to an already published C-67."""
from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api import m8_results, m8_report_access
from Api import m6_cycle_aggregation_repository as calculations
from Api.m8_descriptive_report import _validate, _validate_semantic_decision, build_input, load_package
from Api.m8_recommendation_basis import resolve


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_published_reports (
        cycle_db_id BIGINT PRIMARY KEY REFERENCES m5_cycles(id),
        report_id UUID NOT NULL UNIQUE REFERENCES m8_reports(id),
        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_correction_candidates (
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        expected_report_id UUID NOT NULL REFERENCES m8_reports(id),
        result_revision_id UUID NOT NULL REFERENCES m8_result_revisions(id),
        kind TEXT NOT NULL CHECK(kind IN ('explanation','calculation')),
        incident_ref TEXT NOT NULL, participant_reason TEXT NOT NULL,
        c67_json JSONB NOT NULL, c67_checksum TEXT NOT NULL,
        created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m8_report_corrections (
        id UUID PRIMARY KEY, candidate_id UUID NOT NULL UNIQUE REFERENCES m8_report_correction_candidates(id),
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        previous_report_id UUID NOT NULL REFERENCES m8_reports(id),
        report_id UUID NOT NULL UNIQUE REFERENCES m8_reports(id),
        request_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
        created_by BIGINT NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m8_correction_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M8 correction history is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("m8_report_correction_candidates", "m8_report_corrections"):
        trigger = f"immutable_{table}"
        connection.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        connection.execute(f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                           "FOR EACH ROW EXECUTE FUNCTION prevent_m8_correction_history_change()")


def current_report_id(connection, cycle_db_id: int) -> str | None:
    row = connection.execute("""SELECT COALESCE(current.report_id, latest.id) AS id
        FROM m5_cycles cycle
        LEFT JOIN m8_published_reports current ON current.cycle_db_id=cycle.id
        LEFT JOIN LATERAL (SELECT p.id FROM m8_results r
            JOIN m8_result_revisions rr ON rr.results_id=r.id
            JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
            WHERE r.cycle_db_id=cycle.id ORDER BY rr.revision_no DESC,p.revision_no DESC LIMIT 1) latest ON TRUE
        WHERE cycle.id=%s""", (cycle_db_id,)).fetchone()
    return str(row["id"]) if row and row["id"] else None


def _stored_c67(connection, report_id: str) -> dict:
    row = connection.execute("SELECT c67_json,c67_checksum FROM m8_reports WHERE id=%s",
                             (UUID(str(report_id)),)).fetchone()
    if not row:
        raise ValueError("M8_REPORT_NOT_FOUND")
    m8_results._integrity(row["c67_json"], row["c67_checksum"])
    return row["c67_json"]


def _validated_description(connection, results: dict, proposed: dict, *, validator_gateway=None) -> dict:
    if not isinstance(proposed, dict) or set(proposed) != {"summary", "claims"}:
        raise ValueError("M8_CORRECTION_CANDIDATE_INVALID")
    _, _, descriptive_path, _ = m8_results._cycle_report_packages(connection, results["cycle_id"])
    package = load_package(descriptive_path)
    contract_version = "m8-descriptive-report/" + package["manifest"]["version"]
    model_input, allowed = build_input(results, resolve(connection, results), contract_version=contract_version)
    output = _validate(proposed, allowed)
    if package["validator_prompt"] is None:
        raise ValueError("M8_CORRECTION_VALIDATOR_UNAVAILABLE")
    if validator_gateway is None:
        from Api.llm.deepseek_gateway import DeepSeekGateway
        validator_gateway = DeepSeekGateway()
    if not getattr(validator_gateway, "enabled", True):
        raise ValueError("M8_CORRECTION_VALIDATOR_UNAVAILABLE")
    semantic_input = {"contract_version": contract_version, "evidence": model_input, "candidate": output}
    try:
        raw = validator_gateway.chat(
            [{"role": "system", "content": package["validator_prompt"]},
             {"role": "user", "content": json.dumps(semantic_input, ensure_ascii=False)}],
            temperature=0, timeout_seconds=package["manifest"]["execution"]["timeout_seconds"],
            max_tokens=package["manifest"]["execution"]["max_tokens"],
            routing_key=f"m8-correction-validation:{results['revision_id']}:{checksum(output)}",
            response_format={"type": "json_object"})
    except (RuntimeError, TimeoutError, OSError) as exc:
        raise ValueError("M8_CORRECTION_VALIDATOR_UNAVAILABLE") from exc
    semantic = _validate_semantic_decision(json.loads(raw), output)
    if semantic["status"] != "accepted":
        raise ValueError("M8_CORRECTION_CANDIDATE_REJECTED")
    return {"contract_version": contract_version,
            "mechanism": {"id": package["manifest"]["id"], "version": package["manifest"]["version"],
                          "checksum": package["package_checksum"]},
            "input": model_input, "input_checksum": checksum(model_input),
            "status": "ready", "failure_reason": None, "semantic_validation": semantic, **output}


def prepare(connection, *, expected_report_id: str, result_revision_id: str, kind: str,
            incident_ref: str, participant_reason: str, descriptive: dict, created_by: int,
            validator_gateway=None) -> dict:
    if kind not in {"explanation", "calculation"}:
        raise ValueError("M8_CORRECTION_KIND_INVALID")
    if not incident_ref.strip() or not participant_reason.strip() or len(participant_reason) > 1000:
        raise ValueError("M8_CORRECTION_REASON_REQUIRED")
    original = m8_results.read_report(connection, expected_report_id)
    saved_original = _stored_c67(connection, expected_report_id)
    if original["audience"] != "assessee" or original["status"] != "ready":
        raise ValueError("M8_CORRECTION_SOURCE_INVALID")
    cycle = connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (UUID(original["cycle_id"]),)).fetchone()
    if current_report_id(connection, cycle["id"]) != expected_report_id:
        raise ValueError("M8_CORRECTION_EXPECTED_STALE")
    results = m8_results.read_results_revision(connection, result_revision_id)
    if results["cycle_id"] != original["cycle_id"]:
        raise ValueError("M8_CORRECTION_CYCLE_MISMATCH")
    if kind == "explanation" and results["revision_id"] != original["results_revision_id"]:
        raise ValueError("M8_CORRECTION_RESULTS_MISMATCH")
    if kind == "calculation":
        if results["revision_id"] == original["results_revision_id"]:
            raise ValueError("M8_CORRECTION_NEW_RESULTS_REQUIRED")
        row = connection.execute("SELECT calculation_id FROM m8_result_revisions WHERE id=%s",
                                 (UUID(result_revision_id),)).fetchone()
        calculation = calculations.read(connection, row["calculation_id"])
        if calculation["c56"].get("contract") != "C-56" or calculation["c56"].get("readiness") != "ready_for_pm06":
            raise ValueError("M8_CORRECTION_CALCULATION_NOT_READY")
        if calculation["c56"].get("composition_checksum") != results["results"].get("composition_checksum"):
            raise ValueError("M8_CORRECTION_COMPOSITION_MISMATCH")
        if str(calculation["c56"].get("cycle_id")) != results["cycle_id"]:
            raise ValueError("M8_CORRECTION_CYCLE_MISMATCH")
        if (results["results"].get("c56_ref") != {"calculation_id": calculation["id"],
                                                   "revision_no": calculation["revision_no"]}):
            raise ValueError("M8_CORRECTION_CALCULATION_MISMATCH")
    description = _validated_description(connection, results, descriptive, validator_gateway=validator_gateway)
    if kind == "explanation":
        c67 = deepcopy(saved_original)
        c67["descriptive"] = description
    else:
        c67 = m8_results._report_content(results, "assessee", saved_original.get("target_profile"),
                                         connection=connection, descriptive_override=description)
        c67["template_version"] = saved_original["template_version"]
    if (c67.get("processing") or {}).get("status") == "failed":
        raise ValueError("M8_CORRECTION_CANDIDATE_NOT_PUBLISHABLE")
    visible_changes = diff(m8_report_access.public_projection(original)["c67"],
                           m8_report_access.public_projection({**original, "c67": c67})["c67"])
    if not visible_changes:
        raise ValueError("M8_CORRECTION_NO_CHANGE")
    candidate_id = uuid4()
    connection.execute("""INSERT INTO m8_report_correction_candidates
        (id,cycle_db_id,expected_report_id,result_revision_id,kind,incident_ref,participant_reason,
         c67_json,c67_checksum,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
        (candidate_id, cycle["id"], UUID(expected_report_id), UUID(result_revision_id), kind,
         incident_ref.strip(), participant_reason.strip(), json.dumps(c67, ensure_ascii=False), checksum(c67), created_by))
    return {"candidate_id": str(candidate_id), "expected_report_id": expected_report_id,
            "kind": kind, "changed": visible_changes}


def publish(connection, *, candidate_id: str, expected_report_id: str, key: str, created_by: int) -> dict:
    request_hash = checksum({"candidate_id": candidate_id, "expected_report_id": expected_report_id})
    connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("m8-correction:" + key,))
    previous = connection.execute("SELECT report_id,request_hash FROM m8_report_corrections WHERE request_key=%s",
                                  (key,)).fetchone()
    if previous:
        if previous["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return m8_results.read_report(connection, previous["report_id"])
    candidate = connection.execute("SELECT * FROM m8_report_correction_candidates WHERE id=%s",
                                   (UUID(candidate_id),)).fetchone()
    if not candidate or str(candidate["expected_report_id"]) != expected_report_id:
        raise ValueError("M8_CORRECTION_CANDIDATE_INVALID")
    connection.execute("SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE", (candidate["cycle_db_id"],)).fetchone()
    previous = connection.execute("SELECT report_id,request_hash FROM m8_report_corrections WHERE request_key=%s",
                                  (key,)).fetchone()
    if previous:
        if previous["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return m8_results.read_report(connection, previous["report_id"])
    if current_report_id(connection, candidate["cycle_db_id"]) != expected_report_id:
        raise ValueError("M8_CORRECTION_EXPECTED_STALE")
    if checksum(candidate["c67_json"]) != candidate["c67_checksum"]:
        raise ValueError("CHECKSUM_MISMATCH")
    original = m8_results.read_report(connection, expected_report_id)
    saved_original = _stored_c67(connection, expected_report_id)
    results = m8_results.read_results_revision(connection, candidate["result_revision_id"])
    if results["cycle_id"] != original["cycle_id"]:
        raise ValueError("M8_CORRECTION_CYCLE_MISMATCH")
    c67 = deepcopy(candidate["c67_json"])
    if (c67.get("processing") or {}).get("status") == "failed":
        raise ValueError("M8_CORRECTION_CANDIDATE_NOT_PUBLISHABLE")
    if candidate["kind"] == "explanation":
        if results["revision_id"] != original["results_revision_id"]:
            raise ValueError("M8_CORRECTION_RESULTS_MISMATCH")
        if {k: v for k, v in c67.items() if k != "descriptive"} != {
                k: v for k, v in saved_original.items() if k != "descriptive"}:
            raise ValueError("M8_CORRECTION_FACTS_CHANGED")
    else:
        row = connection.execute("SELECT calculation_id FROM m8_result_revisions WHERE id=%s",
                                 (candidate["result_revision_id"],)).fetchone()
        calculation = calculations.read(connection, row["calculation_id"])
        if calculation["c56"].get("composition_checksum") != results["results"].get("composition_checksum"):
            raise ValueError("M8_CORRECTION_COMPOSITION_MISMATCH")
        if (results["results"].get("c56_ref") != {"calculation_id": calculation["id"],
                                                   "revision_no": calculation["revision_no"]}):
            raise ValueError("M8_CORRECTION_CALCULATION_MISMATCH")
    revision_no = connection.execute("SELECT COALESCE(MAX(revision_no),0)+1 AS n FROM m8_reports WHERE result_revision_id=%s",
                                     (candidate["result_revision_id"],)).fetchone()["n"]
    report_id = uuid4()
    c67["report_id"] = str(report_id)
    c67["report_revision_no"] = revision_no
    c67["results_revision_id"] = results["revision_id"]
    c67["results_revision_no"] = results["revision_no"]
    profile = saved_original.get("target_profile")
    connection.execute("""INSERT INTO m8_reports
        (id,result_revision_id,revision_no,audience,target_profile_json,target_profile_checksum,template_version,
         c67_json,c67_checksum,status,request_key,request_hash,created_by)
        VALUES(%s,%s,%s,'assessee',%s::jsonb,%s,%s,%s::jsonb,%s,'ready',%s,%s,%s)""",
        (report_id, candidate["result_revision_id"], revision_no, json.dumps(profile) if profile else None,
         checksum(profile) if profile else None, c67["template_version"], json.dumps(c67, ensure_ascii=False),
         checksum(c67), "correction:" + key, request_hash, created_by))
    connection.execute("""INSERT INTO m8_report_corrections
        (id,candidate_id,cycle_db_id,previous_report_id,report_id,request_key,request_hash,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
        (uuid4(), UUID(candidate_id), candidate["cycle_db_id"], UUID(expected_report_id), report_id,
         key, request_hash, created_by))
    connection.execute("""INSERT INTO m8_published_reports(cycle_db_id,report_id) VALUES(%s,%s)
        ON CONFLICT(cycle_db_id) DO UPDATE SET report_id=EXCLUDED.report_id,published_at=NOW()""",
        (candidate["cycle_db_id"], report_id))
    return m8_results.read_report(connection, report_id)


def diff(before: dict, after: dict) -> list[dict]:
    """Only participant-facing facts; stable skill IDs prevent positional drift."""
    items = []
    def add(skill_id, name, field, old, new):
        if field in {"summary", "explanation"}:
            def normalized(value):
                if field == "summary":
                    return [" ".join(str(text).split()) for text in value or []]
                return [(" ".join(str(item.get("text") or "").split()),
                         tuple(" ".join(str(limit).split()) for limit in item.get("limitations") or []))
                        for item in value or []]
            if normalized(old) == normalized(new):
                return
        if old != new:
            items.append({"skill_id": skill_id, "skill_name": name, "field": field,
                          "before": old, "after": new})
    left = {s["skill_id"]: s for s in before.get("skills") or []}
    right = {s["skill_id"]: s for s in after.get("skills") or []}
    for skill_id in sorted(left.keys() | right.keys()):
        old, new = left.get(skill_id, {}), right.get(skill_id, {})
        name = new.get("skill_name") or old.get("skill_name") or skill_id
        for field in ("score", "outcome", "presentation", "comparison", "limitations"):
            add(skill_id, name, field, old.get(field), new.get(field))
    add(None, None, "limitations", before.get("limitations"), after.get("limitations"))
    old_coverage, new_coverage = before.get("coverage") or {}, after.get("coverage") or {}
    for scope in sorted(old_coverage.keys() | new_coverage.keys()):
        old_cuts, new_cuts = old_coverage.get(scope) or {}, new_coverage.get(scope) or {}
        for name in sorted(old_cuts.keys() | new_cuts.keys()):
            add(None, None, f"coverage:{scope}:{name}", old_cuts.get(name), new_cuts.get(name))
    old_partial, new_partial = before.get("partial_result") or {}, after.get("partial_result") or {}
    add(None, None, "progress", old_partial.get("progress"), new_partial.get("progress"))
    add(None, None, "partial_limitations", old_partial.get("limitation_reasons"),
        new_partial.get("limitation_reasons"))
    old_desc, new_desc = before.get("descriptive") or {}, after.get("descriptive") or {}
    add(None, None, "summary", old_desc.get("summary") or [], new_desc.get("summary") or [])
    for skill_id in sorted(left.keys() | right.keys()):
        def claims(desc):
            return [dict(text=c.get("text"), limitations=c.get("limitations") or [])
                    for c in desc.get("claims") or [] if skill_id in c.get("skill_ids", [])]
        add(skill_id, right.get(skill_id, left.get(skill_id, {})).get("skill_name") or skill_id,
            "explanation", claims(old_desc), claims(new_desc))
    return items


def public_notice(connection, report: dict) -> dict | None:
    row = connection.execute("""SELECT c.previous_report_id,c.created_at,k.participant_reason
        FROM m8_report_corrections c JOIN m8_report_correction_candidates k ON k.id=c.candidate_id
        WHERE c.report_id=%s""", (UUID(report["id"]),)).fetchone()
    if not row:
        return None
    previous = m8_results.read_report(connection, row["previous_report_id"])
    return {"created_at": row["created_at"], "reason": row["participant_reason"],
            "changes": diff(m8_report_access.public_projection(previous)["c67"],
                            m8_report_access.public_projection(report)["c67"])}

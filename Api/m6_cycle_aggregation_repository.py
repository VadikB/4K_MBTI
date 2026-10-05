from __future__ import annotations

import json
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.assessment_configuration import definition_checksum
from Api import m7_completion
from Api.m6_aggregation_package import hierarchy_for, load_package
from Api.m6_cycle_aggregation import calculate


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_cycle_calculations (
        id UUID PRIMARY KEY, cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id), revision_no INTEGER NOT NULL,
        request_key TEXT NOT NULL, request_hash TEXT NOT NULL, composition_checksum TEXT NOT NULL,
        input_json JSONB NOT NULL, input_hash TEXT NOT NULL, result_json JSONB NOT NULL, result_hash TEXT NOT NULL,
        c56_json JSONB NOT NULL, c56_hash TEXT NOT NULL, created_by BIGINT NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(cycle_db_id,revision_no), UNIQUE(cycle_db_id,request_key))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m6_cycle_calculation_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M6 cycle calculation is immutable'; END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_m6_cycle_calculation ON m6_cycle_calculations")
    connection.execute("""CREATE TRIGGER immutable_m6_cycle_calculation BEFORE UPDATE OR DELETE ON m6_cycle_calculations
        FOR EACH ROW EXECUTE FUNCTION prevent_m6_cycle_calculation_change()""")


def _inputs(connection, cycle_id: str, expected_composition_checksum: str):
    cycle = m7_completion._cycle(connection, cycle_id)
    c46 = m7_completion.read_c46(connection, cycle_id)
    if c46["composition_checksum"] != expected_composition_checksum:
        raise ValueError("COMPOSITION_MISMATCH")
    _, situations, identity, actual = m7_completion._composition(connection, cycle)
    if actual != expected_composition_checksum:
        raise ValueError("COMPOSITION_MISMATCH")
    if cycle["status"] not in {"collection_closed", "calculation_pending", "calculated"}:
        raise ValueError("M6_FINAL_CALCULATION_REQUIRES_CLOSED_COLLECTION")
    planned = c46["payload_json"].get("plan", {}).get("planned_target_set") if c46["payload_json"].get("plan") else c46["payload_json"]["full_target_set"]
    full_targets = c46["payload_json"]["full_target_set"]
    target_ids = {x["indicator_id"] for x in full_targets}
    observations, processing = [], []
    for situation in situations:
        if not situation["handoff_id"]:
            processing.append({"assessment_situation_id": str(situation["assessment_situation_id"]), "status": "not_presented"})
            continue
        revisions = connection.execute("""SELECT a.id,a.created_at,a.output_json,a.output_hash,q.evidence_revision_id,c.id AS c54_id,c.payload_json,c.payload_hash
            FROM m6_assessment_revisions a JOIN m6_c54_revisions c ON c.assessment_revision_id=a.id
            JOIN m6_assessment_requests q ON q.id=a.request_id
            WHERE q.as_db_id=%s AND q.mode='final' ORDER BY a.created_at DESC LIMIT 2""", (situation["id"],)).fetchall()
        if len(revisions) > 1 and revisions[0]['created_at'] == revisions[1]['created_at']:
            raise ValueError('M6_ADMISSION_AMBIGUOUS_REVISION')
        revision = revisions[0] if revisions else None
        if not revision:
            raise ValueError("M6_FINAL_PROCESSING_INCOMPLETE")
        if definition_checksum(revision["output_json"]) != revision["output_hash"] or definition_checksum(revision["payload_json"]) != revision["payload_hash"]:
            raise ValueError("CHECKSUM_MISMATCH")
        for target in revision["output_json"]["targets"]:
            if target["indicator_id"] not in target_ids:
                continue
            ia = connection.execute("""SELECT r.id FROM m6_indicator_assessment_revisions r
                JOIN m6_indicator_assessments i ON i.id=r.indicator_assessment_id
                WHERE r.assessment_revision_id=%s AND i.indicator_id=%s""", (revision["id"], target["indicator_id"])).fetchone()
            observations.append({"assessment_situation_id": str(situation["assessment_situation_id"]),
                "revision_id": str(ia["id"]) if ia else f"non-numeric:{revision['id']}:{target['indicator_id']}",
                "assessment_revision_id": str(revision["id"]), "evidence_revision_id": str(revision["evidence_revision_id"]),
                "indicator_id": target["indicator_id"], "m2_version": target["m2_version"],
                "status": target["status"], "outcome": target.get("outcome"), "opportunity": target["opportunity"],
                "refs": target["refs"], "confidence": target["confidence"], "contradictions": target["contradictions"]})
        processing.append({"assessment_situation_id": str(situation["assessment_situation_id"]), "status": revision["payload_json"]["status"],
            "assessment_revision_id": str(revision["id"]), "c54_revision_id": str(revision["c54_id"])})
    package = load_package()
    value = {"schema_version": 1, "cycle_id": str(cycle["cycle_id"]), "composition": identity,
        "composition_checksum": actual, "source_versions": package["rules"]["source_versions"],
        "algorithm": {"version": package["manifest"]["version"], "rules_hash": package["rules_hash"]},
        "cycle_context": {"cycle": c46["payload_json"]["cycle"], "goal": c46["payload_json"].get("goal"),
            "sessions": c46["payload_json"]["sessions"], "assessment_situations": c46["payload_json"]["assessment_situations"]},
        "full_target_set": full_targets, "planned_target_set": planned, "processing": processing,
        "observations": observations, "hierarchy": hierarchy_for(target_ids)}
    return cycle, c46, value


def create(connection, *, cycle_id: str, key: str, expected_composition_checksum: str,
           admission_mechanism_version: str, decisions: list[dict], created_by: int,
           limitations: list[str] | None = None):
    cycle, c46, value = _inputs(connection, cycle_id, expected_composition_checksum)
    request = {"expected_composition_checksum": expected_composition_checksum,
        "admission_mechanism_version": admission_mechanism_version, "decisions": decisions}
    request_hash = checksum(request)
    prior = connection.execute("SELECT * FROM m6_cycle_calculations WHERE cycle_db_id=%s AND request_key=%s", (cycle["id"], key)).fetchone()
    if prior:
        if prior["request_hash"] != request_hash: raise ValueError("IDEMPOTENCY_CONFLICT")
        return read(connection, prior["id"])
    result = calculate(hierarchy=value["hierarchy"], observations=value["observations"], decisions=decisions,
        planned_indicator_ids=[x["indicator_id"] for x in value["planned_target_set"]], composition_version=expected_composition_checksum)
    revision_no = connection.execute("SELECT COALESCE(MAX(revision_no),0)+1 AS n FROM m6_cycle_calculations WHERE cycle_db_id=%s", (cycle["id"],)).fetchone()["n"]
    calculation_id = uuid4()
    readiness = "ready_for_pm06" if all(x["status"] in {"completed", "not_presented"} for x in value["processing"]) else "not_ready"
    c56 = {"schema_version": 1, "contract": "C-56", "message_version": "1.0", "owner": "PM-05", "consumer": "PM-06",
        "message_id": str(uuid4()), "correlation_id": str(cycle["cycle_id"]), "readiness": readiness,
        "cycle_id": str(cycle["cycle_id"]), "composition": value["composition"], "composition_checksum": expected_composition_checksum,
        "cycle_context": value["cycle_context"],
        "full_target_set": value["full_target_set"], "planned_target_set": value["planned_target_set"],
        "calculation_ref": {"id": str(calculation_id), "revision_no": revision_no, "cycle_id": str(cycle["cycle_id"]),
            "composition_checksum": expected_composition_checksum}, "sources": value["source_versions"], "algorithm": value["algorithm"],
        "admission_mechanism": admission_mechanism_version, "processing": value["processing"], "observations": value["observations"],
        "admissions": result["admission_decisions"], **result,
        "confidence": {"kind": "qualitative", "ia_bases_preserved": True},
        "reliability": {"status": "not_verified", "protocol_ref": None}, "limitations": list(limitations or [])}
    connection.execute("""INSERT INTO m6_cycle_calculations
        (id,cycle_db_id,revision_no,request_key,request_hash,composition_checksum,input_json,input_hash,result_json,result_hash,c56_json,c56_hash,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,%s,%s)""",
        (calculation_id,cycle["id"],revision_no,key,request_hash,expected_composition_checksum,json.dumps(value,ensure_ascii=False),checksum(value),
         json.dumps(result,ensure_ascii=False),checksum(result),json.dumps(c56,ensure_ascii=False),checksum(c56),created_by))
    flat = result["coverage"]["cycle_plan"]
    m7_completion.reconcile_c46(connection, cycle_id=cycle_id, expected_composition_checksum=expected_composition_checksum,
        calculation_ref=c56["calculation_ref"], coverage={k: flat[k] for k in ("opportunities","indicator_assessments","admissible_contributions","components_with_score","complete_components")},
        skill_outcomes=[{"skill_id": x["skill_id"], "outcome": x["outcome"]} for x in result["skill_outcomes"]])
    return read(connection, calculation_id)


def read(connection, calculation_id):
    row = connection.execute("SELECT * FROM m6_cycle_calculations WHERE id=%s", (UUID(str(calculation_id)),)).fetchone()
    if not row: raise ValueError("M6_CYCLE_CALCULATION_NOT_FOUND")
    for value, digest in ((row["input_json"], row["input_hash"]), (row["result_json"], row["result_hash"]), (row["c56_json"], row["c56_hash"])):
        if checksum(value) != digest: raise ValueError("CHECKSUM_MISMATCH")
    return {"id": str(row["id"]), "revision_no": row["revision_no"], "created_at": row["created_at"], "c56": row["c56_json"]}


def read_latest_for_cycle(connection, cycle_id):
    cycle = m7_completion._cycle(connection, cycle_id, lock=False)
    row = connection.execute("SELECT id FROM m6_cycle_calculations WHERE cycle_db_id=%s ORDER BY revision_no DESC LIMIT 1", (cycle["id"],)).fetchone()
    if not row: raise ValueError("M6_CYCLE_CALCULATION_NOT_FOUND")
    return read(connection, row["id"])


def create_substantive(connection, *, cycle_id: str, key: str, expected_composition_checksum: str,
                       created_by: int, gateway=None):
    """Explicit attempt/retry: same key reads saved decision without another AI call."""
    from Api.m6_admission import VERSION, decide
    cycle, _, value = _inputs(connection, cycle_id, expected_composition_checksum)
    prior = connection.execute('SELECT * FROM m6_cycle_calculations WHERE cycle_db_id=%s AND request_key=%s',
                               (cycle['id'], key)).fetchone()
    if prior:
        saved = read(connection, prior['id'])
        if (prior['composition_checksum'] != expected_composition_checksum
                or saved['c56']['admission_mechanism'] != VERSION
                or saved['c56']['observations'] != value['observations']):
            raise ValueError('IDEMPOTENCY_CONFLICT')
        return saved
    mechanism, decisions, limitations = decide(connection, cycle_id=cycle_id,
                                              observations=value['observations'], gateway=gateway)
    return create(connection, cycle_id=cycle_id, key=key,
                  expected_composition_checksum=expected_composition_checksum,
                  admission_mechanism_version=mechanism, decisions=decisions,
                  created_by=created_by, limitations=limitations)

"""Product adapter for the frozen QA-only M6 C-45 resolver."""
from __future__ import annotations

from uuid import UUID

from Api.m6_input_resolver import load_criteria, normalize
from Api import qa_orchestration


def resolve(connection, handoff_id: str) -> tuple[int, dict]:
    handoff = connection.execute(
        "SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s", (UUID(handoff_id),)
    ).fetchone()
    if not handoff:
        raise ValueError("M6_HANDOFF_NOT_FOUND")
    row = connection.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s", (handoff["assessment_situation_db_id"],)
    ).fetchone()
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (row["cycle_db_id"],)).fetchone()
    session = connection.execute("SELECT * FROM m5_cycle_sessions WHERE id=%s", (row["session_db_id"],)).fetchone()
    expected_scope = qa_orchestration.usage_scope()
    if not cycle or not session or row["usage_scope"] != expected_scope or cycle["usage_scope"] != expected_scope:
        raise ValueError("M6_USAGE_SCOPE_INVALID")
    normalized_row = dict(row) if expected_scope == "qa" else {**dict(row), "usage_scope": "qa"}
    material = normalize(
        dict(handoff), normalized_row, dict(cycle), dict(session), load_criteria(row["snapshot_json"])
    )
    material["usage_scope"] = expected_scope
    return int(row["id"]), material

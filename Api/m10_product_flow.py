from __future__ import annotations

import json
from pathlib import Path

from Api import m7_cycle_planner, participant_profile
from Api import m5_scenario_runtime, m7_completion
from Api import qa_orchestration

CASE_PACKAGE = Path(__file__).resolve().parents[1] / "assessment_definitions/cases/competencies_4k/1.1"


def _policy() -> dict:
    return json.loads((CASE_PACKAGE / "admission-policy.json").read_bytes())


def _owned_profile(connection, user_id: int, profile_id=None) -> int:
    return int(participant_profile.profile_for_start(connection, user_id=user_id, profile_id=profile_id)['id'])


def _current_cycle(connection, user_id: int, organization_id: int, configuration_id=None,
                   usage_scope: str = "assessment") -> dict | None:
    rows = connection.execute(
        """SELECT c.cycle_id FROM m5_cycles c
           JOIN assessment_personalized_profiles p ON p.id=c.personalized_profile_id
           WHERE c.owner_user_id=%s AND c.organization_id=%s AND c.usage_scope=%s
             AND (%s::bigint IS NULL OR p.assessment_configuration_id=%s)
             AND c.status IN('prepared','active','paused','interrupted','collection_closed','calculation_pending')
           ORDER BY c.created_at DESC""",
        (user_id, organization_id, usage_scope, configuration_id, configuration_id),
    ).fetchall()
    if len(rows) > 1:
        raise ValueError('M4_PROFILE_SELECTION_REQUIRED: Выберите конфигурацию оценки в профиле.')
    return m7_cycle_planner.read_plan(connection, str(rows[0]['cycle_id'])) if rows else None


def _present_next(connection, *, plan: dict, user_id: int, key: str) -> dict:
    decision = m7_cycle_planner.choose_next(
        connection, cycle_id=str(plan["cycle_id"]), expected_plan_revision_id=str(plan["revision_id"]),
        key=key, created_by=user_id, policy=_policy(),
    )
    presentation = None
    if decision["status"] == "SELECTED":
        presentation = m7_cycle_planner.present(
            connection, decision_id=str(decision["id"]), expected_revision=int(decision["revision_no"]),
        )["presentation"]
    return {"plan": m7_cycle_planner.read_plan(connection, str(plan["cycle_id"])),
            "decision": decision, "presentation": presentation}


def _prepare_next(connection, *, plan: dict, user_id: int, key: str) -> dict:
    """Prepare an admitted AS without presenting it or starting M7 time."""
    decision = m7_cycle_planner.choose_next(
        connection, cycle_id=str(plan["cycle_id"]), expected_plan_revision_id=str(plan["revision_id"]),
        key=key, created_by=user_id, policy=_policy(),
    )
    return {"plan": m7_cycle_planner.read_plan(connection, str(plan["cycle_id"])),
            "decision": decision, "presentation": None}


def prepare(connection, *, user_id: int, key: str,
            selected_skills: list[str] | None = None, profile_id: int | None = None) -> dict:
    """Create/reuse one prepared Cycle; never start its Session or calendar window."""
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(user_id),))
    organization_id = participant_profile.active_organization(connection, user_id)
    profile_id = _owned_profile(connection, user_id, profile_id)
    profile = connection.execute(
        "SELECT assessment_configuration_id FROM assessment_personalized_profiles WHERE id=%s",
        (profile_id,),
    ).fetchone()
    usage_scope = qa_orchestration.usage_scope()
    current = _current_cycle(
        connection, user_id, organization_id, profile["assessment_configuration_id"], usage_scope,
    )
    if current:
        situation = connection.execute(
            """SELECT status FROM m5_assessment_situations
               WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)
               ORDER BY id DESC LIMIT 1""",
            (current["cycle_id"],),
        ).fetchone()
        if not situation:
            result = _prepare_next(
                connection, plan=current, user_id=user_id,
                key=f"product-prepared:{key}",
            )
            return {"resumed": True, **result}
        return {"resumed": True, "plan": current,
                "decision": current["decisions"][-1] if current["decisions"] else None,
                "presentation": None}
    plan = m7_cycle_planner.create_plan(
        connection, personalized_profile_id=profile_id,
        selected_skills=selected_skills or ["K1", "K2", "K3", "K4"],
        created_by=user_id, key=f"product-prepare:{key}", usage_scope=usage_scope,
    )
    if plan["plan"]["status"] == "NO_ROUTE":
        raise ValueError('M7_NO_ADMISSIBLE_CASE: Профиль готов. Ответственный специалист должен подготовить допустимые кейсы для выбранной роли и конфигурации.')
    result = _prepare_next(connection, plan=plan, user_id=user_id, key=f"product-prepared:{key}")
    return {"resumed": False, **result}


def start_prepared(connection, *, user_id: int, cycle_id: str, key: str) -> dict:
    """Recheck owned M4 readiness and explicitly present the already prepared AS."""
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(user_id),))
    plan = m7_cycle_planner.read_plan(connection, cycle_id)
    cycle = connection.execute(
        "SELECT owner_user_id,personalized_profile_id,status,started_at FROM m5_cycles WHERE cycle_id=%s FOR UPDATE",
        (cycle_id,),
    ).fetchone()
    if not cycle or int(cycle["owner_user_id"]) != int(user_id):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    participant_profile.profile_for_start(
        connection, user_id=user_id, profile_id=int(cycle["personalized_profile_id"]),
    )
    open_as = connection.execute(
        """SELECT s.id,s.assessment_situation_id,s.status,d.id AS decision_id,d.revision_no
           FROM m5_assessment_situations s
           JOIN m7_route_assignments a ON a.assessment_situation_db_id=s.id
           JOIN m7_route_decisions d ON d.id=a.decision_id
           WHERE s.cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)
             AND s.status NOT IN('closed','terminated','rejected')
           ORDER BY s.id DESC LIMIT 1""",
        (cycle_id,),
    ).fetchone()
    if not open_as:
        raise ValueError("M7_PREPARED_SITUATION_NOT_FOUND")
    if open_as["status"] == "active":
        return {"resumed": True, "plan": plan, "decision": None,
                "presentation": dict(open_as)}
    presented = m7_cycle_planner.present(
        connection, decision_id=str(open_as["decision_id"]),
        expected_revision=int(open_as["revision_no"]),
    )
    return {"resumed": False, "plan": m7_cycle_planner.read_plan(connection, cycle_id),
            "decision": presented["decision"], "presentation": presented["presentation"]}


def start_or_resume(connection, *, user_id: int, key: str,
                    selected_skills: list[str] | None = None, profile_id: int | None = None) -> dict:
    # Serialize owner start across reloads/tabs before checking for an active Cycle.
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(user_id),))
    organization_id = participant_profile.active_organization(connection, user_id)
    configuration_id = None
    if profile_id is not None:
        # An existing Cycle keeps its frozen snapshot even after a new confirmation.
        scope = connection.execute("""SELECT assessment_configuration_id FROM assessment_personalized_profiles
            WHERE id=%s AND user_id=%s AND organization_id=%s""", (profile_id, user_id, organization_id)).fetchone()
        if not scope:
            raise ValueError('M4_PROFILE_SCOPE_MISMATCH: Подтвердите профиль для текущей организации.')
        configuration_id = scope['assessment_configuration_id']
    usage_scope = qa_orchestration.usage_scope()
    current = _current_cycle(connection, user_id, organization_id, configuration_id, usage_scope)
    if current:
        open_as = connection.execute(
            """SELECT assessment_situation_id,status FROM m5_assessment_situations
               WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)
                 AND status NOT IN('closed','terminated','rejected') ORDER BY id DESC LIMIT 1""",
            (current["cycle_id"],),
        ).fetchone()
        if not open_as and not connection.execute(
            'SELECT 1 FROM m5_assessment_situations WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)',
            (current['cycle_id'],),
        ).fetchone():
            return {'resumed':True,**_present_next(connection,plan=current,user_id=user_id,key=f'product-prepared:{key}')}
        return {"resumed": True, "plan": current, "decision": None,
                "presentation": dict(open_as) if open_as else None}
    profile_id = _owned_profile(connection, user_id, profile_id)
    with connection.transaction():
        plan = m7_cycle_planner.create_plan(
            connection, personalized_profile_id=profile_id,
            selected_skills=selected_skills or ["K1", "K2", "K3", "K4"],
            created_by=user_id, key=f"product-start:{key}", usage_scope=usage_scope,
        )
        if plan['plan']['status'] == 'NO_ROUTE':
            raise ValueError('M7_NO_ADMISSIBLE_CASE: Профиль готов. Ответственный специалист должен подготовить допустимые кейсы для выбранной роли и конфигурации.')
        result = _present_next(connection, plan=plan, user_id=user_id, key=f"product-next:{key}:1")
        return {"resumed": False, **result}


def next_situation(connection, *, cycle_id: str, user_id: int, key: str) -> dict:
    plan = m7_cycle_planner.read_plan(connection, cycle_id)
    return _present_next(connection, plan=plan, user_id=user_id, key=f"product-next:{key}")


def read_runtime(connection, *, cycle_id: str) -> dict:
    """Owner-facing read model assembled only from persisted runtime state."""
    plan = m7_cycle_planner.read_plan(connection, cycle_id)
    status = m7_completion.read_status(connection, cycle_id)
    cycle = connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()
    situations = connection.execute(
        """SELECT assessment_situation_id,status,snapshot_json,started_at,scenario_ended_at,closed_at
           FROM m5_assessment_situations WHERE cycle_db_id=%s ORDER BY id""", (cycle["id"],)
    ).fetchall()
    current = dict(situations[-1]) if situations else None
    trace = participant_trace(m5_scenario_runtime.trace(connection, str(current["assessment_situation_id"]))) if current else None
    clarification = None
    if current:
        row = connection.execute(
            """SELECT d.id FROM m7_clarification_decisions d
               JOIN m5_assessment_situations s ON s.id=d.assessment_situation_db_id
               WHERE s.assessment_situation_id=%s ORDER BY d.created_at DESC LIMIT 1""",
            (current["assessment_situation_id"],),
        ).fetchone()
        if row:
            from Api import m7_clarification
            saved = m7_clarification.read(connection, str(row["id"]))
            clarification = {
                "id": str(saved["id"]), "status": saved["status"],
                "question": saved["question_json"],
                "question_turn_id": str(saved["question_turn_id"]) if saved["question_turn_id"] else None,
                "response_outcome": saved["response_outcome"],
                "answer_turn_id": str(saved["answer_turn_id"]) if saved["answer_turn_id"] else None,
                "explanation": saved["explanation_json"],
            }
    pipeline = connection.execute(
        "SELECT status,stage,error_code,latest_report_id FROM m10_pipeline_runs WHERE cycle_db_id=%s",
        (cycle["id"],),
    ).fetchone()
    continuation = connection.execute(
        "SELECT id,status FROM m7_continuation_intents WHERE cycle_db_id=%s ORDER BY created_at DESC LIMIT 1",
        (cycle["id"],),
    ).fetchone()
    return {
        "runtime_kind": "cycle", "cycle_id": cycle_id, "plan": plan, "status": status,
        "situations": [{"assessment_situation_id": str(x["assessment_situation_id"]), "status": x["status"]}
                       for x in situations],
        "current_situation": ({
            "assessment_situation_id": str(current["assessment_situation_id"]),
            "status": current["status"],
            "participant_payload": current["snapshot_json"]["participant_payload"],
        } if current else None),
        "trace": trace, "clarification": clarification,
        "continuation": ({"intent_id": str(continuation["id"]), "status": continuation["status"]}
                         if continuation else None),
        "pipeline": dict(pipeline) if pipeline else None,
    }


def participant_trace(trace: dict) -> dict:
    """Only delivered dialogue/material; no execution envelope, hidden cards or AI reasoning."""
    return {'assessment_situation_id':trace['assessment_situation_id'],'status':trace['status'],
        'turns':[{**{k:x[k] for k in ('turn_id','sequence_no','speaker_type','speaker_id','content_text')},
                  'speaker_name':x.get('speaker_name')} for x in trace['turns']],
        'events':[{k:x[k] for k in ('event_id','event_type','sequence_no','material_id','payload_json')}
                  for x in trace['events'] if x['event_type'] in ('material_disclosed','mandatory_update')]}


def participant_presentation(result: dict) -> dict:
    """Projection of a start/next response; internal execution stays server-side."""
    presentation = result.get('presentation')
    if not presentation:
        return result
    return {**result, 'presentation': {k: v for k, v in presentation.items()
        if k in ('assessment_situation_id', 'status', 'participant_payload', 'idempotent')}}

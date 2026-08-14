from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ComponentDescriptor:
    code: str
    version: int
    kind: str
    handler: Callable[..., Any] | None = None


class ComponentRegistry:
    def __init__(self) -> None:
        self._components: dict[tuple[str, int], ComponentDescriptor] = {}

    def register(self, descriptor: ComponentDescriptor) -> None:
        key = (descriptor.code, descriptor.version)
        if key in self._components:
            raise ValueError(f"Assessment component is already registered: {descriptor.code} v{descriptor.version}")
        self._components[key] = descriptor

    def resolve(self, code: str, version: int) -> ComponentDescriptor:
        try:
            return self._components[(code, version)]
        except KeyError as exc:
            raise ValueError(f"Unknown assessment component: {code} v{version}") from exc

    def contains(self, code: str, version: int) -> bool:
        return (code, version) in self._components


component_registry = ComponentRegistry()

for _code, _kind in (
    ("profile.prepare", "preparation"),
    ("cases.select", "preparation"),
    ("cases.personalize", "preparation"),
    ("interview.case_dialog", "interview"),
    ("evaluation.run_methodology_evaluators", "evaluation"),
    ("evaluation.communication", "competency_evaluator"),
    ("evaluation.teamwork", "competency_evaluator"),
    ("evaluation.creativity", "competency_evaluator"),
    ("evaluation.critical_thinking", "competency_evaluator"),
    ("evaluation.aggregate", "aggregation"),
    ("report.build", "report"),
):
    component_registry.register(ComponentDescriptor(code=_code, version=1, kind=_kind))


def validate_scenario_definition(definition: dict[str, Any]) -> None:
    stages = definition.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("Assessment scenario must contain at least one stage.")
    stage_ids = {str(stage.get("id") or "").strip() for stage in stages if isinstance(stage, dict)}
    if "" in stage_ids:
        raise ValueError("Every assessment scenario stage must have an id.")
    initial_stage = str(definition.get("initial_stage") or "").strip()
    if initial_stage not in stage_ids:
        raise ValueError("Assessment scenario initial_stage is not defined.")

    for stage in stages:
        code = str(stage.get("component") or "").strip()
        version = int(stage.get("component_version") or 0)
        if "mbti" in code.lower():
            raise ValueError("MBTI components are not allowed in the 4K assessment runtime.")
        component_registry.resolve(code, version)
        transition = str(stage.get("on_success") or "").strip()
        if transition and transition != "complete_session" and transition not in stage_ids:
            raise ValueError(f"Unknown success transition '{transition}' for stage '{stage['id']}'.")


def start_stage_run(connection, *, session_id: int, stage_id: str, component_code: str, component_version: int) -> int:
    row = connection.execute(
        """
        INSERT INTO assessment_stage_runs (
            session_id, stage_id, component_code, component_version, attempt, status, started_at
        )
        VALUES (
            %s, %s, %s, %s,
            COALESCE((SELECT MAX(attempt) + 1 FROM assessment_stage_runs WHERE session_id = %s AND stage_id = %s), 1),
            'running', NOW()
        )
        RETURNING id
        """,
        (session_id, stage_id, component_code, component_version, session_id, stage_id),
    ).fetchone()
    connection.execute("UPDATE user_sessions SET current_stage_id = %s WHERE id = %s", (stage_id, session_id))
    return int(row["id"])


def complete_stage_run(connection, *, stage_run_id: int, output: dict[str, Any] | None = None) -> None:
    import json

    connection.execute(
        """
        UPDATE assessment_stage_runs
        SET status = 'completed', output_json = %s::jsonb, completed_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(output or {}, ensure_ascii=False), stage_run_id),
    )


def fail_stage_run(connection, *, stage_run_id: int, error: Exception) -> None:
    connection.execute(
        """
        UPDATE assessment_stage_runs
        SET status = 'failed', error_code = %s, error_message = %s, completed_at = NOW()
        WHERE id = %s
        """,
        (error.__class__.__name__, str(error)[:2000], stage_run_id),
    )


@dataclass(slots=True)
class ScenarioExecutionContext:
    connection: Any
    session_id: int
    user_id: int
    snapshot: dict[str, Any]
    stage: dict[str, Any]

    @property
    def methodology(self) -> dict[str, Any]:
        return dict(self.snapshot.get("methodology", {}).get("definition") or {})


class ScenarioRunner:
    def load_snapshot(self, connection, *, session_id: int) -> dict[str, Any]:
        row = connection.execute(
            "SELECT execution_snapshot_json FROM user_sessions WHERE id = %s",
            (session_id,),
        ).fetchone()
        if row is None or not isinstance(row["execution_snapshot_json"], dict):
            raise ValueError("Assessment session does not contain an execution snapshot.")
        return dict(row["execution_snapshot_json"])

    def resolve_stage(self, snapshot: dict[str, Any], *, stage_id: str) -> dict[str, Any]:
        scenario = dict(snapshot.get("scenario", {}).get("definition") or {})
        validate_scenario_definition(scenario)
        for stage in scenario["stages"]:
            if str(stage.get("id")) == stage_id:
                return dict(stage)
        raise ValueError(f"Assessment scenario stage was not found: {stage_id}")

    def run_stage(
        self,
        connection,
        *,
        session_id: int,
        user_id: int,
        stage_id: str,
        executor: Callable[[ScenarioExecutionContext], dict[str, Any] | None],
        snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective_snapshot = snapshot or self.load_snapshot(connection, session_id=session_id)
        stage = self.resolve_stage(effective_snapshot, stage_id=stage_id)
        component_code = str(stage["component"])
        component_version = int(stage["component_version"])
        component_registry.resolve(component_code, component_version)
        stage_run_id = start_stage_run(
            connection,
            session_id=session_id,
            stage_id=stage_id,
            component_code=component_code,
            component_version=component_version,
        )
        context = ScenarioExecutionContext(
            connection=connection,
            session_id=session_id,
            user_id=user_id,
            snapshot=effective_snapshot,
            stage=stage,
        )
        try:
            output = dict(executor(context) or {})
        except Exception as exc:
            fail_stage_run(connection, stage_run_id=stage_run_id, error=exc)
            raise
        complete_stage_run(connection, stage_run_id=stage_run_id, output=output)
        return {"stage": stage, "output": output, "snapshot": effective_snapshot}


scenario_runner = ScenarioRunner()

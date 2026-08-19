from __future__ import annotations

import json
from datetime import timedelta

from Api.database import get_connection


class OperationProgressService:
    """Database-backed operation progress shared by every API worker."""

    def __init__(self) -> None:
        self._ttl = timedelta(minutes=15)

    def begin(self, operation_id: str | None, *, title: str, message: str, steps: list[dict[str, str]]) -> None:
        if not operation_id:
            return
        normalized_steps = [
            {
                "label": str(step.get("label") or "").strip(),
                "description": str(step.get("description") or "").strip(),
                "status": "pending",
            }
            for step in steps
        ] or [{"label": "Подготовка", "description": "Система обрабатывает запрос.", "status": "pending"}]
        normalized_steps[0]["status"] = "active"
        with get_connection() as connection:
            self._prune(connection)
            connection.execute(
                """
                INSERT INTO operation_progress (
                    operation_id, title, message, steps_json,
                    current_step_index, status, updated_at
                )
                VALUES (%s, %s, %s, %s::jsonb, 0, 'in_progress', NOW())
                ON CONFLICT (operation_id) DO UPDATE
                SET title = EXCLUDED.title,
                    message = EXCLUDED.message,
                    steps_json = EXCLUDED.steps_json,
                    current_step_index = 0,
                    status = 'in_progress',
                    updated_at = NOW()
                """,
                (operation_id, title, message, json.dumps(normalized_steps, ensure_ascii=False)),
            )

    def advance(
        self,
        operation_id: str | None,
        step_index: int,
        *,
        title: str | None = None,
        message: str | None = None,
    ) -> None:
        if not operation_id:
            return
        with get_connection() as connection:
            row = connection.execute(
                "SELECT title, message, steps_json FROM operation_progress WHERE operation_id = %s FOR UPDATE",
                (operation_id,),
            ).fetchone()
            if row is None:
                return
            steps = self._steps(row["steps_json"])
            bounded_index = max(0, min(step_index, len(steps) - 1))
            for index, step in enumerate(steps):
                step["status"] = "done" if index < bounded_index else "active" if index == bounded_index else "pending"
            connection.execute(
                """
                UPDATE operation_progress
                SET title = %s,
                    message = %s,
                    steps_json = %s::jsonb,
                    current_step_index = %s,
                    updated_at = NOW()
                WHERE operation_id = %s
                """,
                (
                    title or row["title"],
                    message or row["message"],
                    json.dumps(steps, ensure_ascii=False),
                    bounded_index,
                    operation_id,
                ),
            )

    def complete(self, operation_id: str | None, *, title: str | None = None, message: str | None = None) -> None:
        self._finish(operation_id, status="completed", title=title, message=message)

    def fail(self, operation_id: str | None, *, message: str) -> None:
        self._finish(operation_id, status="failed", title=None, message=message)

    def snapshot(self, operation_id: str | None) -> dict | None:
        if not operation_id:
            return None
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT operation_id, title, message, steps_json,
                       current_step_index, status
                FROM operation_progress
                WHERE operation_id = %s
                """,
                (operation_id,),
            ).fetchone()
        if row is None:
            return None
        steps = self._steps(row["steps_json"])
        total_steps = max(len(steps), 1)
        current_step_index = int(row["current_step_index"] or 0)
        progress_percent = round(((current_step_index + 1) / total_steps) * 100)
        return {
            "operation_id": row["operation_id"],
            "title": row["title"],
            "message": row["message"],
            "status": row["status"],
            "current_step_index": current_step_index,
            "progress_percent": progress_percent,
            "steps": steps,
        }

    def _finish(
        self,
        operation_id: str | None,
        *,
        status: str,
        title: str | None,
        message: str | None,
    ) -> None:
        if not operation_id:
            return
        with get_connection() as connection:
            row = connection.execute(
                "SELECT title, message, steps_json, current_step_index FROM operation_progress WHERE operation_id = %s FOR UPDATE",
                (operation_id,),
            ).fetchone()
            if row is None:
                return
            steps = self._steps(row["steps_json"])
            if status == "completed":
                for step in steps:
                    step["status"] = "done"
                current_step_index = max(0, len(steps) - 1)
            else:
                current_step_index = max(0, min(int(row["current_step_index"] or 0), len(steps) - 1))
                if steps:
                    steps[current_step_index]["status"] = "error"
            connection.execute(
                """
                UPDATE operation_progress
                SET title = %s,
                    message = %s,
                    steps_json = %s::jsonb,
                    current_step_index = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE operation_id = %s
                """,
                (
                    title or row["title"],
                    message or row["message"],
                    json.dumps(steps, ensure_ascii=False),
                    current_step_index,
                    status,
                    operation_id,
                ),
            )

    def _prune(self, connection) -> None:
        connection.execute(
            "DELETE FROM operation_progress WHERE updated_at < NOW() - %s::interval",
            (f"{int(self._ttl.total_seconds())} seconds",),
        )

    def _steps(self, value) -> list[dict[str, str]]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        return [dict(item) for item in value] if isinstance(value, list) else []


operation_progress_service = OperationProgressService()

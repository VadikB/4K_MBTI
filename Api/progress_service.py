from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock


@dataclass(slots=True)
class OperationProgressState:
    operation_id: str
    title: str
    message: str
    steps: list[dict[str, str]]
    current_step_index: int = 0
    status: str = "in_progress"
    updated_at: datetime = field(default_factory=datetime.utcnow)


class OperationProgressService:
    def __init__(self) -> None:
        self._operations: dict[str, OperationProgressState] = {}
        self._lock = Lock()
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
        ] or [
            {"label": "Подготовка", "description": "Система обрабатывает запрос.", "status": "pending"},
        ]
        normalized_steps[0]["status"] = "active"
        with self._lock:
            self._prune_locked()
            self._operations[operation_id] = OperationProgressState(
                operation_id=operation_id,
                title=title,
                message=message,
                steps=normalized_steps,
            )

    def advance(self, operation_id: str | None, step_index: int, *, title: str | None = None, message: str | None = None) -> None:
        if not operation_id:
            return
        with self._lock:
            state = self._operations.get(operation_id)
            if state is None:
                return
            bounded_index = max(0, min(step_index, len(state.steps) - 1))
            for index, step in enumerate(state.steps):
                if index < bounded_index:
                    step["status"] = "done"
                elif index == bounded_index:
                    step["status"] = "active"
                else:
                    step["status"] = "pending"
            state.current_step_index = bounded_index
            if title:
                state.title = title
            if message:
                state.message = message
            state.updated_at = datetime.utcnow()

    def complete(self, operation_id: str | None, *, title: str | None = None, message: str | None = None) -> None:
        if not operation_id:
            return
        with self._lock:
            state = self._operations.get(operation_id)
            if state is None:
                return
            for step in state.steps:
                step["status"] = "done"
            state.current_step_index = len(state.steps) - 1
            state.status = "completed"
            if title:
                state.title = title
            if message:
                state.message = message
            state.updated_at = datetime.utcnow()

    def fail(self, operation_id: str | None, *, message: str) -> None:
        if not operation_id:
            return
        with self._lock:
            state = self._operations.get(operation_id)
            if state is None:
                return
            if state.steps:
                state.steps[state.current_step_index]["status"] = "error"
            state.status = "failed"
            state.message = message
            state.updated_at = datetime.utcnow()

    def snapshot(self, operation_id: str | None) -> dict | None:
        if not operation_id:
            return None
        with self._lock:
            self._prune_locked()
            state = self._operations.get(operation_id)
            if state is None:
                return None
            total_steps = max(len(state.steps), 1)
            progress_percent = round(((state.current_step_index + 1) / total_steps) * 100)
            return {
                "operation_id": state.operation_id,
                "title": state.title,
                "message": state.message,
                "status": state.status,
                "current_step_index": state.current_step_index,
                "progress_percent": progress_percent,
                "steps": [dict(step) for step in state.steps],
            }

    def _prune_locked(self) -> None:
        threshold = datetime.utcnow() - self._ttl
        stale = [key for key, value in self._operations.items() if value.updated_at < threshold]
        for key in stale:
            self._operations.pop(key, None)


operation_progress_service = OperationProgressService()

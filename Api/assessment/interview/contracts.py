from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InterviewerTurnResult:
    assistant_message: str
    is_case_complete: bool
    result_status: str
    completion_score: float | None
    evaluator_summary: str

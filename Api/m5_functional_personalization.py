"""Техническая граница ответа генератора функциональной персонализации."""
from __future__ import annotations

from typing import Any


KNOWN_RESPONSE_ENVELOPE_FIELDS = frozenset({
    "profile", "candidate_as", "tester_conclusion", "repair_constraints",
})


def extract_candidate_as(response_json: Any) -> tuple[Any, int]:
    """Снять только строго опознанный технический envelope, не изменяя AS.

    Объект с неизвестным полем или собственным CaseID не распаковывается.
    """
    candidate, depth = response_json, 0
    while (
        isinstance(candidate, dict)
        and "CaseID" not in candidate
        and isinstance(candidate.get("candidate_as"), dict)
        and set(candidate) <= KNOWN_RESPONSE_ENVELOPE_FIELDS
    ):
        candidate = candidate["candidate_as"]
        depth += 1
    return candidate, depth

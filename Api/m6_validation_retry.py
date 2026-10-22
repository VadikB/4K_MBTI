from __future__ import annotations

import json
from collections.abc import Callable

from Api.m5_rule_engine import _call_with_trace


def call_and_validate(*, gateway, messages: list[dict], operation: dict, routing_key: str,
                      validate: Callable[[dict], dict], max_attempts: int) -> tuple[dict, dict]:
    """Retry only rejected provider output; never coerce or partially accept it."""
    attempts: list[dict] = []
    current_messages = list(messages)
    last_error: Exception | None = None
    for attempt_no in range(1, max_attempts + 1):
        raw, trace = _call_with_trace(
            gateway, current_messages, operation=operation,
            routing_key=f"{routing_key}:validation:{attempt_no}",
        )
        try:
            if trace["identity_status"] != "sent_matches_snapshot":
                raise ValueError("M6_AI_IDENTITY_MISMATCH")
            output = validate(json.loads(raw))
        except Exception as exc:
            last_error = exc
            attempts.append({"attempt_no": attempt_no, "status": "rejected",
                             "error_code": type(exc).__name__, "trace": trace})
            if attempt_no == max_attempts:
                combined = dict(trace)
                combined["validation_attempts"] = attempts
                exc.ai_trace = combined
                raise
            current_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Предыдущий JSON отклонён строгой проверкой контракта "
                    f"({type(exc).__name__}). Верни заново только полный JSON по исходной "
                    "схеме и данным. Не копируй неподдерживаемые поля и проверь все "
                    "межполевые инварианты перед ответом."
                )},
            ]
            continue
        attempts.append({"attempt_no": attempt_no, "status": "accepted", "trace": trace})
        combined = dict(trace)
        combined["validation_attempts"] = attempts
        return output, combined
    assert last_error is not None
    raise last_error

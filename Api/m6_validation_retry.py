from __future__ import annotations

import json
from collections.abc import Callable

from Api.m5_rule_engine import _call_with_trace


def _fragment_span_hints(raw: str, messages: list[dict]) -> str:
    """Offer deterministic index hints to the provider; never mutate its candidate."""
    try:
        candidate = json.loads(raw)
        material = json.loads(messages[-1]["content"])
        turns = {str(item["turn_id"]): str(item["content"]) for item in material["turns"]}
        hints = []
        for fragment in candidate.get("fragments", []):
            content = turns.get(str(fragment.get("turn_id")))
            quote = fragment.get("quote")
            if content is None or not isinstance(quote, str) or not quote:
                continue
            start = content.find(quote)
            if start >= 0 and content.find(quote, start + 1) < 0:
                hints.append(f"{fragment.get('id')}: start={start}, end={start + len(quote)}")
        return (" Проверенные подсказки для однозначно найденных дословных цитат: "
                + "; ".join(hints) + ".") if hints else ""
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ""


def _attribution_hints(messages: list[dict]) -> str:
    """Repeat immutable criterion fields that the provider must copy verbatim."""
    try:
        material = json.loads(messages[-1]["content"])
        expected = {item["id"]: {
            "function": item["function"], "product": item["product"],
            "evidence_pattern": item["evidence_pattern"], "boundaries": item["boundary"],
        } for item in material["criteria"]}
        return (" Поле attribution для каждого evidence должно быть дословной копией соответствующего "
                "критерия без пересказа: " + json.dumps(expected, ensure_ascii=False, separators=(",", ":")) + ".")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ""


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
            validation_code = str(exc) if isinstance(exc, ValueError) and str(exc) else type(exc).__name__
            attempts.append({"attempt_no": attempt_no, "status": "rejected",
                             "error_code": validation_code[:200], "trace": trace})
            if attempt_no == max_attempts:
                combined = dict(trace)
                combined["validation_attempts"] = attempts
                exc.ai_trace = combined
                raise
            span_hints = _fragment_span_hints(raw, messages) if validation_code == "M6_FRAGMENT_SPAN" else ""
            attribution_hints = _attribution_hints(messages)
            current_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Предыдущий JSON отклонён строгой проверкой контракта "
                    f"({validation_code}). Верни заново только полный JSON по исходной "
                    "схеме и данным. Не копируй неподдерживаемые поля и проверь все "
                    "межполевые инварианты перед ответом. "
                    + ("Для каждого fragment используй индексы Unicode code points с нуля: "
                       "end-start должен быть равен len(quote), а content[start:end] — в точности quote; "
                       "не включай в quote пропущенный текст и многоточия." + span_hints
                       if validation_code == "M6_FRAGMENT_SPAN" else "")
                    + attribution_hints
                )},
            ]
            continue
        attempts.append({"attempt_no": attempt_no, "status": "accepted", "trace": trace})
        combined = dict(trace)
        combined["validation_attempts"] = attempts
        return output, combined
    assert last_error is not None
    raise last_error

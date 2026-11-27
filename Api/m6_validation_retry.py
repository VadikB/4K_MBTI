from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from Api.m5_rule_engine import _call_with_trace


def _validation_failure(exc: Exception, candidate: object, messages: list[dict]) -> dict:
    if isinstance(exc, ValidationError):
        issues = []
        for item in exc.errors(include_input=False, include_context=False, include_url=False)[:20]:
            path = list(item["loc"])
            if item["type"] == "extra_forbidden":
                path[-1] = "<extra>"
            issues.append({"path": path, "rule": item["type"]})
        return {"error_code": "M6_SCHEMA_VALIDATION", "stage": "schema",
                "issue_count": exc.error_count(), "issues": issues}
    if isinstance(exc, json.JSONDecodeError):
        return {"error_code": "M6_INVALID_JSON", "stage": "json"}
    code = str(exc) if isinstance(exc, ValueError) else ""
    if not re.fullmatch(r"[A-Z][A-Z0-9_:-]{2,199}", code):
        code = type(exc).__name__
    failure = {"error_code": code, "stage": "identity" if code == "M6_AI_IDENTITY_MISMATCH" else "contract"}
    if code == "M6_FRAGMENT_SPAN":
        issue = _fragment_span_issue(candidate, messages)
        if issue:
            failure["issues"] = [issue]
    return failure


def _is_fragment_span_failure(failure: dict) -> bool:
    return failure["error_code"] == "M6_FRAGMENT_SPAN" or (
        failure["stage"] == "schema" and any(
            len(path) == 3 and path[0] == "fragments" and isinstance(path[1], int) and path[2] in {"start", "end"}
            for path in (issue["path"] for issue in failure["issues"])
        )
    )


def _referenced_fragments(candidate: object, messages: list[dict]):
    if not isinstance(candidate, dict) or not isinstance(candidate.get("fragments"), list):
        return
    material = json.loads(messages[-1]["content"])
    turns = {
        turn["turn_id"]: turn["content"]
        for turn in material.get("turns", [])
        if turn["speaker_type"] == "assessee"
    }
    for index, fragment in enumerate(candidate["fragments"]):
        if not isinstance(fragment, dict):
            continue
        turn_id, quote = fragment.get("turn_id"), fragment.get("quote")
        if isinstance(turn_id, str) and isinstance(quote, str) and quote and turn_id in turns:
            yield index, fragment, turns[turn_id], quote


def _fragment_span_issue(candidate: object, messages: list[dict]) -> dict | None:
    """Explain an existing validator rejection without changing the frozen contract."""
    for index, fragment, content, quote in _referenced_fragments(candidate, messages):
        start, end = fragment.get("start"), fragment.get("end")
        if type(start) is not int or type(end) is not int:
            continue
        if start >= end:
            return {"path": ["fragments", index, "end"], "rule": "span_end_not_after_start"}
        if end > len(content):
            return {"path": ["fragments", index, "end"], "rule": "span_end_exceeds_turn"}
        if content[start:end] != quote:
            return {"path": ["fragments", index, "quote"], "rule": "span_quote_mismatch"}
    return None


def _fragment_span_hints(candidate: object, messages: list[dict]) -> str:
    """Find a unique exact quote in the referenced assessee turn."""
    hints = []
    for index, _, content, quote in _referenced_fragments(candidate, messages):
        start = content.find(quote)
        if start >= 0 and content.find(quote, start + 1) < 0:
            hints.append(f"fragments[{index}]: start={start}, end={start + len(quote)}")
    return (" Проверенные позиции однозначных дословных цитат: " + "; ".join(hints) + ".") if hints else ""


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


def _context_reference_hints(messages: list[dict]) -> str:
    """Expose only the closed reference namespaces already present in M6 input."""
    try:
        material = json.loads(messages[-1]["content"])
        allowed = {
            "turn": [str(item["turn_id"]) for item in material["turns"]],
            "event": [str(item["event_id"]) for item in material["events"]],
            "material": [str(item["material_id"]) for item in material["materials"]],
        }
        return (
            " Допустимые context_refs образуют закрытый список "
            "{kind,id} из входа: "
            + json.dumps(allowed, ensure_ascii=False, separators=(",", ":"))
            + ". Не используй speaker_id, fragment/BS/evidence ID, ID из initial_presentation "
              "или непредъявленного материала. Сохраняй только содержательно нужные refs; "
              "не заменяй ошибочную ссылку произвольной допустимой."
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ""


def call_and_validate(*, gateway, messages: list[dict], operation: dict, routing_key: str,
                      validate: Callable[[dict], dict], max_attempts: int) -> tuple[dict, dict]:
    """Retry only rejected provider output; never coerce or partially accept it."""
    attempts: list[dict] = []
    current_messages = list(messages)
    last_error: Exception | None = None
    for attempt_no in range(1, max_attempts + 1):
        try:
            raw, trace = _call_with_trace(
                gateway, current_messages, operation=operation,
                routing_key=f"{routing_key}:validation:{attempt_no}",
            )
        except Exception as exc:
            if attempts:
                exc.ai_trace = {**getattr(exc, "ai_trace", {}), "validation_attempts": attempts}
            raise
        candidate = None
        try:
            if trace["identity_status"] != "sent_matches_snapshot":
                raise ValueError("M6_AI_IDENTITY_MISMATCH")
            candidate = json.loads(raw)
            output = validate(candidate)
        except Exception as exc:
            last_error = exc
            failure = _validation_failure(exc, candidate, messages)
            validation_code = failure["error_code"]
            attempts.append({"attempt_no": attempt_no, "status": "rejected", **failure, "trace": trace})
            if attempt_no == max_attempts:
                combined = dict(trace)
                combined["validation_attempts"] = attempts
                exc.ai_trace = combined
                raise
            span_failure = _is_fragment_span_failure(failure)
            span_hints = _fragment_span_hints(candidate, messages) if span_failure and candidate is not None else ""
            schema_hints = (
                " Ошибки схемы (путь и правило): " + json.dumps(failure["issues"], ensure_ascii=False) + "."
                if failure["stage"] == "schema" else ""
            )
            attribution_hints = _attribution_hints(messages)
            context_hints = (_context_reference_hints(messages)
                             if validation_code == "M6_CONTEXT_REFERENCE" else "")
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
                       if span_failure else "")
                    + schema_hints
                    + context_hints
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

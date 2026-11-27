from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

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


def validation_failure(exc: Exception) -> tuple[str, list[dict]]:
    if isinstance(exc, ValidationError):
        issues = []
        for error in exc.errors(include_url=False, include_input=False, include_context=False):
            location = error["loc"]
            if error["type"] == "extra_forbidden" and location[-1] not in {"start", "end"}:
                # The provider controls the unknown property name.
                location = (*location[:-1], "<extra>")
            path = ".".join(map(str, location)) or "$"
            issues.append({"code": error["type"], "path": path})
        return "ValidationError", issues
    if isinstance(exc, json.JSONDecodeError):
        return "JSONDecodeError", [{"code": "INVALID_JSON", "path": "$"}]
    message = str(exc) if isinstance(exc, ValueError) else ""
    code = message if re.fullmatch(r"[A-Z][A-Z0-9_:-]{2,199}", message) else type(exc).__name__
    return code, getattr(exc, "validation_issues", [{"code": code, "path": "$"}])


def _quote_feedback(issues: list[dict]) -> str:
    codes = {issue["code"] for issue in issues}
    feedback = []
    if "M6_FRAGMENT_QUOTE_AMBIGUOUS" in codes:
        feedback.append("Удлини дословную цитату из того же хода вокруг выбранного места, "
                        "чтобы расширенная цитата встретилась в этом ходе ровно один раз. Сохрани id фрагмента.")
    if "M6_FRAGMENT_QUOTE_NOT_FOUND" in codes:
        feedback.append("Цитата отсутствует в указанном ходе. Проверь точный turn_id и дословно "
                        "скопируй выбранный участок из этого хода без нормализации и пересказа. Сохрани id фрагмента.")
    if codes & {"M6_FRAGMENT_AUTHOR", "M6_FRAGMENT_TURN_UNKNOWN"}:
        feedback.append("Укажи точный turn_id хода участника из предоставленного ввода и сохрани id фрагмента.")
    return " ".join(feedback)


def call_and_validate(*, gateway, messages: list[dict], operation: dict, routing_key: str,
                      validate: Callable[[dict], dict], max_attempts: int,
                      response_contract: dict | None = None) -> tuple[dict, dict]:
    """Retry only rejected provider output; never partially accept it."""
    attempts: list[dict] = []
    provider_attempts: list[dict] = []
    current_messages = list(messages)
    for attempt_no in range(1, max_attempts + 1):
        try:
            raw, trace = _call_with_trace(
                gateway, current_messages, operation=operation,
                routing_key=f"{routing_key}:validation:{attempt_no}",
                response_contract=response_contract,
            )
        except Exception as exc:
            trace = getattr(exc, "ai_trace", {})
            provider_attempts.append({"attempt_no": attempt_no, "trace": trace})
            attempts.append({"attempt_no": attempt_no, "status": "technical_failure",
                             "error_code": type(exc).__name__})
            exc.ai_trace = {**trace, "provider_attempts": provider_attempts, "validation_attempts": attempts}
            raise
        provider_attempts.append({"attempt_no": attempt_no, "trace": trace})
        try:
            if trace["identity_status"] != "sent_matches_snapshot":
                raise ValueError("M6_AI_IDENTITY_MISMATCH")
            output = validate(json.loads(raw))
        except Exception as exc:
            validation_code, issues = validation_failure(exc)
            attempts.append({"attempt_no": attempt_no, "status": "rejected",
                             "error_code": validation_code, "validation_errors": issues})
            if attempt_no == max_attempts:
                exc.ai_trace = {**trace, "provider_attempts": provider_attempts, "validation_attempts": attempts}
                raise
            span_hints = _fragment_span_hints(raw, messages) if validation_code == "M6_FRAGMENT_SPAN" else ""
            attribution_hints = _attribution_hints(messages)
            context_hints = (_context_reference_hints(messages)
                             if any(issue["code"] == "M6_CONTEXT_REFERENCE" for issue in issues) else "")
            current_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Предыдущий JSON отклонён строгой проверкой контракта "
                    f"({validation_code}). Нарушения по путям полей: "
                    + json.dumps(issues, ensure_ascii=False, separators=(",", ":"))
                    + ". Верни заново только полный JSON по исходной схеме и данным. "
                    "Проверь все ссылки и поля. "
                    + ("Для каждого fragment используй индексы Unicode code points с нуля: "
                       "end-start должен быть равен len(quote), а content[start:end] — в точности quote; "
                       "не включай в quote пропущенный текст и многоточия." + span_hints
                       if validation_code == "M6_FRAGMENT_SPAN" else "")
                    + _quote_feedback(issues)
                    + context_hints
                    + attribution_hints
                )},
            ]
            continue
        attempts.append({"attempt_no": attempt_no, "status": "accepted"})
        return output, {**trace, "provider_attempts": provider_attempts, "validation_attempts": attempts}
    raise ValueError("M6_VALIDATION_BUDGET_INVALID")

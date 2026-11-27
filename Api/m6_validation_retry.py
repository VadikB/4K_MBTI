from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from Api.m5_rule_engine import _call_with_trace
from Api.m6_contracts import ValidationIssues, candidate_records, check_fragment_span, fragment_turn, quote_position


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
    for index, fragment in candidate_records(candidate, "fragments"):
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


def _fragment_span_hints(candidate: object, messages: list[dict], indices: set[int] | None = None) -> str:
    """Find a unique exact quote in the referenced assessee turn."""
    hints = []
    for index, _, content, quote in _referenced_fragments(candidate, messages):
        if indices is not None and index not in indices:
            continue
        start, reason = quote_position(content, quote)
        if reason is None:
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
        return "M6_SCHEMA_VALIDATION", issues + getattr(exc, "validation_issues", [])
    if isinstance(exc, json.JSONDecodeError):
        return "M6_INVALID_JSON", [{"code": "INVALID_JSON", "path": "$"}]
    message = str(exc) if isinstance(exc, ValueError) else ""
    code = message if re.fullmatch(r"[A-Z][A-Z0-9_:-]{2,199}", message) else type(exc).__name__
    return code, getattr(exc, "validation_issues", [{"code": code, "path": "$"}])


def _legacy_quote_issues(candidate: object, material: dict) -> list[dict]:
    """Recover citation issues hidden by schema errors elsewhere in the answer."""
    turns = {turn["turn_id"]: turn for turn in material["turns"]}
    issues = ValidationIssues()
    for index, fragment in candidate_records(candidate, "fragments"):
        turn_id = fragment.get("turn_id")
        if not isinstance(turn_id, str):
            continue
        path = f"fragments.{index}"
        turn = fragment_turn(turns, turn_id, path, issues)
        if turn is not None:
            start, end, quote = fragment.get("start"), fragment.get("end"), fragment.get("quote")
            check_fragment_span(
                turn["content"],
                start if type(start) is int and start >= 0 else None,
                end if type(end) is int and end > 0 else None,
                quote if isinstance(quote, str) and quote else None,
                path, issues,
            )
    return issues.items


def _missing_indicator_ids(candidate: object, material: dict) -> list[str]:
    if not isinstance(candidate, dict) or not isinstance(candidate.get("bundles"), list):
        return []
    returned_ids = {record["indicator_id"] for _, record in candidate_records(candidate, "bundles")
                    if isinstance(record.get("indicator_id"), str)}
    return [target["indicator_id"] for target in material["indicator_targets"]
            if target["indicator_id"] not in returned_ids]


def _bundle_feedback(missing_ids: list[str]) -> str:
    if not missing_ids:
        return ""
    return (" Недостающие indicator_id в bundles: " + ", ".join(missing_ids) + ". "
            "Добавь ровно одну запись на каждый недостающий индикатор. "
            "Для индикатора без подтверждённого свидетельства укажи evidence_ids=[] и конкретное "
            "opportunity_basis по исходному ходу и условиям ситуации. "
            "Сохрани корректные bundles, fragments, signals, evidence, их ID и связи. "
            "Исправь только ошибочные записи и затронутые зависимости.")


def _quote_issue_indices(issues: list[dict]) -> set[int]:
    return {int(match[1]) for issue in issues
            if (match := re.fullmatch(r"fragments\.(\d+)\.(start|end|quote|turn_id)", issue["path"]))}


def _quote_turn_feedback(candidate: object, material: dict, indices: set[int]) -> str:
    turn_ids = {turn["turn_id"] for turn in material["turns"] if turn["speaker_type"] == "assessee"}
    sources = {}
    for index, fragment in candidate_records(candidate, "fragments"):
        turn_id = fragment.get("turn_id")
        if index in indices and isinstance(turn_id, str) and turn_id in turn_ids:
            sources[f"fragments[{index}]"] = turn_id
    return (" Исходные turn_id цитат участника: " + json.dumps(sources, ensure_ascii=False) + ".") if sources else ""


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
    if any(issue["code"] == "string_too_short" and issue["path"].endswith(".quote") for issue in issues):
        feedback.append("Для пустой цитаты выбери подтверждающий дословный фрагмент из исходного хода.")
    feedback.append("При правке сохрани наблюдение и основание для того же индикатора. "
                    "Если исходный ход не подтверждает наблюдение, пересмотри зависимые записи. "
                    "При пересмотре атрибуции заполни attribution_notes по правилам исходного запроса.")
    return " ".join(feedback)


def call_and_validate(*, gateway, messages: list[dict], operation: dict, routing_key: str,
                      validate: Callable[[dict], dict], max_attempts: int,
                      response_contract: dict | None = None,
                      evidence_material: dict | None = None) -> tuple[dict, dict]:
    """Retry only rejected provider output; never partially accept it."""
    attempts: list[dict] = []
    provider_attempts: list[dict] = []
    quote_contract = response_contract is not None
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
        candidate = None
        try:
            if trace["identity_status"] != "sent_matches_snapshot":
                raise ValueError("M6_AI_IDENTITY_MISMATCH")
            candidate = json.loads(raw)
            output = validate(candidate)
        except Exception as exc:
            validation_code, issues = validation_failure(exc)
            failure = {"error_code": validation_code} if quote_contract else _validation_failure(exc, candidate, messages)
            missing_ids = []
            if evidence_material is not None:
                missing_ids = _missing_indicator_ids(candidate, evidence_material)
                if missing_ids:
                    failure["missing_indicator_ids"] = missing_ids
                if not quote_contract and isinstance(exc, ValidationError):
                    issues = issues + _legacy_quote_issues(candidate, evidence_material)
            attempts.append({"attempt_no": attempt_no, "status": "rejected", **failure,
                             "validation_errors": issues})
            if attempt_no == max_attempts:
                exc.ai_trace = {**trace, "provider_attempts": provider_attempts, "validation_attempts": attempts}
                raise
            quote_indices = _quote_issue_indices(issues) if evidence_material is not None else set()
            span_failure = not quote_contract and (bool(quote_indices) or _is_fragment_span_failure(failure))
            span_hints = _fragment_span_hints(candidate, messages, quote_indices or None) if span_failure else ""
            quote_turns = _quote_turn_feedback(candidate, evidence_material, quote_indices) if quote_indices else ""
            schema_hints = (
                " Ошибки схемы (путь и правило): " + json.dumps(failure["issues"], ensure_ascii=False) + "."
                if failure.get("stage") == "schema" else ""
            )
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
                    "Проверь все ссылки и поля."
                    + (" Для каждого fragment используй индексы Unicode code points с нуля: "
                       "end-start должен быть равен len(quote), а content[start:end] — в точности quote; "
                       "не включай в quote пропущенный текст и многоточия." + span_hints
                       if span_failure else "")
                    + schema_hints
                    + quote_turns
                    + (" " + _quote_feedback(issues) if quote_contract or quote_indices else "")
                    + _bundle_feedback(missing_ids)
                    + context_hints
                    + attribution_hints
                )},
            ]
            continue
        attempts.append({"attempt_no": attempt_no, "status": "accepted"})
        return output, {**trace, "provider_attempts": provider_attempts, "validation_attempts": attempts}
    raise ValueError("M6_VALIDATION_BUDGET_INVALID")

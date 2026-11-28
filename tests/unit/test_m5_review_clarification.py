"""Controlled SPEC.02 replies and replay of receipts for scoped M5 clarification."""
from copy import deepcopy
import json
from time import sleep
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from Api.assessment_start_readiness import functional_gate
from Api.cycle_execution_manifest import (
    BATTERY_V04_SCENARIO_CURRENT, M5_BATTERY_PILOT_REVIEW_PACKAGES, M5_REVIEW_RESPONSE_PACKAGE, ROOT,
)
from Api.llm.deepseek_gateway import OperationBudget
from Api.m5_functional_generation_service import build_passport_snapshot, build_persistence_trace, checksum, prepare
from Api.m5_review_clarification import CLARIFICATION_SUFFIX
from tests.integration.test_m5_battery_v04_db import V04Gateway
from tests.unit.test_m5_v7_start_review import pilot_cases

CLARITY = "quality.clarity"
AUTHORITY = "common.authority"
ROLE_TRACE = {"tester": "provider_operation", "challenger": "challenger_operation"}
MATERIAL_TEXT = (
    "Срок поставки A меняется с 45 на 70 календарных дней. "
    "Быстрее ли A, чем B (60 дней)? Нет, 70 дней больше 60 дней."
)
FINDING = {
    "code": "EDITORIAL_AWKWARD_PHRASING", "severity": "non_blocking", "requirement_ref": CLARITY,
    "reason": "Риторический вопрос усложняет чтение, хотя единица и смысл ясны.",
}
PASS_REASON = "Текст сразу отвечает на вопрос и однозначно сообщает, что 70 календарных дней больше 60."
WARNING_REASON = "Вопрос и следующий за ним ответ однозначны, но редакционно избыточны."


class ClarifyingGateway(V04Gateway):
    def __init__(self, role="tester", outcome="pass", *, blocker=False, attempts=2, wait=0):
        super().__init__()
        self.role = role
        self.outcome = outcome
        self.blocker = blocker
        self.attempts = attempts
        self.wait = wait
        self.budgets = {}
        self.dispatched_budgets = {}
        self.responses = {}

    def operation_budget(self, operation_id):
        assert operation_id not in self.budgets
        budget = OperationBudget(self.attempts, 60)
        self.budgets[operation_id] = budget
        return budget

    def chat_with_trace(self, messages, **kwargs):
        route = kwargs["routing_key"]
        budget = kwargs["operation_budget"]
        self.dispatched_budgets[route] = budget
        budget.reserve()
        if route.endswith(CLARIFICATION_SUFFIX):
            payload = json.loads(messages[-1]["content"])
            self.calls.append((route, deepcopy(messages), payload))
            row = deepcopy(payload["previous_rows"][0]["original_row"])
            if self.outcome == "pass":
                row.update(status="PASS", findings=[], reason=PASS_REASON)
            elif self.outcome == "warning":
                row.update(status="FAIL", reason=WARNING_REASON)
            elif self.outcome == "json":
                return SimpleNamespace(content="{", sent={"messages": messages}, provider={})
            token = payload["clarification_id"]
            if self.outcome in {"foreign-role", "foreign-candidate", "foreign-round"}:
                first_route = route.removesuffix(CLARIFICATION_SUFFIX)
                first_payload = next(body for key, _, body in self.calls if key == first_route)
                dispatch = deepcopy(first_payload["review_dispatch"])
                dispatch.update({
                    "candidate_sha256": checksum(first_payload["candidate_as"]),
                    "package": first_payload["review_package"],
                    "request_id": first_route, "request_sha256": checksum(next(
                        sent for key, sent, _ in self.calls if key == first_route
                    )), "attempt": 1,
                })
                key, value = {"foreign-role": ("reviewer", "challenger"),
                              "foreign-candidate": ("candidate_sha256", "0" * 64),
                              "foreign-round": ("round", 2)}[self.outcome]
                dispatch[key] = value
                # Keep the initial response fingerprint and change only the tested dispatch field.
                token = checksum({"dispatch": dispatch, "response_sha256": checksum(self.responses[first_route].encode()),
                                  "check_ids": [CLARITY]})
                row.update(status="PASS", findings=[], reason=PASS_REASON)
            sleep(self.wait)
            return SimpleNamespace(content=json.dumps({"clarification_id": token, "checks": [row]}, ensure_ascii=False),
                                   sent={"messages": messages}, provider={})
        if self.outcome == "budget-json" and f":{self.role}:01:" in route and not route.endswith(":json-retry"):
            self.calls.append((route, deepcopy(messages), json.loads(messages[-1]["content"])))
            return SimpleNamespace(content="{", sent={"messages": messages}, provider={})
        retry = route.endswith(":json-retry")
        response = super().chat_with_trace(messages[:-1] if retry else messages, **kwargs)
        _, _, payload = self.calls[-1]
        if retry:
            self.calls[-1] = (route, deepcopy(messages), payload)
            response.sent["messages"] = messages
        if ":generation:" in route:
            candidate = json.loads(response.content)
            case_id = payload["case"]["CaseID"]
            candidate["AssessmentSituationID"] = str(uuid5(NAMESPACE_URL, "task10:" + case_id))
            if case_id == "CASE.SPEC.02":
                material = next(row for row in candidate["Материалы"] if row["MaterialID"] == "M03")
                material["Текст"] = MATERIAL_TEXT
            response.content = json.dumps(candidate, ensure_ascii=False)
        self.responses[route] = response.content
        return response

    def review_response(self, routing, payload, checks):
        role = payload["review_dispatch"]["reviewer"]
        candidate = payload["candidate_as"]
        for row in checks:
            if role == self.role and row["check_id"] == CLARITY:
                path = row["evidence_paths"][0]
                if payload["case"]["CaseID"] == "CASE.SPEC.02":
                    index = next(i for i, material in enumerate(candidate["Материалы"]) if material["MaterialID"] == "M03")
                    path = f"/candidate_as/Материалы/{index}/Текст"
                row.update(status="PASS", reason=WARNING_REASON, evidence_paths=[path],
                           findings=[{**FINDING, "paths": [path]}])
            if self.blocker and role == "tester" and row["check_id"] == AUTHORITY:
                row.update(status="FAIL", reason="Синтетический подтверждённый блокер полномочий.", findings=[{
                    "code": "AUTHORITY_BLOCKER", "severity": "blocking", "requirement_ref": AUTHORITY,
                    "reason": "Ролевой мандат в этой ситуации отсутствует.", "paths": row["evidence_paths"],
                }])
        return super().review_response(routing, payload, checks)


@pytest.fixture
def fixed_spec02(pilot_cases):
    cases, bank = pilot_cases
    return build_passport_snapshot(
        case_version=cases[2], operation_id="task10-fixed-spec02", synthetic=True, battery_pilot=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        review_response_package=ROOT / M5_REVIEW_RESPONSE_PACKAGE,
        battery_scenario_package=ROOT / BATTERY_V04_SCENARIO_CURRENT,
        package_ref={"id": bank["id"], "version": bank["version"]},
        profile={"user_context": {"regular_tasks": ["Сверяю рабочие предложения."]}},
    )


def _no_contract(snapshot):
    older = deepcopy(snapshot)
    older["refs"].pop("review_response")
    return older


@pytest.mark.parametrize(("role", "outcome", "terminal"), [
    ("tester", "pass", "PASS"), ("challenger", "warning", "PASS_WITH_WARNINGS"),
])
def test_only_affected_rows_are_clarified(fixed_spec02, role, outcome, terminal):
    previous = prepare(_no_contract(fixed_spec02), ClarifyingGateway(role, outcome))
    assert previous["tester"]["aggregation"]["status"] == "INCOMPLETE"
    gateway = ClarifyingGateway(role, outcome, wait=0.008)
    result = prepare(fixed_spec02, gateway)
    assert result["tester"]["aggregation"]["status"] == terminal
    assert result["candidate_checksum"] == previous["candidate_checksum"]
    assert result["repair"] is None
    assert len([key for key, _, _ in gateway.calls if ":generation:" in key]) == 1
    other = "tester" if role == "challenger" else "challenger"
    tester = result["tester"]
    batch = tester[ROLE_TRACE[role]]["batches"][0]
    first, second = batch["calls"]
    assert sum(len(row["calls"]) for row in tester[ROLE_TRACE[role]]["batches"]) == 4
    assert sum(len(row["calls"]) for row in tester[ROLE_TRACE[other]]["batches"]) == 3
    assert first["review_dispatch"]["candidate_sha256"] == second["review_dispatch"]["candidate_sha256"] == result["candidate_checksum"]
    assert second["review_dispatch"]["check_ids"] == [CLARITY]
    assert second["elapsed_ms"] >= 8
    assert gateway.dispatched_budgets[batch["operation_id"]] is gateway.dispatched_budgets[batch["operation_id"] + CLARIFICATION_SUFFIX]
    request = next(body for path, _, body in gateway.calls if path.endswith(CLARIFICATION_SUFFIX))
    original = next(row for row in json.loads(first["response_content"])["checks"] if row["check_id"] == CLARITY)
    assert request["previous_rows"][0]["original_row"] == original and original["status"] == "PASS"
    assert request["previous_rows"][0]["related_materials"][original["evidence_paths"][0]] == MATERIAL_TEXT
    assert request["previous_rows"][0]["protocol_errors"][0]["code"] == "STATUS_FINDINGS_CONFLICT"
    assert batch["clarification"]["accepted_check_ids"] == [CLARITY]
    for name in ROLE_TRACE:
        before_rows, after_rows = (value["tester"]["independent_checks"][name] for value in (previous, result))
        assert [{k: v for k, v in row.items() if k != "operation_id"} for row in before_rows if row["check_id"] != CLARITY or name != role] == [
            {k: v for k, v in row.items() if k != "operation_id"} for row in after_rows if row["check_id"] != CLARITY or name != role
        ]
    trace = json.loads(json.dumps(build_persistence_trace(fixed_spec02, result), sort_keys=True))
    functional_gate(trace, operation_id=fixed_spec02["operation_id"])
    functional_gate(trace, operation_id=fixed_spec02["operation_id"])
    assert [warning["check_id"] for warning in tester["aggregation"]["warnings"]] == ([] if outcome == "pass" else [CLARITY])


@pytest.mark.parametrize("outcome", ["repeat", "json", "foreign-role", "foreign-candidate", "foreign-round", "budget-json"])
def test_bad_clarification_remains_incomplete(fixed_spec02, outcome):
    gateway = ClarifyingGateway("tester", outcome)
    result = prepare(fixed_spec02, gateway)
    batch = result["tester"]["provider_operation"]["batches"][0]
    assert result["tester"]["aggregation"]["status"] == "INCOMPLETE"
    assert result["repair"] is None
    assert len(batch["calls"]) == 2
    assert [error["code"] for error in result["tester"]["aggregation"]["verification_errors"]] == ["STATUS_FINDINGS_CONFLICT"]
    if outcome == "budget-json":
        assert "clarification" not in batch and batch["parse_failures"][0]["attempt"] == 1
        assert gateway.calls[2][0].endswith(":json-retry")
    else:
        assert batch["clarification"]["accepted_check_ids"] == []


def test_confirmed_blocker_still_uses_addressed_candidate_repair(fixed_spec02):
    gateway = ClarifyingGateway("challenger", "repeat", blocker=True)
    result = prepare(fixed_spec02, gateway)
    assert result["tester"]["aggregation"]["status"] == "FAIL"
    assert result["repair"]["outcome"] == "UNCHANGED_CANDIDATE"
    repair = next(body for path, _, body in gateway.calls if ":generation:repair:" in path)
    assert [row["check_id"] for row in repair["blocking_failures"]] == [AUTHORITY]
    assert repair["rejected_candidate_checksum"] == result["candidate_checksum"]


def test_exhausted_transport_keeps_the_initial_conflict(fixed_spec02):
    result = prepare(fixed_spec02, ClarifyingGateway("tester", "pass", attempts=1))
    assert result["tester"]["aggregation"]["status"] == "INCOMPLETE"
    batch = result["tester"]["provider_operation"]["batches"][0]
    assert len(batch["calls"]) == 1
    assert batch["clarification"]["error"] == "REVIEW_CLARIFICATION_UNAVAILABLE"


@pytest.mark.parametrize("field", ["reviewer", "candidate_sha256", "round", "response"])
def test_m7_replays_both_receipts(fixed_spec02, field):
    trace = build_persistence_trace(fixed_spec02, prepare(fixed_spec02, ClarifyingGateway()))
    first, second = trace["tester"]["provider_operation"]["batches"][0]["calls"]
    if field == "response":
        first["response_content"] += " "
    else:
        second["review_dispatch"][field] = "foreign"
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_DISPATCH_MISMATCH"):
        functional_gate(trace, operation_id=fixed_spec02["operation_id"])


def test_both_roles_receive_explicit_response_forms_on_one_call_per_batch(fixed_spec02):
    previous_gateway = ClarifyingGateway(role=None)
    current_gateway = ClarifyingGateway(role=None)
    old = _no_contract(fixed_spec02)
    previous = build_persistence_trace(old, prepare(old, previous_gateway))
    current = build_persistence_trace(fixed_spec02, prepare(fixed_spec02, current_gateway))
    operation_id = fixed_spec02["operation_id"]
    assert len(previous_gateway.calls) == len(current_gateway.calls) == 7
    assert previous["candidate_checksum"] == current["candidate_checksum"]
    for role in ROLE_TRACE:
        _, old_sent, old_payload = next(entry for entry in previous_gateway.calls if f":{role}:" in entry[0])
        _, sent, payload = next(entry for entry in current_gateway.calls if f":{role}:" in entry[0])
        assert old_payload["required_output"]["checks"][0]["findings"]
        assert len(sent) == len(old_sent) + 1
        assert "findings" not in payload["required_output"]["checks"][0]
        forms = payload["required_output"]["findings_by_status"]
        assert set(forms) == {"FAIL", "PASS|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR"}
        assert forms["FAIL"][0]["severity"] == "blocking|non_blocking" and not forms["PASS|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR"]
        assert '"status":"PASS"' in sent[-2]["content"] and '"severity":"non_blocking"' in sent[-2]["content"]
    functional_gate(previous, operation_id=operation_id)
    functional_gate(current, operation_id=operation_id)

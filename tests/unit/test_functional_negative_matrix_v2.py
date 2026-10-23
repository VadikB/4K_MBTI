import copy
import json
from types import SimpleNamespace

from scripts import run_functional_negative_matrix_v2 as runner


class BlindGateway:
    enabled = True

    def __init__(self):
        self.tester_payloads = []

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        if ":mutation:" in kwargs["routing_key"]:
            candidate = copy.deepcopy(payload["assessment_situation"])
            candidate.pop("Предыдущая версия AS")
            content = json.dumps(candidate, ensure_ascii=False)
        else:
            self.tester_payloads.append(payload)
            required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            content = json.dumps({"checks": [{
                "check_id": item["check_id"], "status": "PASS", "reason": "blind fixture",
                "evidence_paths": [], "findings": [],
                "adversarial_review": {"candidate_conflicts": [], "resolution": "no conflict"},
            } for item in required]}, ensure_ascii=False)
        return SimpleNamespace(content=content, sent={"parameters": kwargs},
                               provider={"finish_reason": "stop", "request_id": kwargs["routing_key"]})


def test_full_negative_as_is_rejected_without_leaking_expected_diagnosis_to_tester():
    row = runner.read_json(runner.NEGATIVES)[0]
    position = next(item for item in runner.read_json(runner.FINAL)["positions"]
                    if item["case_ref"]["case_id"] == row["CaseID"])
    gateway = BlindGateway()

    result = runner.run_one(row, position, gateway)

    assert result["result"] == "PASS"
    assert result["acceptance"] == {"positive_admitted": True, "mutated_as_rejected": True}
    assert len(gateway.tester_payloads) == 4
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()), set())
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()
    # The Case legitimately contains its invariants and the mutated AS contains
    # the requested defect. What must not cross the blind boundary is the QA row
    # that maps this mutation to a known diagnosis and expected verdict.
    assert not ({"NegativeID", "negative_id", "Нарушенный инвариант", "Почему отклонить",
                 "Ожидаемый результат валидатора", "expected_violated_invariant"}
                & keys(gateway.tester_payloads))

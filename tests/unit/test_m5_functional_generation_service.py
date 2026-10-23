import json
from types import SimpleNamespace

from Api import m5_functional_generation_service as service


class Gateway:
    enabled = True
    def __init__(self): self.profiles = []
    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        if ":generation:" in kwargs["routing_key"]:
            self.profiles.append(payload["profile"])
            content = json.dumps(payload["author_as_example"], ensure_ascii=False)
        else:
            checks = [{"check_id": item["check_id"], "status": "PASS", "reason": "fixture", "findings": []}
                      for item in payload["applicability_plan"]["required_checks"]]
            content = json.dumps({"checks": checks}, ensure_ascii=False)
        return SimpleNamespace(content=content, sent={"parameters": kwargs},
                               provider={"finish_reason": "stop", "request_id": kwargs["routing_key"]})


def profile(task):
    return {"status": "ready", "base_role": "specialist_expert",
            "organization_context": {"operating_context": "test"},
            "role_profile": {"position_or_status": task, "responsibility_object": task, "authority": "analyse"},
            "user_context": {"regular_tasks": task, "decision_situations": task,
                             "constraints_and_interactions": "coordinate"}}


def test_shared_service_admits_only_after_deterministic_and_independent_checks():
    gateway = Gateway()
    first = service.build_input_snapshot(case_id="CASE.SPEC.01", profile=profile("credit risk"), operation_id="op-1")
    second = service.build_input_snapshot(case_id="CASE.SPEC.01", profile=profile("warehouse supply"), operation_id="op-2")
    result_a, result_b = service.prepare(first, gateway), service.prepare(second, gateway)
    assert result_a["admitted_for_participant"] is True
    assert result_b["admitted_for_participant"] is True
    assert result_a["input_snapshot_checksum"] != result_b["input_snapshot_checksum"]
    assert gateway.profiles[0]["user_context"]["regular_tasks"] != gateway.profiles[1]["user_context"]["regular_tasks"]
    assert result_a["tester"]["aggregation"]["status"] == "PASS"


def test_shared_service_closes_admission_when_tester_omits_required_checks():
    class EmptyTester(Gateway):
        def chat_with_trace(self, messages, **kwargs):
            if ":tester:" in kwargs["routing_key"]:
                return SimpleNamespace(content='{"checks":[]}', sent={}, provider={"finish_reason":"stop"})
            return super().chat_with_trace(messages, **kwargs)
    snapshot = service.build_input_snapshot(case_id="CASE.SPEC.01", profile=profile("risk"), operation_id="op-x")
    result = service.prepare(snapshot, EmptyTester())
    assert result["admitted_for_participant"] is False
    assert result["tester"]["aggregation"]["status"] == "INCOMPLETE"

import json
from types import SimpleNamespace

from Api import m5_functional_generation_service as service


class Gateway:
    enabled = True
    def __init__(self): self.profiles = []; self.generation_requirements = []; self.tester_payloads = []
    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        if ":generation:" in kwargs["routing_key"]:
            self.profiles.append(payload["profile"])
            self.generation_requirements.append(payload["requirements"])
            content = json.dumps(payload["author_as_example"], ensure_ascii=False)
        else:
            self.tester_payloads.append(payload)
            required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            checks = [{"check_id": item["check_id"], "status": "PASS", "reason": "fixture", "findings": [],
                       "adversarial_review": {"candidate_conflicts": [], "resolution": "no conflict"}}
                      for item in required]
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
    assert "Предыдущая версия AS" in gateway.generation_requirements[0]["required_top_level_fields_exact"]
    assert gateway.generation_requirements[0]["omit_empty_required_fields"] is False
    assert result_a["tester"]["aggregation"]["status"] == "PASS"
    assert gateway.tester_payloads[0]["required_output"]["checks"][0]["check_id"].startswith("exact id")
    assert result_a["compiled_case"]["author_assessment_situation"] == result_a["candidate_as"]
    assert result_a["compiled_case"]["author_as_source"]["sha256"] == result_a["candidate_checksum"]
    assert set(result_a["execution_rules"]["cases"]) == {"CASE.SPEC.01"}


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
    assert result["compiled_case"] is None and result["execution_rules"] is None


def test_malformed_provider_json_is_retried_once_without_salvaging_fragments():
    class MalformedOnce(Gateway):
        def __init__(self): super().__init__(); self.calls = 0
        def chat_with_trace(self, messages, **kwargs):
            self.calls += 1
            response = super().chat_with_trace(messages, **kwargs)
            if self.calls == 1: response.content += '{"second":"object"}'
            return response
    gateway = MalformedOnce()
    snapshot = service.build_input_snapshot(case_id="CASE.SPEC.01", profile=profile("risk"), operation_id="op-r")
    result = service.prepare(snapshot, gateway)
    assert result["admitted_for_participant"] is True
    assert result["generation_operation"]["parse_failures"][0]["code"] == "PROVIDER_JSON_INVALID"
    assert gateway.calls == 4  # generation failure + generation retry + tester + challenger


def test_blocking_tester_failure_triggers_one_full_repair_and_retest():
    class RepairingGateway(Gateway):
        def __init__(self): super().__init__(); self.tester_calls = 0
        def chat_with_trace(self, messages, **kwargs):
            if ":tester:" in kwargs["routing_key"]:
                self.tester_calls += 1
                if self.tester_calls == 1:
                    payload = json.loads(next(x["content"] for x in reversed(messages) if x["role"] == "user"))
                    required = payload["applicability_plan"]["required_checks"]
                    checks = []
                    for item in required:
                        failed = item["check_id"] == "common.professional_consistency"
                        checks.append({"check_id": item["check_id"], "status": "FAIL" if failed else "PASS",
                            "reason": "fixture blocking mismatch" if failed else "fixture pass",
                            "findings": ([{"code": "ROLE_MISMATCH", "severity": "blocking",
                                "paths": ["candidate_as.role"], "reason": "fixture",
                                "requirement_ref": item["check_id"]}] if failed else []),
                            "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"}})
                    return SimpleNamespace(content=json.dumps({"checks": checks}), sent={},
                                           provider={"finish_reason": "stop"})
            return super().chat_with_trace(messages, **kwargs)

    snapshot = service.build_input_snapshot(case_id="CASE.SPEC.01", profile=profile("risk"), operation_id="op-repair")
    result = service.prepare(snapshot, RepairingGateway())
    assert result["admitted_for_participant"] is True
    assert result["repair"]["original_tester"]["aggregation"]["status"] == "FAIL"
    assert result["repair"]["repair_generation_operation"]["kind"] == "generation_repair"
    assert result["repair"]["repair_generation_operation"]["prompt_ref"] == {
        "id": "m5_functional_repair", "version": "1.0.0",
        "checksum": "d0b424cbff9000dfd3aa55341f89c63f20964c254a0077dc65cf95d90c77ccf0",
    }
    assert result["tester"]["aggregation"]["status"] == "PASS"

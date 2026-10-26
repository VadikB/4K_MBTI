import json
from copy import deepcopy
from types import SimpleNamespace

from Api import m5_functional_generation_service as service


def add_adaptation_mappings(candidate, author):
    material_ids = [item["MaterialID"] for item in candidate["Материалы"]]
    event_ids = [item["EventID"] for item in candidate["События"]]
    character_ids = [item["CharacterID"] for item in candidate["Активные персонажи"]]
    for index, target in enumerate(candidate["IndicatorObservability"]):
        target.update({
            "material_refs": material_ids[:1],
            "event_refs": event_ids[:1],
            "character_refs": character_ids[:1],
            "authority_refs": ["participant"],
            "author_mapping": {
                "source_pointer": f"/IndicatorObservability/{index}",
                "source_checksum": service.checksum(author["IndicatorObservability"][index]),
            },
        })
    return candidate


class Gateway:
    enabled = True
    def __init__(self): self.profiles = []; self.generation_requirements = []; self.tester_payloads = []
    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        if ":generation:" in kwargs["routing_key"]:
            self.profiles.append(payload["profile"])
            self.generation_requirements.append(payload["requirements"])
            candidate = deepcopy(payload["author_as_example"])
            add_adaptation_mappings(candidate, payload["author_as_example"])
            content = json.dumps(candidate, ensure_ascii=False)
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
    assert first["refs"]["package"] == {
        "id": "m5-functional-personalization-cases",
        "version": "0.4",
        "compiler": {
            "id": "m5-functional-json-compiler",
            "version": "0.4.0",
            "source_schema_profile": "functional-personalization-indicator-v2",
            "indicator_layer_contract": "m5-functional-indicator-two-layer/1.0.0",
        },
    }
    assert gateway.profiles[0]["user_context"]["regular_tasks"] != gateway.profiles[1]["user_context"]["regular_tasks"]
    assert "Предыдущая версия AS" in gateway.generation_requirements[0]["required_top_level_fields_exact"]
    assert gateway.generation_requirements[0]["omit_empty_required_fields"] is False
    assert result_a["tester"]["aggregation"]["status"] == "PASS"
    assert gateway.tester_payloads[0]["required_output"]["checks"][0]["check_id"].startswith("exact id")
    assert result_a["compiled_case"]["author_assessment_situation"] == result_a["candidate_as"]
    assert result_a["compiled_case"]["author_as_source"]["sha256"] == result_a["candidate_checksum"]
    assert set(result_a["execution_rules"]["cases"]) == {"CASE.SPEC.01"}


def test_provider_cannot_overwrite_frozen_author_indicator_content():
    changed_fields = {
        "K1.I01": ("Конкретное условие", "Что сохранить при адаптации", "Дефект потери"),
        "K1.I13": ("Конкретное условие", "Что сохранить при адаптации"),
        "K1.I14": ("Конкретное условие", "Что сохранить при адаптации", "Дефект потери"),
        "K4.I06": ("Дефект потери",),
    }

    class PilotMutationGateway(Gateway):
        def chat_with_trace(self, messages, **kwargs):
            payload = json.loads(next(item["content"] for item in reversed(messages)
                                      if item["role"] == "user"))
            if ":generation:" in kwargs["routing_key"]:
                candidate = deepcopy(payload["author_as_example"])
                for target in candidate["IndicatorObservability"]:
                    for field in changed_fields.get(target["IndicatorID"], ()):
                        target[field] = "LLM_CHANGED_AUTHOR_CONTENT"
                add_adaptation_mappings(candidate, payload["author_as_example"])
                return SimpleNamespace(content=json.dumps(candidate, ensure_ascii=False), sent={},
                                       provider={"finish_reason": "stop"})
            return super().chat_with_trace(messages, **kwargs)

    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("sales"), operation_id="a06-pilot-regression",
    )
    result = service.prepare(snapshot, PilotMutationGateway())

    expected = {item["IndicatorID"]: item
                for item in snapshot["author_as_example"]["IndicatorObservability"]}
    actual = {item["IndicatorID"]: item for item in result["candidate_as"]["IndicatorObservability"]}
    adapted = {item["IndicatorID"]: item
               for item in result["candidate_as"]["IndicatorTargetLayers"]["adapted"]["targets"]}
    assert result["admitted_for_participant"] is True
    assert result["repair"] is None
    assert result["generation_operation"]["kind"] == "generation"
    assert result["deterministic_validation"]["status"] == "PASS"
    assert result["author_content_binding"]["changed"] is True
    assert (result["author_content_binding"]["provider_candidate_checksum"]
            != result["candidate_checksum"])
    for indicator_id, fields in changed_fields.items():
        for field in fields:
            assert actual[indicator_id][field] == expected[indicator_id][field]
            assert adapted[indicator_id][field] == "LLM_CHANGED_AUTHOR_CONTENT"


def test_author_binding_does_not_recreate_missing_indicator_target():
    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("sales"), operation_id="a06-missing-target",
    )
    candidate = deepcopy(snapshot["author_as_example"])
    candidate["IndicatorObservability"].pop()

    bound = service.bind_frozen_author_indicator_content(snapshot, candidate)
    validation = service.deterministic_checks(snapshot, bound)

    assert len(bound["IndicatorObservability"]) == len(snapshot["author_as_example"]["IndicatorObservability"])
    assert len(bound["IndicatorTargetLayers"]["adapted"]["targets"]) == len(candidate["IndicatorObservability"])
    assert validation["status"] == "FAIL"
    assert next(item for item in validation["checks"]
                if item["code"] == "indicator_adapted_target_set")["result"] == "FAIL"


def test_two_layer_contract_accepts_valid_adaptation_and_compiles_it():
    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("sales"), operation_id="two-layer-positive",
    )
    result = service.prepare(snapshot, Gateway())

    layers = result["candidate_as"]["IndicatorTargetLayers"]
    assert result["admitted_for_participant"] is True
    assert layers["author"]["targets"] == snapshot["author_as_example"]["IndicatorObservability"]
    assert layers["author"]["checksum"] == service.checksum(layers["author"]["targets"])
    assert layers["adapted"]["checksum"] == service.checksum(layers["adapted"]["targets"])
    compiled = {item["indicator_id"]: item for item in result["compiled_case"]["indicator_targets"]}
    adapted = {item["IndicatorID"]: item for item in layers["adapted"]["targets"]}
    assert compiled["K1.I01"]["observation_condition"] == adapted["K1.I01"]["Конкретное условие"]
    assert compiled["K1.I01"]["author_basis"]["target_checksum"] == service.checksum(
        layers["author"]["targets"][0]
    )


def test_two_layer_contract_rejects_lost_condition_bad_reference_and_authority():
    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("sales"), operation_id="two-layer-negative",
    )
    gateway = Gateway()
    generated = service.generate(snapshot, gateway)
    targets = generated["candidate_as"]["IndicatorTargetLayers"]["adapted"]["targets"]
    targets[0]["Конкретное условие"] = ""
    targets[1]["material_refs"] = ["UNKNOWN_MATERIAL"]
    targets[2]["authority_refs"] = ["character:UNKNOWN"]
    generated["candidate_as"]["IndicatorTargetLayers"]["adapted"]["checksum"] = service.checksum(targets)

    validation = service.deterministic_checks(snapshot, generated["candidate_as"])

    failure = next(item for item in validation["checks"]
                   if item["code"] == "indicator_adaptation_references")
    assert validation["status"] == "FAIL"
    assert failure["result"] == "FAIL"
    assert failure["actual"][0]["empty_condition"] is True
    assert failure["actual"][1]["material_refs"] == ["UNKNOWN_MATERIAL"]
    assert failure["actual"][2]["authority_refs"] == ["character:UNKNOWN"]


def test_two_layer_contract_rejects_semantic_substitution_from_independent_tester():
    class SemanticSubstitutionGateway(Gateway):
        def chat_with_trace(self, messages, **kwargs):
            if ":tester:" in kwargs["routing_key"]:
                payload = json.loads(next(item["content"] for item in reversed(messages)
                                          if item["role"] == "user"))
                checks = []
                for item in payload["applicability_plan"]["required_checks"]:
                    failed = item["check_id"].startswith("indicator:")
                    checks.append({
                        "check_id": item["check_id"], "status": "FAIL" if failed else "PASS",
                        "reason": "meaning substituted" if failed else "fixture",
                        "findings": ([{"code": "ADAPTATION_MEANING_SUBSTITUTED", "severity": "blocking",
                                      "paths": ["candidate_as.IndicatorTargetLayers.adapted"],
                                      "reason": "существенное условие подменено",
                                      "requirement_ref": item["check_id"]}] if failed else []),
                        "adversarial_review": {"candidate_conflicts": [], "resolution": "checked"},
                    })
                return SimpleNamespace(content=json.dumps({"checks": checks}), sent={},
                                       provider={"finish_reason": "stop"})
            return super().chat_with_trace(messages, **kwargs)

    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("sales"), operation_id="two-layer-semantic",
    )
    generation = service.generate(snapshot, SemanticSubstitutionGateway())
    tested = service.test_candidate(snapshot, generation, SemanticSubstitutionGateway())
    assert tested["aggregation"]["status"] == "FAIL"
    assert tested["aggregation"]["admitted_for_participant"] is False


def test_frozen_package_03_snapshot_keeps_legacy_handoff_contract():
    class LegacyGateway(Gateway):
        def chat_with_trace(self, messages, **kwargs):
            payload = json.loads(next(item["content"] for item in reversed(messages)
                                      if item["role"] == "user"))
            if ":generation:" in kwargs["routing_key"]:
                return SimpleNamespace(
                    content=json.dumps(payload["author_as_example"], ensure_ascii=False),
                    sent={}, provider={"finish_reason": "stop"},
                )
            return super().chat_with_trace(messages, **kwargs)

    package_03 = service.ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.3"
    snapshot = service.build_input_snapshot(
        case_id="CASE.SPEC.01", profile=profile("legacy"), operation_id="legacy-03",
        source_root=package_03 / "sources/functional-v0.2",
    )
    prepared = service.prepare(snapshot, LegacyGateway())
    trace = service.build_persistence_trace(snapshot, prepared)

    assert prepared["admitted_for_participant"] is True
    assert "IndicatorTargetLayers" not in prepared["candidate_as"]
    assert trace["schema_version"] == 2
    assert "indicator_target_layers_checksum" not in trace


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

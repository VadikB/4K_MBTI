import json
from pathlib import Path

import pytest

from Api.m8_descriptive_report import build_input, generate, load_package
from test_m8_recommendations import fixture


class Gateway:
    enabled = True

    def __init__(self, output):
        self.output = output
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        value = json.loads(messages[1]["content"])
        if "candidate" in value:
            candidate = value["candidate"]
            return json.dumps({
                "status": "accepted",
                "claim_decisions": [
                    {"index": index, "decision": "supported", "reason_code": "SUPPORTED_FIXTURE"}
                    for index, _ in enumerate(candidate["claims"])
                ],
                "summary_decisions": [
                    {"index": index, "decision": "supported", "reason_code": "SUPPORTED_FIXTURE"}
                    for index, _ in enumerate(candidate["summary"])
                ],
            }, ensure_ascii=False)
        return json.dumps(self.output, ensure_ascii=False)


def inputs():
    payload, resolved = fixture()
    results = {
        "id": "results-1",
        "revision_id": payload.pop("results_revision_id"),
        "revision_no": 1,
        "cycle_id": payload["cycle_id"],
        "results": {
            **payload,
            "personalized_profile_snapshot": {
                "content": {
                    "user_context": {
                        "regular_tasks": ["Согласование сроков"],
                        "email": "private@example.invalid",
                    }
                }
            },
            "limitations": ["Проверка гипотез не наблюдалась."],
            "partial_result": None,
        },
    }
    return results, resolved


def valid_output():
    return {
        "summary": ["Вывод основан на явно названной цели."],
        "claims": [
            {
                "kind": "explanation",
                "skill_ids": ["K1.1"],
                "basis_refs": ["ia-1"],
                "text": "Вывод основан на явно названной цели.",
                "limitations": ["Проверка гипотез не наблюдалась."],
                "context_refs": ["user_context.regular_tasks"],
            },
            {
                "kind": "quote",
                "skill_ids": ["K1.1"],
                "basis_refs": ["ia-1"],
                "text": "Хочет согласовать срок",
                "limitations": [],
                "context_refs": [],
            },
        ],
    }


def test_package_and_grounded_description_are_versioned_and_pii_free():
    results, resolved = inputs()
    gateway = Gateway(valid_output())
    report = generate(results, resolved, gateway=gateway)

    assert load_package()["manifest"]["version"] == "1.2.0"
    assert report["status"] == "ready"
    assert report["claims"][1]["text"] == "Хочет согласовать срок"
    assert "private@example.invalid" not in str(report)
    assert gateway.calls[0][1]["temperature"] == 0
    assert gateway.calls[0][1]["response_format"] == {"type": "json_object"}
    assert gateway.calls[1][1]["routing_key"] == "m8-description-validation:r1"


def test_v1_package_keeps_frozen_single_pass_behavior():
    results, resolved = inputs()
    gateway = Gateway(valid_output())
    package = Path(__file__).resolve().parents[2] / "assessment_definitions/prompts/m8_descriptive_report/v1"

    report = generate(results, resolved, gateway=gateway, package_path=package)

    assert report["status"] == "ready"
    assert report["contract_version"] == "m8-descriptive-report/1.1.0"
    assert len(gateway.calls) == 1


class RejectingSemanticGateway(Gateway):
    def __init__(self, output, reason_code="OPPOSITE_MEANING"):
        super().__init__(output)
        self.reason_code = reason_code

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        value = json.loads(messages[1]["content"])
        if "candidate" not in value:
            return json.dumps(self.output, ensure_ascii=False)
        candidate = value["candidate"]
        return json.dumps({
            "status": "rejected",
            "claim_decisions": [
                {"index": index, "decision": "contradicted" if index == 0 else "supported",
                 "reason_code": self.reason_code if index == 0 else "SUPPORTED_QUOTE"}
                for index, _ in enumerate(candidate["claims"])
            ],
            "summary_decisions": [
                {"index": index, "decision": "contradicted", "reason_code": self.reason_code}
                for index, _ in enumerate(candidate["summary"])
            ],
        }, ensure_ascii=False)


@pytest.mark.parametrize("reason_code", [
    "OPPOSITE_MEANING",
    "UNSUPPORTED_GENERALIZATION",
    "UNSUPPORTED_CAUSALITY",
    "WRONG_CONTEXT",
    "INSUFFICIENT_EVIDENCE",
])
def test_semantically_invalid_description_is_rejected_and_not_exposed_as_ready(reason_code):
    results, resolved = inputs()
    opposite = valid_output()
    opposite["summary"] = ["Участник не обозначил цель коммуникации."]
    opposite["claims"][0]["text"] = "Участник не обозначил цель коммуникации."
    report = generate(results, resolved, gateway=RejectingSemanticGateway(opposite, reason_code))

    assert report["status"] == "failed"
    assert report["failure_reason"] == "DESCRIPTION_SEMANTIC_REJECTED"
    assert report["summary"] == [] and report["claims"] == []
    assert report["semantic_validation"]["claim_decisions"][0]["reason_code"] == reason_code


def test_input_uses_only_selected_frozen_context():
    results, resolved = inputs()
    model_input, allowed = build_input(results, resolved)

    assert model_input["context"] == [
        {"ref": "user_context.regular_tasks", "text": "Согласование сроков"}
    ]
    assert allowed["quotes"] == {"Хочет согласовать срок": {("ia-1", "K1.1")}}
    assert "email" not in str(model_input)


def test_no_interpretable_basis_returns_empty_ready_description_without_provider_call():
    results, resolved = inputs()
    resolved["projections"] = []
    gateway = Gateway({"summary": ["must not be used"], "claims": []})
    report = generate(results, resolved, gateway=gateway)
    assert report["status"] == "ready"
    assert report["summary"] == [] and report["claims"] == []
    assert gateway.calls == []


def test_forbidden_advice_and_unverified_references_fail_closed():
    results, resolved = inputs()
    cases = []
    advice = valid_output()
    advice["claims"][0]["text"] = "Вам следует попробовать упражнение."
    cases.append(advice)
    foreign_basis = valid_output()
    foreign_basis["claims"][0]["basis_refs"] = ["foreign"]
    cases.append(foreign_basis)
    changed_quote = valid_output()
    changed_quote["claims"][1]["text"] = "Изменённая цитата"
    cases.append(changed_quote)
    foreign_context = valid_output()
    foreign_context["claims"][0]["context_refs"] = ["user_context.email"]
    cases.append(foreign_context)
    invented_limitation = valid_output()
    invented_limitation["claims"][0]["limitations"] = ["Выдуманное ограничение."]
    cases.append(invented_limitation)
    empty_basis = valid_output()
    empty_basis["claims"][0]["basis_refs"] = []
    cases.append(empty_basis)
    ungrounded_summary = valid_output()
    ungrounded_summary["summary"] = ["Новый вывод без проверенного утверждения."]
    cases.append(ungrounded_summary)

    for output in cases:
        report = generate(results, resolved, gateway=Gateway(output))
        assert report["status"] == "failed"
        assert report["claims"] == []
        assert report["failure_reason"] == "DESCRIPTION_GENERATION_FAILED"


def test_basis_and_quote_must_belong_to_the_claimed_skill():
    results, resolved = inputs()
    other = dict(resolved["projections"][0])
    other["revision_id"] = "ia-2"
    other["criterion"] = {**other["criterion"], "skill_id": "K1.2"}
    other["target"] = {**other["target"], "indicator_id": "K1.2.I1"}
    other["traces"] = [{"fragments": [{"id": "f-2", "quote": "Другая цитата"}]}]
    resolved["projections"].append(other)
    results["results"]["assessed_skill_profile"].append({
        **results["results"]["assessed_skill_profile"][0],
        "skill_id": "K1.2",
    })

    foreign_skill_basis = valid_output()
    foreign_skill_basis["claims"][0]["basis_refs"] = ["ia-2"]
    changed_owner = valid_output()
    changed_owner["claims"][1]["basis_refs"] = ["ia-2"]
    for output in (foreign_skill_basis, changed_owner):
        report = generate(results, resolved, gateway=Gateway(output))
        assert report["status"] == "failed"


def test_each_claimed_skill_requires_its_own_basis_and_quote_ownership():
    results, resolved = inputs()
    other = dict(resolved["projections"][0])
    other["revision_id"] = "ia-2"
    other["criterion"] = {**other["criterion"], "skill_id": "K1.2"}
    other["target"] = {**other["target"], "indicator_id": "K1.2.I1"}
    other["traces"] = [{"fragments": [{"id": "f-2", "quote": "Другая цитата"}]}]
    resolved["projections"].append(other)
    results["results"]["assessed_skill_profile"].append({
        **results["results"]["assessed_skill_profile"][0],
        "skill_id": "K1.2",
    })

    unsupported_skill = valid_output()
    unsupported_skill["claims"][0]["skill_ids"] = ["K1.1", "K1.2"]
    unsupported_quote = valid_output()
    unsupported_quote["claims"][1]["skill_ids"] = ["K1.1", "K1.2"]
    for output in (unsupported_skill, unsupported_quote):
        report = generate(results, resolved, gateway=Gateway(output))
        assert report["status"] == "failed"
        assert report["failure_reason"] == "DESCRIPTION_GENERATION_FAILED"

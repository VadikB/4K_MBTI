import json
from pathlib import Path

import pytest

from Api.m10_product_flow import participant_plan
from Api.m5_battery_contract import load_scenario
from Api.m5_battery_profile import review, verified_receipt
from Api.m5_case_runtime import checksum
from Api.m7_planning_package import methodology_targets
from Api.pilot_plan_admission import project_eligible_route
from Api.product_cycle_preparation_queue import public_operation


pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2] / "assessment_definitions/cases/competencies_4k"
BANK = ROOT / "functional-personalization/0.9/case-package.json"
RULES = ROOT / "functional-personalization-runtime/1.10.0"
SPEC02 = "CASE.SPEC.02"
SPEC09 = "CASE.SPEC.09"
WORK = "По результатам лабораторных проб сопоставляю способы контроля дефектов деталей."
DECISIONS = "После сравнения проб рекомендовала способ контроля, предложила повторить замер."
LIMITS = "Изучаю журналы проб и формулирую предварительные условия. Утверждает руководитель службы."
PROFILE = {"user_context": {"regular_tasks": WORK, "decision_situations": DECISIONS,
                            "constraints_and_interactions": LIMITS}}


class FitGateway:
    def __init__(self, cases):
        self.cases = cases
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(json.loads(messages[-1]["content"]))
        return json.dumps({"cases": self.cases})


def cases():
    return {case["case_id"]: case for case in json.loads(BANK.read_bytes())["cases"]}


def evidence(field=None, quote=None, status="supported"):
    return {"status": status, "field": field, "quote": quote}


def test_fit_uses_three_distinct_profile_answers_and_keeps_exact_evidence_private():
    design = load_scenario(cases()[SPEC02], RULES)
    gateway = FitGateway({SPEC02: {"work": evidence("regular_tasks", WORK),
                                  "decision": evidence("decision_situations", DECISIONS),
                                  "authority": evidence("constraints_and_interactions", LIMITS)}})
    result = review(PROFILE, [design], gateway, operation_id="test-fit")[SPEC02]
    assert result["status"] == "applicable"
    assert gateway.calls[0]["profile"] == PROFILE["user_context"]
    assert verified_receipt(PROFILE, design, result) == result
    with pytest.raises(ValueError, match="REVIEW_EVIDENCE_INVALID"):
        verified_receipt({"user_context": {**PROFILE["user_context"], "regular_tasks": "Другая работа"}}, design, result)
    candidate = {"case_id": SPEC02, "profile_fit": result}
    assert participant_plan({"plan": {"route": [candidate], "catalog": [candidate]}}) == {
        "plan": {"route": [{"case_id": SPEC02}], "catalog": [{"case_id": SPEC02}]}}


def test_a_confirmed_task_list_preserves_exact_item_provenance():
    design = load_scenario(cases()[SPEC02], RULES.parent / "1.10.4")
    first_task = "Веду журнал заявок."
    context = {**PROFILE["user_context"], "regular_tasks": [first_task, WORK]}
    profile = {"user_context": context}
    rows = {"work": evidence("regular_tasks", WORK),
            "decision": evidence("decision_situations", DECISIONS),
            "authority": evidence("constraints_and_interactions", LIMITS)}
    gateway = FitGateway({SPEC02: rows})
    result = review(profile, [design], gateway, operation_id="test-list-fit")[SPEC02]
    assert gateway.calls[0]["profile"] == context
    assert result["status"] == "applicable"
    assert result["evidence"]["work"]["quote"] == WORK
    assert result["evidence_source_paths"] == {"work": ["user_context/regular_tasks/1"]}
    assert verified_receipt(profile, design, result) == result

    reordered = {"user_context": {**context, "regular_tasks": [WORK, first_task]}}
    with pytest.raises(ValueError, match="REVIEW_SOURCE_MISMATCH"):
        verified_receipt(reordered, design, result)
    gateway = FitGateway({SPEC02: {**rows, "work": evidence("regular_tasks", f"{first_task} {WORK}")}})
    with pytest.raises(ValueError, match="REVIEW_EVIDENCE_INVALID"):
        review(profile, [design], gateway, operation_id="test-list-fit")


def test_saved_scalar_projection_for_an_earlier_rule_keeps_its_receipt():
    design = load_scenario(cases()[SPEC02], RULES)
    profile = {"user_context": {**PROFILE["user_context"], "regular_tasks": [WORK]}}
    old_sources = {"decision_situations": DECISIONS, "constraints_and_interactions": LIMITS}
    rows = {"work": evidence(status="unspecified"),
            "decision": evidence("decision_situations", DECISIONS),
            "authority": evidence("constraints_and_interactions", LIMITS)}
    gateway = FitGateway({SPEC02: rows})
    result = review(profile, [design], gateway, operation_id="test-old-fit")[SPEC02]
    assert gateway.calls[0]["profile"] == old_sources
    assert result["profile_sources_checksum"] == checksum(old_sources)
    assert "evidence_source_paths" not in result
    assert verified_receipt(profile, design, result) == result


def test_missing_decision_and_explicit_incompatibility_are_distinct_before_generation():
    case = cases()[SPEC02]
    design = load_scenario(case, RULES)
    one_answer = {"user_context": {"regular_tasks": WORK}}
    unknown = evidence(status="unspecified")
    gateway = FitGateway({SPEC02: {"work": evidence("regular_tasks", WORK), "decision": unknown, "authority": unknown}})
    missing = review(one_answer, [design], gateway, operation_id="test-fit")[SPEC02]
    assert (missing["status"], missing["criterion"]) == ("clarification_required", "decision")
    assert missing["message"] == design["profile_fit"]["criteria"]["decision"]["question"]
    answer = "Только переношу в реестр готовые решения. Выбор и рекомендации прямо запрещены."
    local_profile = {"user_context": {"regular_tasks": answer}}
    gateway = FitGateway({SPEC02: {"work": evidence("regular_tasks", answer, status="contradicted"),
                                  "decision": unknown, "authority": unknown}})
    rejected = review(local_profile, [design], gateway, operation_id="test-fit")[SPEC02]
    assert (rejected["status"], rejected["criterion"]) == ("incompatible", "work")


@pytest.mark.parametrize(("excluded", "expected"), [({SPEC09}, 39), ({SPEC02, SPEC09}, 30), ({SPEC02}, 32)])
def test_whole_route_coverage_meets_or_explains_versioned_program_requirements(excluded, expected):
    catalog = []
    for key, row in cases().items():
        ids = [target["indicator_id"] for target in row["indicator_targets"]]
        catalog.append({"case_id": key, "case_version": row["version"], "target_ids": ids,
                        "contribution_target_ids": ids, "planned_max_minutes": row["planned_max_minutes"],
                        "eligible": key not in excluded, "reasons": ["missing_profile_data"] if key in excluded else [],
                        "profile_fit": {"status": "clarification_required", "message": f"Уточнение {key}?"}})
    promised = set().union(*(row["target_ids"] for row in catalog))
    targets = [target for target in methodology_targets(["K1", "K2", "K3", "K4"])
               if target["indicator_id"] in promised]
    projection = project_eligible_route(catalog, targets, {"minimum_target_count": 39,
                                                          "required_target_ids": sorted(promised)})
    assert len(projection["covered"]) == expected
    assert not excluded.intersection(row["case_id"] for row in projection["route"])
    assert projection["admissible"] is (expected == 39)
    assert projection["coverage"]["missing_target_ids"] == sorted(promised - projection["covered"])
    assert projection["coverage"]["missing_required_target_ids"] == projection["coverage"]["missing_target_ids"]
    if expected < 39:
        assert projection["coverage"]["clarification_question"] == "Уточнение CASE.SPEC.02?"
        assert any(row["case_id"] == SPEC02 and row["reasons"] == ["missing_profile_data"]
                   for row in projection["coverage"]["excluded_cases"])
        operation = public_operation({
            "operation_id": "test", "status": "failed", "preparation": {"attempt_no": 1},
            "error_message": "PILOT_PLAN_PROGRAM_COVERAGE_UNAVAILABLE:"
                             + json.dumps(projection["coverage"], ensure_ascii=False),
        })
        assert operation["error"]["code"] == "ASSESSMENT_PROGRAM_COVERAGE_UNAVAILABLE"
        assert operation["retry_allowed"] is False
        assert operation["preparation"]["allowed_actions"] == []
        assert f"Доступно целей: {expected}." in operation["error"]["message"]
        assert "Вопрос для уточнения профиля. Уточнение CASE.SPEC.02?" in operation["error"]["message"]
        assert "В этом назначении подтверждённые ответы доступны только для просмотра." in operation["error"]["message"]
        assert "организатору нужно выдать новое назначение" in operation["error"]["message"]


def test_eligible_alternate_may_admit_only_under_its_own_program_requirements():
    catalog = [{"case_id": "A", "case_version": "1", "target_ids": ["a"], "contribution_target_ids": ["a"],
                "planned_max_minutes": 5, "eligible": True, "reasons": []},
               {"case_id": "B", "case_version": "1", "target_ids": ["b"], "contribution_target_ids": ["b"],
                "planned_max_minutes": 6, "eligible": False, "reasons": ["profile"]}]
    targets = [{"indicator_id": "a", "skill_id": "K1.S1"}, {"indicator_id": "b", "skill_id": "K2.S1"}]
    assert project_eligible_route(catalog, targets, {"minimum_target_count": 1, "required_target_ids": ["a"]})["admissible"]
    assert not project_eligible_route(catalog, targets, {"minimum_target_count": 1, "required_target_ids": ["b"]})["admissible"]

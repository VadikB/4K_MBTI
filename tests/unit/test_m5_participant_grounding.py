"""Controlled provider checks of the evidence and the admitted AS, not model quality."""
import json
from uuid import NAMESPACE_URL, uuid5

import pytest

from Api.assessment_start_readiness import functional_gate
from Api.cycle_execution_manifest import (
    M5_PARTICIPANT_GROUNDING_PACKAGE, M5_PARTICIPANT_GROUNDING_PACKAGES, M5_REVIEW_RESPONSE_PACKAGE,
)
from Api.m5_battery_contract import FACILITATOR
from Api.m5_battery_scenario import plan_turn
from Api.m5_functional_generation_service import build_passport_snapshot, build_persistence_trace, prepare
from Api.m5_participant_grounding import FINDING
from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome
from tests.integration.test_m5_battery_v04_db import V04Gateway
from tests.unit.test_m5_v7_start_review import (
    BATTERY_V04_SCENARIO_CURRENT, M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT, pilot_cases,
)

DECKHOUSE = "варианты внедрения Deckhouse"
ARCHIVE = "варианты перехода на электронный архив"
FALSE_POSITION = "Вы — специалист по внедрению Deckhouse и DevOps-сопровождению."
EXPERT_ADDRESS = "Вы — эксперт по внедрению."
WORK_DIVISION = "Коллега отвечает за сроки. Вы — за сравнение цен."
COLLEAGUE_LETTER = "Приложено письмо.\nКому: коллеге из команды внедрения.\n" + EXPERT_ADDRESS
FUNCTION_SUBSTITUTION = "В вашей работе вы внедряете Deckhouse и сопровождаете DevOps самостоятельно."
CONFIRMATION = "Вы сами подтверждаете техническую пригодность выбранного варианта."
PROMISE = "Вы обязаны пообещать заказчику срок внедрения за инженерную команду."
OWN_TECHNICAL_DECISION = "Самостоятельно подтверждаю техническую пригодность в пределах испытаний."
WORK = "profile/user_context/regular_tasks"
DECISION = "profile/user_context/decision_situations"
LIMITS = "profile/user_context/constraints_and_interactions"
POSITION = "profile/user_context/position_or_status"
PROFESSIONAL = "common.professional_consistency"
AUTHORITY = "common.authority"

SELLER = {
    "position_or_status": "sale",
    "regular_tasks": "Уточняю требования клиентов и сравниваю предложения по Deckhouse и электронному архиву.",
    "decision_situations": "Готовлю рекомендации коллеге и черновик ответа покупателю.",
    "constraints_and_interactions": "Техническую пригодность подтверждает инженер. Срок утверждает команда внедрения.",
}
ENGINEER = {
    "position_or_status": "Инженер",
    "regular_tasks": "Проверяю два варианта Deckhouse на стенде и готовлю техническое заключение.",
    "decision_situations": OWN_TECHNICAL_DECISION,
    "constraints_and_interactions": "Срок внедрения утверждает руководитель работ. Заказчику отправляю черновик.",
}


class GroundingGateway(V04Gateway):
    """The fixture returns separately controlled generation and review responses."""

    def __init__(self, topic=DECKHOUSE, *, defects=(), wrong_quote=False, show_position=False):
        super().__init__()
        self.topic = topic
        self.defects = defects
        self.wrong_quote = wrong_quote
        self.show_position = show_position

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing = kwargs["routing_key"]
        if ":generation:" not in routing:
            return response
        payload = self.calls[-1][2]
        candidate = json.loads(response.content)
        candidate["AssessmentSituationID"] = str(uuid5(NAMESPACE_URL, "task11:" + payload["case"]["CaseID"]))
        context = payload["profile"]["user_context"]
        own_tech = context.get("decision_situations") == OWN_TECHNICAL_DECISION
        p00 = next(row for row in candidate["Материалы"] if row["MaterialID"] == "P00")
        p00["Текст"] = (
            f"Сопоставьте {self.topic}. Напишите рекомендацию коллеге и подготовьте черновик для заказчика. "
            + (CONFIRMATION if own_tech else "Техническую пригодность подтверждает инженер.")
        )
        for material in candidate["Материалы"]:
            key = material["MaterialID"]
            if key != "P00":
                material["Текст"] = material["Текст"].replace("Deckhouse", self.topic)
            if ":repair:" not in routing:
                material["Текст"] = " ".join(
                    [*(phrase for mid, phrase in self.defects if mid == key), material["Текст"]]
                )
        if "participant_grounding" in payload and self.show_position:
            p00["Текст"] = payload["participant_grounding"]["p00"]["position_marker"] + "\n" + p00["Текст"]
        response.content = json.dumps(candidate, ensure_ascii=False)
        return response

    def review_response(self, routing, payload, checks):
        if "participant_grounding" not in payload:
            return super().review_response(routing, payload, checks)
        own_tech = payload["profile"]["user_context"].get("decision_situations") == OWN_TECHNICAL_DECISION
        evidence = {
            FUNCTION_SUBSTITUTION: (PROFESSIONAL, WORK, "Опишите деятельность по сопоставлению предложений."),
            **{phrase: (PROFESSIONAL, POSITION, "Укажите задачу продавца по подготовке рекомендации.")
               for phrase in (FALSE_POSITION, EXPERT_ADDRESS)},
            CONFIRMATION: (AUTHORITY, LIMITS, "Попросите инженера подтвердить техническую пригодность."),
            PROMISE: (AUTHORITY, LIMITS, "Укажите предварительный срок и запросите подтверждение команды."),
        }
        for row in checks:
            findings = []
            for material in payload["candidate_as"]["Материалы"]:
                for phrase, (check_id, source, correction) in evidence.items():
                    if (row["check_id"] != check_id or phrase not in material["Текст"]
                            or (phrase == CONFIRMATION and own_tech)
                            or (phrase == EXPERT_ADDRESS and COLLEAGUE_LETTER in material["Текст"])):
                        continue
                    findings.append({
                        "code": FINDING, "severity": "blocking", "requirement_ref": check_id,
                        "paths": ["candidate_as/Материалы/" + material["MaterialID"] + "/Текст"],
                        "reason": "Утверждение об участнике выходит за подтверждённую деятельность или мандат.",
                        "actual": {"phrase": phrase + (" неточная цитата" if self.wrong_quote else ""),
                                   "subject": "participant"},
                        "expected": {"basis_path": source, "correction": correction},
                    })
            if findings:
                row.update(status="FAIL", findings=findings)
        return super().review_response(routing, payload, checks)


def snapshot(pilot_cases, context, *, number=2, grounded=True, grounding_package=M5_PARTICIPANT_GROUNDING_PACKAGE):
    cases, bank = pilot_cases
    return build_passport_snapshot(
        case_version=cases[number], operation_id="controlled-task11", synthetic=True, battery_pilot=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        review_response_package=ROOT / M5_REVIEW_RESPONSE_PACKAGE,
        participant_grounding_package=(ROOT / grounding_package if grounded else None),
        battery_scenario_package=ROOT / BATTERY_V04_SCENARIO_CURRENT,
        package_ref={"id": bank["id"], "version": bank["version"]},
        profile_sources={"organization_context": 31, "role_profile": 32, "user_context": 33},
        selected_base_role="specialist_expert",
        profile={"user_context": {**context, "acquaintance_answers": {"private_unused": "internal"}},
                 "organization_context": {"activity_description": [DECKHOUSE, ARCHIVE]},
                 "role_profile": {"code": "specialist_expert",
                                  "card": {"independent_authority": ["Обосновывать решение в своей зоне."]}}},
    )


def task_start(inputs):
    return inputs["participant_grounding"]["p00"]["task_opening"]


def document(candidate, material_id):
    return next(row["Текст"] for row in candidate["Материалы"] if row["MaterialID"] == material_id)


def receipt(input_snapshot, gateway):
    result = prepare(input_snapshot, gateway)
    trace = build_persistence_trace(input_snapshot, result)
    if result["admitted_for_participant"]:
        functional_gate(trace, operation_id=input_snapshot["operation_id"])
    return result


def test_same_seller_two_subjects_and_exact_work_basis_reaches_every_role(pilot_cases):
    inputs = snapshot(pilot_cases, SELLER)
    for topic in (DECKHOUSE, ARCHIVE):
        before = GroundingGateway(topic)
        assert receipt(snapshot(pilot_cases, SELLER, grounded=False), before)["admitted_for_participant"]
        gateway = GroundingGateway(topic)
        result = receipt(inputs, gateway)
        assert result["tester"]["aggregation"]["status"] == "PASS"
        assert result["repair"] is None
        opening = document(result["candidate_as"], "P00")
        assert opening.startswith(task_start(inputs) + "\n\n" + f"Сопоставьте {topic}.")
        assert "Техническую пригодность подтверждает инженер." in opening
        assert len(gateway.calls) == len(before.calls) == 7
        for _, _, payload in gateway.calls:
            assert payload["profile"] == inputs["profile"]
            assert payload["profile"]["user_context"] == SELLER
            assert payload["participant_grounding"] == inputs["participant_grounding"]
        raw = json.loads(result["generation_operation"]["calls"][0]["response_content"])
        assert opening == task_start(inputs) + "\n\n" + document(raw, "P00")


@pytest.mark.parametrize("subject", [SELLER, ENGINEER], ids=["seller", "engineer"])
def test_same_subject_and_same_title_keep_different_confirmed_authority(pilot_cases, subject):
    context = {**subject, "position_or_status": "Эксперт"}
    inputs = snapshot(pilot_cases, context)
    gateway = GroundingGateway(defects=(("M01", CONFIRMATION), ("M06", PROMISE)))
    result = receipt(inputs, gateway)
    assert result["admitted_for_participant"]
    assert len(gateway.calls) == 14
    repair = result["repair"]
    assert repair["outcome"] == "PASS"
    payload = next(body for route, _, body in gateway.calls if ":generation:repair:" in route)
    assert payload["participant_grounding"] == inputs["participant_grounding"]
    assert payload["profile"]["user_context"] == context
    quotes = {finding["actual"]["phrase"] for row in payload["blocking_failures"] for finding in row["findings"]}
    assert quotes == ({CONFIRMATION, PROMISE} if subject is SELLER else {PROMISE})
    assert all(finding["actual"]["subject"] == "participant" and finding["expected"]["basis_path"] == LIMITS
               for row in payload["blocking_failures"] for finding in row["findings"])
    assert PROMISE not in document(result["candidate_as"], "M06")
    assert (CONFIRMATION in document(result["candidate_as"], "P00")) == (subject is ENGINEER)

    if subject is ENGINEER:
        allowed = receipt(inputs, GroundingGateway(defects=(("M01", CONFIRMATION),)))
        assert allowed["admitted_for_participant"] and allowed["repair"] is None


def test_old_payload_reproduces_substitution_and_new_repair_covers_all_documents(pilot_cases):
    before = GroundingGateway(defects=(("P00", FALSE_POSITION),))
    old = receipt(snapshot(pilot_cases, SELLER, grounded=False), before)
    assert old["repair"] is None
    assert old["admitted_for_participant"]
    assert document(old["candidate_as"], "P00").startswith(FALSE_POSITION)
    assert before.calls[0][2]["profile"]["user_context"]["position_or_status"] == "sale"
    assert "decision_situations" not in before.calls[0][2]["profile"]["user_context"]

    defects = (("P00", FUNCTION_SUBSTITUTION), *((f"M{n:02}", CONFIRMATION) for n in range(1, 7)))
    gateway = GroundingGateway(defects=defects)
    inputs = snapshot(pilot_cases, SELLER)
    result = receipt(inputs, gateway)
    assert result["admitted_for_participant"] and result["repair"]["outcome"] == "PASS"
    repair = next(body for route, _, body in gateway.calls if ":generation:repair:" in route)
    findings = {path: finding for row in repair["blocking_failures"] for finding in row["findings"] for path in finding["paths"]}
    assert set(findings) == {f"/candidate_as/Материалы/{index}/Текст" for index in range(7)}
    p00_index = next(i for i, row in enumerate(repair["rejected_candidate_as"]["Материалы"]) if row["MaterialID"] == "P00")
    p00_diagnostic = findings[f"/candidate_as/Материалы/{p00_index}/Текст"]
    assert p00_diagnostic["actual"] == {"phrase": FUNCTION_SUBSTITUTION, "subject": "participant"}
    assert p00_diagnostic["expected"] == {"basis_path": WORK, "correction": "Опишите деятельность по сопоставлению предложений."}
    assert document(result["candidate_as"], "P00").startswith(task_start(inputs))
    assert all(phrase not in document(result["candidate_as"], key) for key, phrase in defects)
    assert repair["profile"] == inputs["profile"]


def test_title_is_optional_and_does_not_confirm_a_mandate(pilot_cases):
    no_title = {"regular_tasks": " ".join(SELLER[key] for key in (
        "regular_tasks", "decision_situations", "constraints_and_interactions",
    ))}
    inputs = snapshot(pilot_cases, no_title)
    result = receipt(inputs, GroundingGateway(show_position=True))
    assert result["admitted_for_participant"] and document(result["candidate_as"], "P00").startswith(task_start(inputs))
    with pytest.raises(ValueError, match="M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/рабочая функция и полномочия"):
        snapshot(pilot_cases, {"position_or_status": "Эксперт"})


def test_optional_header_uses_frozen_value_and_does_not_mask_a_body_defect(pilot_cases):
    inputs = snapshot(pilot_cases, SELLER, number=3)
    gateway = GroundingGateway(show_position=True, defects=(("P00", FUNCTION_SUBSTITUTION), ("M01", PROMISE)))
    result = receipt(inputs, gateway)
    original = result["repair"]["original_candidate_as"]
    assert result["admitted_for_participant"]
    assert document(original, "P00").startswith("Должность — sale\n\n" + FUNCTION_SUBSTITUTION)
    assert document(result["candidate_as"], "P00").startswith("Должность — sale\n\nСопоставьте")
    assert PROMISE in document(original, "M01")
    assert PROMISE not in document(result["candidate_as"], "M01")
    literal = receipt(snapshot(pilot_cases, {**SELLER, "position_or_status": "Инженер по качеству"}, number=3),
                      GroundingGateway(show_position=True))
    assert document(literal["candidate_as"], "P00").startswith("Должность — Инженер по качеству\n\n")


@pytest.mark.parametrize(("number", "material_id", "body"), [
    (2, "P00", WORK_DIVISION),
    (3, "P00", COLLEAGUE_LETTER),
    (2, "M01", COLLEAGUE_LETTER),
], ids=["division-of-work", "embedded-letter-to-colleague", "document-to-colleague"])
def test_addressed_prose_is_presented_without_repair(pilot_cases, number, material_id, body):
    title = "Менеджер B2B-продаж · Северо-Запад"
    inputs = snapshot(pilot_cases, {**SELLER, "position_or_status": title}, number=number)
    show_position = number == 3
    gateway = GroundingGateway(defects=((material_id, body),), show_position=show_position)
    result = receipt(inputs, gateway)

    assert result["admitted_for_participant"] and result["repair"] is None
    assert len(gateway.calls) == 7
    assert body in document(result["candidate_as"], material_id)
    opening = document(result["candidate_as"], "P00")
    assert opening.startswith(f"Должность — {title}\n\n" if show_position else task_start(inputs))
    for role in ("tester", "challenger"):
        messages = next(messages for route, messages, _ in gateway.calls if f":{role}:" in route)
        assert any(item["role"] == "system" and "поле «Кому»" in item["content"] for item in messages)


@pytest.mark.parametrize(("number", "title_assertion"), [(2, EXPERT_ADDRESS), (3, FALSE_POSITION)],
                         ids=["spec02-task-opening", "after-exact-profile-signature"])
def test_direct_title_substitution_is_addressed_in_semantic_repair(pilot_cases, number, title_assertion):
    inputs = snapshot(pilot_cases, SELLER, number=number)
    gateway = GroundingGateway(defects=(("P00", title_assertion),), show_position=number == 3)
    result = receipt(inputs, gateway)

    assert result["admitted_for_participant"] and len(gateway.calls) == 14
    old_review = result["repair"]["original_tester"]
    assert old_review["aggregation"]["deterministic_failures"] == []
    for reviewer in ("tester", "challenger"):
        rows = old_review["independent_checks"][reviewer]
        finding, = next(row for row in rows if row["check_id"] == PROFESSIONAL)["findings"]
        assert finding["actual"] == {"phrase": title_assertion, "subject": "participant"}
        assert finding["expected"]["basis_path"] == POSITION
        assert finding["paths"][0].endswith("/Текст")
    opening = document(result["candidate_as"], "P00")
    expected = task_start(inputs) if number == 2 else "Должность — sale\n\n"
    assert opening.startswith(expected) and title_assertion not in opening


def test_official_heading_is_checked_against_profile(pilot_cases):
    inputs = snapshot(pilot_cases, SELLER, number=3)
    invented_heading = "Должность — Инженер по внедрению"
    gateway = GroundingGateway(defects=(("P00", invented_heading + "\n"),))
    result = receipt(inputs, gateway)

    assert result["admitted_for_participant"] and len(gateway.calls) == 8
    blocked = result["repair"]["original_tester"]
    finding, = blocked["aggregation"]["deterministic_failures"]
    assert finding["code"] == "participant_position_label"
    assert finding["actual"] == [(0, invented_heading)]
    assert finding["expected"] == [(0, "Должность — sale")]


def test_archived_v1_receipt_still_replays_with_its_frozen_package(pilot_cases):
    inputs = snapshot(pilot_cases, SELLER, grounding_package=M5_PARTICIPANT_GROUNDING_PACKAGES["1.0.0"])
    gateway = GroundingGateway(defects=(("P00", WORK_DIVISION),))
    result = receipt(inputs, gateway)
    assert result["admitted_for_participant"] and inputs["refs"]["participant_grounding"]["version"] == "1.0.0"
    failures = result["repair"]["original_tester"]["aggregation"]["deterministic_failures"]
    assert [row["code"] for row in failures] == ["participant_position_declaration"]


def test_a_finding_with_an_inexact_quote_cannot_authorize_repair(pilot_cases):
    result = prepare(snapshot(pilot_cases, SELLER), GroundingGateway(defects=(("M05", PROMISE),), wrong_quote=True))
    assert result["tester"]["aggregation"]["status"] == "INCOMPLETE"
    assert not result["admitted_for_participant"] and result["repair"] is None
    assert "PARTICIPANT_FINDING_QUOTE_MISMATCH" in {
        error["code"] for error in result["tester"]["aggregation"]["verification_errors"]
    }


@pytest.mark.parametrize("reply", ["Техническую пригодность подтверждает инженер.", CONFIRMATION])
def test_facilitator_reply_is_checked_against_same_frozen_basis(pilot_cases, reply):
    inputs = snapshot(pilot_cases, SELLER)
    candidate = prepare(inputs, GroundingGateway())
    design = candidate["execution_rules"]["cases"]["CASE.SPEC.02"]["battery_scenario"]
    payload = {"runtime_rules": {"battery_scenario": design}, "characters": []}
    calls = []

    class Semantic:
        def decide(self, *, rule, text, **_):
            key = rule["rule_id"]
            if key == "SCENARIO_CONTROL":
                return Decision(RuleOutcome.TRUE, "CONTINUE", "Вопрос об источнике.")
            if key == "E01_FACT":
                return Decision(RuleOutcome.TRUE, "MATCH", "Запрошено пояснение.", details={"speaker_ids": [FACILITATOR]})
            if key == "FACILITATOR_PARTICIPANT_GROUNDING":
                calls.append((rule, text))
                if text == CONFIRMATION:
                    return Decision(RuleOutcome.FALSE, "NO_MATCH",
                                    "Участник, " + LIMITS + ". Подтверждение оставить инженеру.",
                                    details={"text": CONFIRMATION})
                return Decision(RuleOutcome.TRUE, "MATCH", "Подтверждает инженер.")
            return Decision(RuleOutcome.FALSE, "NO_MATCH", "Событие не относится к вопросу.")

    class Character:
        def respond(self, *, material, **_):
            assert material["reaction_rule"]["profile"] == inputs["profile"]
            assert material["reaction_rule"]["participant_grounding"] == inputs["participant_grounding"]
            return CharacterReply("COMPLETED", reply, "controlled")

    state = {"disclosed_materials": design["start_ids"], "dialogue_history": []}
    outcome = plan_turn(payload, state, text="Что означает формулировка M05?", turn_id="example",
                        semantic=Semantic(), character=Character())
    assert len(calls) == 1 and calls[0][1] == reply
    assert calls[0][0]["condition"]["participant_grounding"] == inputs["participant_grounding"]
    visible = outcome.replies[0]
    if reply == CONFIRMATION:
        assert visible.response.content == design["facilitator_grounding"]["fallback"]
        assert visible.occurred_rule_ids == ()
        assert outcome.decisions["FACILITATOR_PARTICIPANT_GROUNDING"][1].details == {"text": CONFIRMATION}
    else:
        assert visible.response.content == reply
        assert visible.occurred_rule_ids == ("E01_FACT",)

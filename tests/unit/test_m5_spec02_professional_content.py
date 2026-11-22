"""Exercise SPEC.02 provider requests and admission with scripted semantic verdicts."""

from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import build_manifest, resolve_dependency
from Api.m5_passport_generation import AS_PACKAGE, BANK_PACKAGE, CURRENT_AS_PACKAGE, M2, provider_basis
from tests.passport_as_fixture import synthetic_as


CHECKS = ("common.professional_consistency", "case02.attractive_feature", "indicator:K1.I09")
PRESERVE = "Что сохранить при адаптации"
PROFESSIONS = {
    "credit": ("аналитик кредитных заявок", "кредитных заявок", "полнота пакета и сверка источника дохода"),
    "quality": ("инженер входного контроля", "измерительных приборов", "комплектность и сверка маркировки"),
    "hiring": ("специалист по подбору", "заявок на вакансию", "полнота анкеты и соответствие опыта"),
    "archives": ("архивист", "описей дел", "целостность описи и сверка шифра"),
}


def snapshot_for(profession, *, case_id="CASE.SPEC.02", package=None):
    position, objects, _ = PROFESSIONS[profession]
    cases = json.loads((BANK_PACKAGE / "case-package.json").read_bytes())["cases"]
    case = next(row for row in cases if row["case_id"] == case_id)
    profile = {
        "organization_context": {"activity_description": f"Профильная обработка {objects}."},
        "user_context": {"position_or_status": position, "regular_tasks": f"Проверка {objects}."},
        "role_profile": {"code": case["base_role"], "card": {
            "responsibility_object": objects,
            "independent_authority": "Сопоставить условия, подготовить рекомендацию заказчику.",
            "approval_required": "Обязательства по сроку и объёму согласует руководитель.",
        }},
    }
    manifest, checksum = build_manifest(
        profile_ref={"checksum": service.checksum(profile)}, selected_role_ref={"code": case["base_role"]},
        target_set_checksum=service.checksum(case["indicator_targets"]), parameter_sources={}, catalog_ref=None,
        **({"dependencies": {"m5_functional_as": str(package.relative_to(service.ROOT))}} if package else {}),
    )
    selected = resolve_dependency(manifest, checksum, "m5_functional_as")
    return service.build_passport_snapshot(
        case_version=case, profile=profile, operation_id=f"spec02-{profession}", synthetic=True, as_package=selected,
    )


def material(candidate, material_id):
    return next(row for row in candidate["Материалы"] if row["MaterialID"] == material_id)


def k1_i09(candidate):
    return next(row for row in candidate["IndicatorObservability"] if row["IndicatorID"] == "K1.I09")


def material_path(candidate, material_id):
    return f"candidate_as/Материалы/{candidate['Материалы'].index(material(candidate, material_id))}/Текст"


def document_texts(profession):
    _, objects, criteria = PROFESSIONS[profession]
    return {
        "M01": f"Заказчик, версия 1, утверждено. К 18 ноября нужны проверенные заключения минимум по 100 "
               f"позициям из партии {objects}. Критерии приёмки: {criteria}.",
        "M02": f"Владелец A, версия 1, план. Плановый объём A — 140 позиций из партии {objects} за пять "
               "рабочих дней. Ожидаем завершение к 18 ноября.",
        "M03": f"Владелец A, версия 2, актуализация. План на 140 позиций из партии {objects} сохраняется. "
               "Часть сверок завершится только 22 ноября. Объём проверенных заключений к 18 ноября неизвестен.",
        "M04": f"Владелец B, версия 1, предварительно. План — 110 позиций из партии {objects} за пять "
               "рабочих дней к 18 ноября. "
               "Доступность проверяющего для итоговой сверки ещё не согласована.",
        "M05": f"Профильный проверяющий, версия 1, отчёт. По 6 из 8 прошлых образцов {objects} "
               f"есть проверенные заключения, критерии — {criteria}. Все образцы из одной ранней партии. "
               "Проверка текущей партии не проводилась.",
        "M06": f"Коллега, версия 1, предложение. На обработку {objects} у A запланировано 140 позиций "
               "против 110 у B. По-моему, значит A отвечает всем требованиям заказчика.",
    }


def glossary(profession):
    _, objects, _ = PROFESSIONS[profession]
    return (
        f"Словарь. Плановый объём — число позиций в партии {objects}, намеченных к обработке. "
        "Заключение — запись о выполненной проверке до итоговой сверки по критериям. "
        "Проверенное заключение — результат с подтверждённым соответствием критериям."
    )


def coherent_as(snapshot, profession):
    position, objects, _ = PROFESSIONS[profession]
    candidate = synthetic_as(provider_basis(snapshot))
    candidate["Название"] = f"Выбор способа проверки {objects}"
    p00 = material(candidate, "P00")
    p00.update(Название="Вводная", Текст=(
        f"Вы — {position}. Сопоставьте два способа проверки {objects}. "
        "Подготовьте обоснованную рекомендацию коллеге и короткий черновик заказчику. "
        "Заказчику даётся рекомендация. Обязательство по сроку и ресурсам требует согласования.\n\n"
        + glossary(profession)
    ))
    for material_id, body in document_texts(profession).items():
        material(candidate, material_id)["Текст"] = body
    passport = snapshot["case"]["Паспорт"]
    candidate["События"] = passport["17 Сценарий Dialogue"]["События"]
    targets = passport["22 IndicatorIDs"]["Проектные условия"]
    for row, target in zip(candidate["IndicatorObservability"], targets, strict=True):
        assert row["IndicatorID"] == target["IndicatorID"]
        row.update({
            "Конкретное условие": f"Выбор способа проверки {objects}. " + " ".join(target["Проектное условие"]),
            "Форма проявления": "Самостоятельная рекомендация коллеге или черновик заказчику.",
            "Дефект потери": target["Риск потери"],
            "material_refs": target["Материалы и факты по функции"],
        })
    k1_i09(candidate).update({
        "Конкретное условие": "В сообщении заказчику можно отделить плановый объём от результата, "
                              "сохранив разницу между заключением до итоговой сверки и проверенным заключением.",
        PRESERVE: "В словаре P00 и документах сохранить смысл и статус заключения до сверки и результата "
                  "с подтверждённым соответствием. Дать основания сформулировать различие самостоятельно.",
        "material_refs": ["P00", "M01", "M02", "M03", "M05"],
    })
    return candidate


def mutate_profession(candidate, profession, foreign_profession):
    p00 = material(candidate, "P00")
    foreign_glossary = glossary(foreign_profession)
    documents = document_texts(foreign_profession)
    if foreign_profession == "hiring":
        foreign_glossary = foreign_glossary.replace("Проверенное заключение", "Решение по подбору")
        documents["M05"] = documents["M05"].replace("есть проверенные заключения",
                                                      "есть подтверждённое решение по подбору")
    p00["Текст"] = p00["Текст"].replace(glossary(profession), foreign_glossary)
    for material_id, body in documents.items():
        if material_id != "M01":
            material(candidate, material_id)["Текст"] = body


def mutate_glossary(candidate):
    p00 = material(candidate, "P00")
    p00["Текст"] = p00["Текст"].replace(
        "Заключение — запись о выполненной проверке до итоговой сверки по критериям.",
        "Заключение — результат с подтверждённым соответствием критериям.",
    )


def finding(check_id, paths, reason):
    return {"code": "SCRIPTED_CONTROL", "severity": "blocking", "paths": paths,
            "reason": reason, "requirement_ref": check_id}


class CapturingGateway:
    def __init__(self, initial, repaired, verdicts):
        self.initial = initial
        self.repaired = repaired
        self.verdicts = verdicts
        self.calls = []

    def chat_with_trace(self, messages, **kwargs):
        route = kwargs["routing_key"]
        payload = json.loads(messages[-1]["content"])
        if ":generation:" in route:
            role = "repair" if ":repair:" in route else "generation"
            response = self.initial if role == "generation" else self.repaired
            assert response is not None
        else:
            role = "tester" if ":tester:" in route else "challenger"
            checks = payload["applicability_plan"]["required_checks"] if role == "tester" else payload["protected_checks"]
            candidate_checksum = payload["candidate_checksum"]
            overrides = self.verdicts.get((candidate_checksum, role), {})
            response = {"candidate_checksum": candidate_checksum, "checks": []}
            for check in checks:
                check_id = check["check_id"]
                defect = overrides.get(check_id)
                response["checks"].append({
                    "check_id": check_id,
                    "status": "FAIL" if defect else "PASS",
                    "reason": defect["reason"] if defect else "Запрограммированный PASS для входа стенда.",
                    "findings": [defect] if defect else [],
                    "evidence_paths": defect["paths"] if defect else [],
                    "adversarial_review": {"candidate_conflicts": [], "resolution": "Синтетический ответ."},
                })
        self.calls.append({"role": role, "routing_key": route, "input_checksum": service.checksum(messages),
                           "messages": deepcopy(messages), "response": deepcopy(response)})
        return SimpleNamespace(content=json.dumps(response, ensure_ascii=False), sent={},
                               provider={"finish_reason": "stop"})


@pytest.mark.parametrize(("control", "profession", "reviewer", "repair_mode"), [
    ("AC1-credit", "credit", "tester", "corrected"),
    ("AC1-quality", "quality", "challenger", "still-invalid"),
    ("AC2", "credit", "challenger", "corrected"),
    ("AC3", "credit", None, None),
    ("AC2-unchanged", "credit", "tester", "unchanged"),
    ("AC2-without-paths", "credit", "tester", None),
], ids=["AC1-credit", "AC1-quality", "AC2", "AC3", "AC2-unchanged", "AC2-without-paths"])
def test_spec02_provider_requests_and_admission(tmp_path, control, profession, reviewer, repair_mode):
    snapshot = snapshot_for(profession)
    coherent = coherent_as(snapshot, profession)
    initial = deepcopy(coherent)
    defects = {}
    if control.startswith("AC1"):
        mutate_profession(initial, profession, {"credit": "hiring", "quality": "archives"}[profession])
        anchor = material_path(initial, "M01")
        defects[CHECKS[0]] = finding(
            CHECKS[0], [anchor, material_path(initial, "P00"),
                        *(material_path(initial, f"M{n:02d}") for n in range(2, 7))],
            "P00 и M01 задают один предмет, словарь и M02–M06 описывают другой.",
        )
        if control == "AC1-credit":
            defects[CHECKS[1]] = finding(
                CHECKS[1], [anchor, material_path(initial, "M02"), material_path(initial, "M06")],
                "Преимущество A рассчитано для другого предмета. Из M02 и M06 нельзя вывести соблюдение M01.",
            )
    elif control.startswith("AC2"):
        mutate_glossary(initial)
        target_path = f"candidate_as/IndicatorObservability/{initial['IndicatorObservability'].index(k1_i09(initial))}"
        paths = [material_path(initial, "P00"), material_path(initial, "M01"), material_path(initial, "M05"),
                 f"{target_path}/Конкретное условие", f"{target_path}/{PRESERVE}"]
        defects[CHECKS[2]] = finding(
            CHECKS[2], [] if control == "AC2-without-paths" else paths,
            "В P00 оба названия определены одним статусом, M01 и M05 не дают отличающего факта. "
            "Оба поля карты требуют недоступного участнику различия.",
        )

    initial_checksum = service.checksum(initial)
    verdicts = {(initial_checksum, reviewer): defects} if reviewer else {}
    repaired = {"corrected": coherent, "unchanged": initial}.get(repair_mode)
    if repair_mode == "still-invalid":
        repaired = deepcopy(initial)
        material(repaired, "M06")["Текст"] += " Уточнено время записи."
        verdicts[(service.checksum(repaired), reviewer)] = defects

    gateway = CapturingGateway(initial, repaired, verdicts)
    prepared = service.prepare(snapshot, gateway)
    before = prepared["repair"]["original_tester"] if prepared["repair"] else prepared["tester"]
    assert service.deterministic_checks(snapshot, initial)["status"] == "PASS"
    assert before["aggregation"]["status"] == (
        "INCOMPLETE" if control == "AC2-without-paths" else "FAIL" if defects else "PASS"
    )
    assert before["reviewed_candidate_checksum"] == initial_checksum
    if reviewer:
        other = {"tester": "challenger", "challenger": "tester"}[reviewer]
        assert all(row["status"] == "PASS" for row in before["independent_checks"][other])
    if control == "AC2-without-paths":
        assert not before["aggregation"]["blocking_failures"]
        assert any(row["code"] == "FINDING_LOCATION_REQUIRED" for row in before["aggregation"]["verification_errors"])
    else:
        assert {item["check_id"]: item["findings"][0] for item in before["aggregation"]["blocking_failures"]} == defects

    admitted = control == "AC3" or repair_mode == "corrected"
    assert prepared["admitted_for_participant"] is admitted
    assert (prepared["compiled_case"] is not None) is admitted
    assert (prepared["execution_rules"] is not None) is admitted
    assert bool(prepared["repair"]) is bool(repair_mode)
    if repair_mode == "unchanged":
        assert prepared["repair"]["outcome"] == "UNCHANGED_CANDIDATE"
    if admitted:
        public = prepared["compiled_case"]["participant_presentation"]
        assert public["introduction"] == material(coherent, "P00")["Текст"]
        assert [row["material_id"] for row in public["initial_materials"]] == [f"M{n:02d}" for n in range(1, 7)]
        assert not set(public) & {"case_content_contract", "m2_indicator_descriptors", "IndicatorObservability"}
        assert service.build_persistence_trace(snapshot, prepared)["accepted_as"] == coherent

    contract = json.loads((CURRENT_AS_PACKAGE / "case-content-contract.json").read_bytes())
    m2 = json.loads(M2.read_bytes())
    k1 = next(item for item in m2["competencies"] if item["id"] == "K1")
    descriptor = next(item for skill in k1["skills"] for component in skill["components"]
                      for item in component["indicators"] if item["id"] == "K1.I09")
    plan = snapshot["applicability_plan"]
    expected_ids = [row["check_id"] for row in plan["required_checks"]]
    assert service.checksum(expected_ids) == "bf4e1bd5155ef3e152d9c9404cc3bf5df4dbeccc0d2b2f325ed93e5f1c7de091"
    protected_ids = [row["check_id"] for row in plan["required_checks"] if row["protected"]]
    assert set(CHECKS) <= set(protected_ids)
    assert plan["protocol"]["version"] == "2.1.0"
    assert plan["protocol"]["checksum"] == snapshot["refs"]["tester_protocol"]["sha256"]

    reviewed = {}
    for call in gateway.calls:
        role = call["role"]
        payload = json.loads(call["messages"][-1]["content"])
        assert payload["case_content_contract"] == contract
        assert payload["m2_indicator_descriptors"] == {"K1.I09": descriptor}
        assert payload["profile"] == snapshot["profile"]
        assert payload["profile"]["user_context"]["position_or_status"] == PROFESSIONS[profession][0]
        card = payload["profile"]["role_profile"]["card"]
        assert card["responsibility_object"] == PROFESSIONS[profession][1]
        assert card["independent_authority"] and card["approval_required"]
        assert payload["normative_indicator_targets"] == snapshot["case_version"]["indicator_targets"]
        assert "author_as_example" not in payload and "author_assessment_situation" not in payload
        if role == "generation":
            assert "case_content_contract" in call["messages"][0]["content"]
        elif role == "repair":
            assert "case_content_contract" in call["messages"][2]["content"]
            assert service.checksum(payload["rejected_candidate_as"]) == initial_checksum
            assert payload["blocking_failures"] == before["aggregation"]["blocking_failures"]
        else:
            checksum = payload["candidate_checksum"]
            assert checksum == service.checksum(payload["candidate_as"])
            assert any("case_content" in message["content"] for message in call["messages"][:-1])
            rows = (payload["applicability_plan"]["required_checks"] if role == "tester" else payload["protected_checks"])
            for row in rows:
                check_id = row["check_id"]
                if check_id in CHECKS:
                    assert row["mandatory"] is True and row["protected"] is True
                    assert row["requirement"]["case_content"] == contract["requirements"][check_id]
            reviewed.setdefault((role, checksum), []).extend(row["check_id"] for row in rows)
    review_rounds = [initial_checksum]
    if repair_mode in {"corrected", "still-invalid"}:
        assert prepared["candidate_checksum"] != initial_checksum
        review_rounds.append(prepared["candidate_checksum"])
    assert reviewed == {(role, checksum): ids for checksum in review_rounds
                        for role, ids in [("tester", expected_ids), ("challenger", protected_ids)]}

    (tmp_path / f"{control}.json").write_text(json.dumps({
        "scope": "SYNTHETIC_GATEWAY_SCRIPTED_SEMANTIC_VERDICTS",
        "scenario": control, "source_refs": snapshot["refs"],
        "initial_candidate_checksum": initial_checksum, "initial_structure": "PASS",
        "initial_aggregation": before["aggregation"],
        "repair_outcome": repair_mode, "final_candidate_checksum": prepared["candidate_checksum"],
        "final_aggregation": prepared["tester"]["aggregation"],
        "request_counts": Counter(item["role"] for item in gateway.calls),
        "requests": gateway.calls,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_spec02_new_fields_apply_only_to_new_package_and_preserve_bound_versions():
    current = snapshot_for("credit")
    historical = snapshot_for("credit", package=AS_PACKAGE)
    assert current["refs"]["protocol_package"]["version"] == "2.0.0"
    assert historical["refs"]["protocol_package"]["version"] == "1.0.0"
    assert current["refs"]["as_contract"] == historical["refs"]["as_contract"]
    assert current["refs"]["m2"] == historical["refs"]["m2"]
    assert current["case_version"] == historical["case_version"]
    assert "case_content_contract" not in provider_basis(historical)

    old_candidate = synthetic_as(provider_basis(historical))
    assert service.deterministic_checks(historical, old_candidate)["status"] == "PASS"
    validation = service.deterministic_checks(current, old_candidate)
    assert validation["status"] == "FAIL"
    assert validation["errors"] == [{
        "error_class": "candidate_validation", "check": "indicator_adaptation_required_text",
        "path": f"candidate_as/IndicatorObservability/K1.I09/{PRESERVE}",
    }]

    other = snapshot_for("quality", case_id="CASE.SPEC.03")
    previous_plan = service.build_applicability_plan(other["case"])
    assert other["applicability_plan"]["required_checks"] == previous_plan["required_checks"]
    assert "case_content_contract" not in provider_basis(other)


@pytest.fixture
def spec02_candidate():
    snapshot = snapshot_for("credit")
    return snapshot, coherent_as(snapshot, "credit")


def _record_followup(tmp_path, prepared, gateway):
    initial = prepared["repair"]["original_tester"] if prepared["repair"] else prepared["tester"]
    repair_payloads = [json.loads(call["messages"][-1]["content"]) for call in gateway.calls
                       if call["role"] == "repair"]
    (tmp_path / "followup.json").write_text(json.dumps({
        "synthetic": True,
        "initial_candidate_checksum": initial["candidate_checksum"],
        "initial_admission": initial["aggregation"],
        "final_candidate_checksum": prepared["candidate_checksum"],
        "final_admission": prepared["tester"]["aggregation"],
        "admitted": prepared["admitted_for_participant"],
        "repair_requests": len(repair_payloads),
        "repair_bases": [{"blocking_failures": item["blocking_failures"],
                          "validation_errors": item["validation_errors"]} for item in repair_payloads],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("reviewer", ["tester", "challenger"])
@pytest.mark.parametrize(("field", "invalid_value", "error_code"), [
    ("requirement_ref", "indicator:K4.I99", "FINDING_REQUIREMENT_REF_MISMATCH"),
    ("paths", ["candidate_as/Материалы/9999/Текст"], "FINDING_PATH_UNRESOLVABLE"),
    ("paths", ["/candidate_as/Материалы/0/Необязательное поле"], "FINDING_PATH_UNRESOLVABLE"),
], ids=["foreign-requirement", "nonexistent-document", "unknown-leaf"])
def test_unfounded_finding_never_triggers_repair(spec02_candidate, tmp_path, reviewer, field, invalid_value, error_code):
    snapshot, candidate = spec02_candidate
    check_id = "indicator:K1.I09"
    defect = finding(check_id, [material_path(candidate, "M01")], "Синтетическая находка с ошибочным основанием.")
    defect[field] = invalid_value
    candidate_checksum = service.checksum(candidate)
    gateway = CapturingGateway(candidate, None, {(candidate_checksum, reviewer): {check_id: defect}})
    prepared = service.prepare(snapshot, gateway)
    assert prepared["deterministic_validation"]["status"] == "PASS"
    aggregation = prepared["tester"]["aggregation"]
    assert aggregation["status"] == "INCOMPLETE"
    assert not prepared["admitted_for_participant"] and not prepared["repair"]
    assert not aggregation["blocking_failures"]
    assert not any(call["role"] == "repair" for call in gateway.calls)
    error, = aggregation["verification_errors"]
    assert (error["code"], error["reviewer"], error["check_id"], error["candidate_checksum"]) == (
        error_code, reviewer, check_id, candidate_checksum,
    )
    assert error["actual"] == (invalid_value if field == "requirement_ref" else invalid_value[0])
    _record_followup(tmp_path, prepared, gateway)


@pytest.mark.parametrize("reviewer", ["tester", "challenger"])
@pytest.mark.parametrize(("check_id", "path"), [
    *(pytest.param(check_id, "candidate_as/CaseID", id=check_id) for check_id in CHECKS),
    pytest.param("indicator:K1.I09", "candidate_as/Материалы/M01/MaterialID", id="material-identifier"),
    pytest.param("indicator:K1.I09", "candidate_as/IndicatorObservability/0/Конкретное условие", id="different-indicator"),
    pytest.param("case02.attractive_feature", "candidate_as/IndicatorObservability/K1.I09/Конкретное условие",
                 id="outside-materials"),
])
def test_finding_must_use_an_evidence_section(spec02_candidate, tmp_path, reviewer, check_id, path):
    snapshot, candidate = spec02_candidate
    candidate_checksum = service.checksum(candidate)
    defect = finding(check_id, [path], "Синтетическая претензия без ссылки на относящееся к ней содержание.")
    gateway = CapturingGateway(candidate, None, {(candidate_checksum, reviewer): {check_id: defect}})
    prepared = service.prepare(snapshot, gateway)
    aggregation = prepared["tester"]["aggregation"]
    assert prepared["deterministic_validation"]["status"] == "PASS"
    assert aggregation["status"] == "INCOMPLETE" and not aggregation["blocking_failures"]
    assert not prepared["admitted_for_participant"] and prepared["repair"] is None
    assert not any(call["role"] == "repair" for call in gateway.calls)
    error, = aggregation["verification_errors"]
    assert error["code"] == "FINDING_EVIDENCE_UNRELATED"
    assert error["reviewer"] == reviewer and error["check_id"] == check_id
    assert error["candidate_checksum"] == candidate_checksum and error["actual"] == [path]
    assert error["expected"] == snapshot["case_content_contract"]["finding_evidence_sections"][check_id]
    _record_followup(tmp_path, prepared, gateway)


@pytest.mark.parametrize("valid_reviewer, invalid_reviewer", [("tester", "challenger"), ("challenger", "tester")])
@pytest.mark.parametrize("invalid_path, error_code", [
    ("$.candidate_as.Материалы[9999].Текст", "FINDING_PATH_UNRESOLVABLE"),
    ("candidate_as/CaseID", "FINDING_EVIDENCE_UNRELATED"),
], ids=["nonexistent-address", "metadata-only"])
def test_localized_blocker_survives_other_reviewers_error(
    spec02_candidate, tmp_path, valid_reviewer, invalid_reviewer, invalid_path, error_code,
):
    snapshot, corrected = spec02_candidate
    candidate = deepcopy(corrected)
    mutate_glossary(candidate)
    check_id = "indicator:K1.I09"
    real_finding = finding(
        check_id,
        ["candidate_as/CaseID", "$.candidate_as.Материалы[P00].Текст", "/candidate_as/Материалы/M01/Текст",
         "candidate_as/IndicatorObservability/K1.I09/Конкретное условие",
         "candidate_as.IndicatorObservability['K1.I09']['Что сохранить при адаптации']"],
        "Словарь присвоил один статус обоим терминам, от которых зависит условие карты.",
    )
    invalid_finding = finding(
        check_id, [invalid_path], "Синтетическая находка без доступного содержательного основания.",
    )
    initial_checksum = service.checksum(candidate)
    gateway = CapturingGateway(candidate, corrected, {
        (initial_checksum, valid_reviewer): {check_id: real_finding},
        (initial_checksum, invalid_reviewer): {check_id: invalid_finding},
    })
    prepared = service.prepare(snapshot, gateway)
    initial = prepared["repair"]["original_tester"]["aggregation"]
    assert initial["status"] == "FAIL"
    assert [(item["reviewer"], item["findings"]) for item in initial["blocking_failures"]] == [
        (valid_reviewer, [real_finding]),
    ]
    error, = initial["verification_errors"]
    assert (error["reviewer"], error["code"]) == (invalid_reviewer, error_code)
    repair_call, = [call for call in gateway.calls if call["role"] == "repair"]
    payload = json.loads(repair_call["messages"][-1]["content"])
    assert payload["blocking_failures"] == initial["blocking_failures"]
    assert prepared["candidate_checksum"] == service.checksum(corrected) != initial_checksum
    assert prepared["tester"]["reviewed_candidate_checksum"] == prepared["candidate_checksum"]
    assert all(row["candidate_checksum"] == prepared["candidate_checksum"]
               for reviews in prepared["tester"]["independent_checks"].values() for row in reviews)
    assert prepared["admitted_for_participant"]
    _record_followup(tmp_path, prepared, gateway)


@pytest.mark.parametrize("field", [PRESERVE, "material_refs"])
def test_finding_can_cite_the_row_with_a_missing_required_k1_i09_field(spec02_candidate, tmp_path, field):
    snapshot, corrected = spec02_candidate
    candidate = deepcopy(corrected)
    del k1_i09(candidate)[field]
    check_id = "indicator:K1.I09"
    defect = finding(check_id, ["candidate_as/IndicatorObservability/K1.I09"],
                     f"В строке K1.I09 отсутствует поле «{field}».")
    gateway = CapturingGateway(candidate, corrected, {(service.checksum(candidate), "tester"): {check_id: defect}})
    prepared = service.prepare(snapshot, gateway)
    initial = prepared["repair"]["original_tester"]["aggregation"]
    assert initial["blocking_failures"][0]["findings"] == [defect]
    assert not initial["verification_errors"]
    assert prepared["admitted_for_participant"]
    _record_followup(tmp_path, prepared, gateway)


@pytest.mark.parametrize("path", [
    "candidate_as/Материалы/M01",
    "candidate_as.Автор",
    "$.candidate_as[\"Материалы\"][0][\"Текст\"]",
], ids=["existing-container", "undeclared-leaf", "missing-required-field"])
def test_finding_on_a_missing_field_must_identify_a_required_element(spec02_candidate, tmp_path, path):
    snapshot, corrected = spec02_candidate
    candidate = deepcopy(corrected)
    del material(candidate, "M01")["Текст"]
    check_id = "case02.attractive_feature"
    defect = finding(check_id, [path], "В обязательном M01 отсутствует текст требований.")
    gateway = CapturingGateway(candidate, corrected, {(service.checksum(candidate), "challenger"): {check_id: defect}})
    prepared = service.prepare(snapshot, gateway)
    initial = prepared["repair"]["original_tester"]["aggregation"]
    if path == "candidate_as.Автор":
        assert not initial["blocking_failures"]
        assert initial["verification_errors"][0]["actual"] == path
    else:
        assert initial["blocking_failures"][0]["findings"] == [defect]
        assert not initial["verification_errors"]
    assert prepared["admitted_for_participant"]
    _record_followup(tmp_path, prepared, gateway)


@pytest.mark.parametrize("changed", [False, True], ids=["unchanged", "corrected"])
def test_empty_k1_i09_refs_block_even_when_both_reviewers_pass(spec02_candidate, tmp_path, changed):
    snapshot, corrected = spec02_candidate
    candidate = deepcopy(corrected)
    k1_i09(candidate)["material_refs"] = []
    gateway = CapturingGateway(candidate, corrected if changed else candidate, {})
    prepared = service.prepare(snapshot, gateway)
    repair = prepared["repair"]
    initial = repair["original_tester"]
    assert initial["aggregation"]["status"] == "FAIL"
    assert all(row["status"] == "PASS" for reviews in initial["independent_checks"].values() for row in reviews)
    error, = repair["original_deterministic_validation"]["errors"]
    assert error["path"] == "candidate_as/IndicatorObservability/K1.I09/material_refs"
    assert error["check"] == "indicator_initial_material_ref_required"
    repair_call, = [call for call in gateway.calls if call["role"] == "repair"]
    payload = json.loads(repair_call["messages"][-1]["content"])
    assert payload["validation_errors"] == [error]
    assert prepared["admitted_for_participant"] is changed
    if changed:
        assert prepared["tester"]["reviewed_candidate_checksum"] == service.checksum(corrected)
    else:
        assert repair["outcome"] == "UNCHANGED_CANDIDATE"
        assert prepared["compiled_case"] is None
    _record_followup(tmp_path, prepared, gateway)

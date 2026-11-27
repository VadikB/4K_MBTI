"""Сохранение сводки индикатора при повторе M6 Evidence."""
from copy import deepcopy

import pytest

from Api.assessment_configuration import definition_checksum
from Api.m6_evidence_service_v2 import evaluate
from Api.m6_package_v2 import load_mechanism
from tests.m6_bundle_repair_fixture import (
    TARGETS,
    RecordedEvidenceGateway,
    complete_reply,
    double_defect_reply,
    partial_reply,
)
from tests.unit.test_m6_bundle_repair import synthetic_material


pytestmark = pytest.mark.unit


REVIEWED = ("K1.I06", "K4.I03")
LIMIT = "Ход фиксирует намерение сверить сроки. Выполненная сверка ещё не показана."


def bundle(result, indicator):
    return next(row for row in result["bundles"] if row["indicator_id"] == indicator)


def completed(material):
    result = complete_reply(material)
    for indicator in REVIEWED:
        bundle(result, indicator)["limitations"] = [LIMIT]
    return result


def partial(material):
    result = partial_reply(material)
    # Повреждена отдельная цитата по K1.I09. Две выбранные сводки совпадают
    # с полным корректным ответом для этого же хода и этих же целей.
    result["bundles"] = [row for row in completed(material)["bundles"] if row["indicator_id"] in REVIEWED]
    assert bundle(result, "K1.I06")["evidence_ids"] == ["evidence-schedule"]
    assert bundle(result, "K4.I03")["evidence_ids"] == []
    return result


@pytest.fixture(params=["1.0.1", "1.0.2"])
def mechanism(request):
    return load_mechanism(f"m6_evidence/{request.param}")


def analyse(mechanism, gateway):
    return evaluate(synthetic_material(TARGETS), mechanism, definition_checksum(mechanism), gateway=gateway)


CHANGES = {
    "opportunity_basis": "У участника не было хода для ответа и слова о сроках не прозвучали.",
    "limitations": [],
    "context_refs": [],
    "contradictions": ["Участник сообщил два взаимоисключающих срока исполнения."],
}


@pytest.mark.parametrize("indicator", REVIEWED, ids=["with-evidence", "without-evidence"])
@pytest.mark.parametrize("field", CHANGES)
def test_repair_preserves_independent_bundle_or_rejects_at_its_path(mechanism, indicator, field):
    def changed(material):
        result = completed(material)
        bundle(result, indicator)[field] = deepcopy(CHANGES[field])
        return result

    gateway = RecordedEvidenceGateway(partial, changed)
    try:
        result, trace = analyse(mechanism, gateway)
    except ValueError as error:
        assert len(gateway.calls) == 2
        first, last = error.ai_trace["validation_attempts"]
        assert (first["status"], last["status"]) == ("rejected", "rejected")
        # Исполнитель может адресовать поле индексом в первом или во втором
        # ответе либо самим indicator_id.
        field_paths = {f"bundles.{indicator}.{field}"}
        for reply in gateway.responses:
            index = next(i for i, row in enumerate(reply["bundles"]) if row["indicator_id"] == indicator)
            field_paths.add(f"bundles.{index}.{field}")
        paths = [issue["path"].strip("/").replace("/", ".") for issue in last["validation_errors"]]
        assert any(path == base or path.startswith(base + ".") for base in field_paths for path in paths), paths
        return

    assert len(gateway.calls) == 2
    first, last = trace["validation_attempts"]
    assert (first["status"], last["status"]) == ("rejected", "accepted")
    assert len(result["bundles"]) == len(TARGETS)
    initial, model_repair = gateway.responses
    assert bundle(initial, indicator)[field] != bundle(model_repair, indicator)[field]
    for reviewed in REVIEWED:
        assert bundle(result, reviewed) == bundle(initial, reviewed), (
            f"Принята подмена сводки {reviewed}, поле {field}"
        )


@pytest.mark.parametrize("case", ["full", "zero-to-nine", "unchanged", "invalid-reference", "new-evidence"])
def test_valid_cases_pass(mechanism, case):
    def first_reply(material):
        if case == "full":
            return completed(material)
        if case == "zero-to-nine":
            return double_defect_reply(material)
        result = partial(material)
        if case == "invalid-reference":
            bundle(result, "K1.I06")["context_refs"][0]["id"] = "unknown-turn"
        return result

    def repaired(material):
        result = completed(material)
        if case == "new-evidence":
            # После исправления цитаты о цене она также обосновывает отдельное
            # наблюдение по K1.I06. Существующая связь со сроками сохраняется.
            schedule, price = result["evidence"]
            extra = deepcopy(price)
            extra.update(
                id="evidence-price-for-message",
                indicator_id="K1.I06",
                interpretation="Участник включил уточнение цены в сообщение о дальнейших действиях.",
                attribution=deepcopy(schedule["attribution"]),
            )
            result["evidence"].append(extra)
            row = bundle(result, "K1.I06")
            row["evidence_ids"].append(extra["id"])
            row["opportunity_basis"] += " Также названо уточнение цены."
        return result

    gateway = RecordedEvidenceGateway(first_reply, repaired)
    result, trace = analyse(mechanism, gateway)
    assert len(gateway.calls) == (1 if case == "full" else 2)
    assert trace["validation_attempts"][-1]["status"] == "accepted"
    assert len(result["bundles"]) == len(TARGETS)
    assert {row["indicator_id"] for row in result["bundles"]} == set(TARGETS)
    assert bundle(result, "K4.I03") == bundle(completed(synthetic_material(TARGETS)), "K4.I03")
    schedule = bundle(result, "K1.I06")
    assert schedule["context_refs"][0]["id"] == "synthetic-turn"
    expected = {"evidence-schedule"}
    if case == "new-evidence":
        expected.add("evidence-price-for-message")
    assert set(schedule["evidence_ids"]) == expected


def test_duplicate_evidence_under_new_id_does_not_justify_rewriting_summary(mechanism):
    def repaired(material):
        result = completed(material)
        duplicate = {**deepcopy(result["evidence"][0]), "id": "duplicate-schedule"}
        result["evidence"].append(duplicate)
        summary = bundle(result, "K1.I06")
        summary["evidence_ids"].append(duplicate["id"])
        summary["opportunity_basis"] = CHANGES["opportunity_basis"]
        return result

    gateway = RecordedEvidenceGateway(partial, repaired)
    with pytest.raises(ValueError, match="M6_REPAIR_BUNDLE_CHANGED") as rejected:
        analyse(mechanism, gateway)

    assert len(gateway.calls) == 2
    assert {"code": "M6_REPAIR_BUNDLE_CHANGED", "path": "bundles.0.opportunity_basis"} in (
        rejected.value.ai_trace["validation_attempts"][-1]["validation_errors"]
    )


def test_foreign_evidence_reference_only_invalidates_the_bundle_that_uses_it(mechanism):
    def first_reply(material):
        result = partial(material)
        bundle(result, "K4.I03")["evidence_ids"] = ["evidence-schedule"]
        result["bundles"].reverse()
        return result

    def repaired(material):
        result = completed(material)
        bundle(result, "K1.I06")["limitations"] = []
        return result

    gateway = RecordedEvidenceGateway(first_reply, repaired)
    with pytest.raises(ValueError, match="M6_REPAIR_BUNDLE_CHANGED") as rejected:
        analyse(mechanism, gateway)

    assert len(gateway.calls) == 2
    assert {"code": "M6_REPAIR_BUNDLE_CHANGED", "path": "bundles.0.limitations"} in (
        rejected.value.ai_trace["validation_attempts"][-1]["validation_errors"]
    )

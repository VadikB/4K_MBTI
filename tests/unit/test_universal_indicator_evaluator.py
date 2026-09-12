import json

import pytest

from Api import universal_indicator_evaluator as module
from Api.universal_indicator_evaluator import IndicatorShadowRunner, UniversalIndicatorEvaluator
from tests.unit.test_assessment_indicator_repository import input_data


def payload(*, case_id: int = 31, indicator_code: str = "K1.I01") -> dict:
    return {
        "contract_version": 2,
        "competency_code": "K1",
        "component_code": "evaluation.communication",
        "component_version": 2,
        "status": "evaluated",
        "indicator_assessments": [{
            "indicator_code": indicator_code,
            "evidence_state": "observed",
            "level_code": "L1",
            "evidence": [{"session_case_id": case_id, "observation": "Уточняет цели.", "excerpt": "Уточню цели."}],
            "red_flag_codes": [],
            "rationale": "Наблюдается базовое действие.",
            "confidence": 0.8,
        }],
    }


class Gateway:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


@pytest.mark.unit
def test_indicator_evaluator_uses_frozen_markdown_and_contract_schema() -> None:
    gateway = Gateway(json.dumps(payload(), ensure_ascii=False))
    result = UniversalIndicatorEvaluator(gateway).evaluate(input_data=input_data())

    assert result.indicator_assessments[0].level_code == "L1"
    system = gateway.calls[0][0][0]["content"]
    assert "Оценить индикаторы." in system
    assert "CompetencyIndicatorEvaluationOutput" in system


@pytest.mark.unit
def test_disabled_indicator_shadow_does_not_call_llm_or_repository(monkeypatch) -> None:
    class Repository:
        def save(self, **_kwargs):
            raise AssertionError("disabled shadow must not write")

    gateway = Gateway(json.dumps(payload()))
    monkeypatch.setattr(module.settings, "assessment_indicator_shadow_enabled", False)

    assert IndicatorShadowRunner(gateway, Repository()).run(
        connection=object(), input_data=input_data(),
    ) == "disabled"
    assert gateway.calls == []


@pytest.mark.unit
def test_successful_indicator_shadow_saves_validated_output(monkeypatch) -> None:
    saved = []

    class Repository:
        def save(self, **kwargs):
            saved.append(kwargs["output"])

    monkeypatch.setattr(module.settings, "assessment_indicator_shadow_enabled", True)
    result = IndicatorShadowRunner(Gateway(json.dumps(payload())), Repository()).run(
        connection=object(), input_data=input_data(),
    )

    assert result == "succeeded"
    assert saved[0].indicator_assessments[0].indicator_code == "K1.I01"


@pytest.mark.unit
def test_invalid_shadow_reference_is_isolated_without_write(monkeypatch, caplog) -> None:
    class Repository:
        def save(self, **_kwargs):
            raise AssertionError("invalid output must not write")

    monkeypatch.setattr(module.settings, "assessment_indicator_shadow_enabled", True)
    result = IndicatorShadowRunner(
        Gateway(json.dumps(payload(case_id=999))), Repository(),
    ).run(connection=object(), input_data=input_data())

    assert result == "failed"
    assert "Уточню цели" not in caplog.text
    assert "UniversalIndicatorEvaluationError" in caplog.text

from copy import deepcopy
from io import BytesIO
import json

from pypdf import PdfReader
import pytest

from Api.m8_report_comparison import compare_reports, render_comparison_pdf
from scripts.report_preview_fixture import saved_reports


@pytest.mark.parametrize("pair,mode,expected", [
    ("normal", "numeric", [(1.75, 2.25, .5), (0, 0, 0), (2, 1.75, -.25)]),
    ("partial", "numeric", [(1.5, 1.75, .25)]),
    ("mixed", "mixed", [(1.75, 2.25, .5), (1.5, 1.5, None), (2, 1.75, None), (None, None, None), (None, None, None)]),
])
def test_shared_saved_fixtures_have_independent_numbers_outcomes_and_no_mutation(pair, mode, expected):
    reports = saved_reports()
    current, previous = reports[pair + "-current"], reports[pair + "-previous"]
    before = deepcopy((current, previous))
    value = compare_reports(current, previous)
    assert value["contract_version"] == "m8-report-comparison/1.2.0"
    assert value["mode"] == mode
    for index, numbers in enumerate(expected):
        row = value["skills"][index]
        assert (row["previous"], row["current"], row["difference"]) == numbers
        for side, report in [("previous", previous), ("current", current)]:
            result = row[side + "_result"]
            assert result["outcome"] == report["c67"]["skills"][index]["outcome"]
            assert result["completeness"] == report["c67"]["skills"][index]["completeness"]
            assert result["skill_ref"]["report_id"] == report["id"]
            assert all(row["skill_id"] in claim["skill_ids"] for claim in result["claims"])
    assert (current, previous) == before
    if pair == "partial":
        assert all(value["skills"][0][side + "_result"]["reasons"] for side in ["previous", "current"])
    if pair == "mixed":
        assert [row["current_result"]["outcome"] for row in value["skills"][3:5]] == ["result_without_score", "no_result"]


def test_legacy_unknown_completeness_is_not_upgraded_and_private_material_is_not_projected():
    reports = saved_reports()
    current, previous = reports["normal-current"], reports["normal-previous"]
    previous["c67"]["skills"][0].pop("completeness")
    previous["c67"]["skills"][0]["presentation"]["internal_prompt"] = "PRIVATE-SYNTHETIC-MARKER"
    previous["c67"]["descriptive"]["claims"][0]["evidence_ids"] = ["PRIVATE-SYNTHETIC-MARKER"]
    previous["c67"]["skills"][0]["limitations"] = ["Неизвестное существенное ограничение"]
    value = compare_reports(current, previous)
    assert value["skills"][0]["previous_result"]["completeness"] is None
    assert "Неизвестное существенное ограничение" in value["skills"][0]["previous_result"]["limitations"]
    assert "PRIVATE-SYNTHETIC-MARKER" not in json.dumps(value)
    current["c67"]["skills"].pop(0)
    removed = compare_reports(current, previous)["skills"][-1]
    assert removed["current_result"]["present"] is False
    assert removed["current_result"]["outcome"] is None


def test_different_roles_never_get_a_shared_delta():
    reports = saved_reports()
    value = compare_reports(reports["mixed-current"], reports["role-previous"])
    assert value["mode"] == "separate"
    assert all(row["difference"] is None for row in value["skills"])


@pytest.mark.parametrize("pair,expected", [("normal", "+0,50"), ("partial", "+0,25")])
def test_real_pdf_keeps_exact_pair_numbers_and_both_partial_results(pair, expected):
    reports = saved_reports()
    value = compare_reports(reports[pair + "-current"], reports[pair + "-previous"])
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_comparison_pdf(value))).pages)
    assert "Программа 4К · октябрь" in text and "Программа 4К · ноябрь" in text
    assert "2026-10-01" in text and "2026-11-17" in text
    assert expected in text
    assert "0,00" in text
    if pair == "partial":
        assert text.count("Результат по части навыка") == 2
        assert text.count("Оценена часть обязательных проявлений") == 2
        assert "1,50" in text and "1,75" in text

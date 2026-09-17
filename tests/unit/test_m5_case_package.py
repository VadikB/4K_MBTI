from __future__ import annotations

import copy
import io
import json
import zipfile

import pytest
from pydantic import ValidationError

from Api.assessment_case_contracts import AssessmentSituation, CaseDefinition, VerificationReport
from scripts.build_m5_case_package import (
    M2, M3, OUTPUT, build_package, read_xlsx,
    validate_package, verify_directory, write_package,
)

pytestmark = pytest.mark.unit


def package():
    return json.loads((OUTPUT / "case-package.json").read_text())


def validate(value):
    validate_package(value, json.loads(M2.read_text()), json.loads(M3.read_text()))


def provenance():
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    return {"archive": manifest["archive"], "sources": manifest["sources"],
            "source_workbooks": json.loads((OUTPUT / "source-workbooks.json").read_text()),
            "source_texts": json.loads((OUTPUT / "source-texts.json").read_text())}


def situation():
    source = [o for o in package()["candidate_observability"] if o["test_as_id"] == "AS.TEST.SCR.A01.TEAM"]
    ref = {"id": "test", "version": "1", "checksum": "a" * 64}
    return {
        "assessment_situation_id": "AS.FIXTURE", "case_ref": ref, "profile_ref": ref,
        "methodology_ref": ref, "base_role": "team_lead", "substitutions": [],
        "presentation": "Синтетическое предъявление", "conditions": "Тестовые условия",
        "scenario": "Тестовый сценарий", "planned_minutes": 8, "qa_result": "PASS", "qa_basis": "Фикстура",
        "observability": [{"skill_id": o["skill_id"], "component_id": o["component_id"],
                           "indicator_id": o["indicator_id"], "required": True,
                           "conditions": [o["conditions"]], "branches": [o["branch"]],
                           "observable_action": o["observable_action"], "loss_risk": o["loss_risk"],
                           "qa_result": "PASS", "qa_basis": "Фикстура"} for o in source],
    }


def test_repository_package_is_read_back_verified_and_not_runtime_pass():
    report = verify_directory(OUTPUT)
    assert report["mode"] == "static_package"
    assert report["runtime_execution"] == report["m6_execution"] == "NOT_RUN"
    value = package()
    assert len(value["cases"]) == 20
    assert len(value["case_types"]) == 20
    assert len(CaseDefinition.model_fields) == 21
    assert len(value["test_situations"]) == 40
    assert len(value["candidate_observability"]) == 80
    assert len(value["qa_specs"]) == 160
    assert {r["result"] for r in value["qa_specs"]} == {"NOT_RUN"}


def test_k2_candidates_do_not_silently_become_approved_targets():
    pending = [o for o in package()["candidate_observability"] if o["indicator_id"] is None]
    assert len(pending) == 14
    assert all(o["resolution"] == "pending_methodological_review" for o in pending)
    assert all(o["candidate_indicator_ids"] for o in pending)
    assert any(len(o["candidate_indicator_ids"]) > 1 for o in pending)
    assert any(len(o["candidate_indicator_ids"]) == 1 for o in pending)


@pytest.mark.parametrize("mutation,match", [
    (lambda p: p["cases"][0]["case_type_ids"].append("CT99"), "Unknown CT"),
    (lambda p: p["cases"][0]["applicable_base_roles"].append("unknown"), "Unknown CT or BaseRole"),
    (lambda p: p["cases"][0]["applicability"][0].update(skill_id="K1.1"), "Applicability hierarchy"),
    (lambda p: p["candidate_observability"][0].update(candidate_indicator_ids=["K1.I01"]), "candidate"),
    (lambda p: p["test_situations"][0].update(case_version="unknown"), "version/synthetic"),
    (lambda p: p["qa_specs"][0].update(result="PASS"), "cannot claim"),
    (lambda p: p["cases"].append(copy.deepcopy(p["cases"][0])), "Duplicate CaseID"),
    (lambda p: p["candidate_observability"].append(copy.deepcopy(p["candidate_observability"][0])), "Duplicate Observability"),
    (lambda p: p["candidate_observability"].pop(0), "missing an Applicability target"),
    (lambda p: p["role_branches"][0].update(CaseID="SCR.D05"), "branch AS/role"),
    (lambda p: p["scenarios"][0].update(CTIDs="CT01"), "composition mismatch"),
    (lambda p: p["pilot_forms"][0].update({"Компонентов": 11}), "coverage mismatch"),
    (lambda p: p.update(runtime_enabled=True), "runtime disabled"),
])
def test_invalid_package_is_rejected(mutation, match):
    value = package()
    mutation(value)
    with pytest.raises(ValueError, match=match):
        validate(value)


def test_one_case_type_does_not_limit_multiple_indicators():
    case = package()["cases"][0]
    case["case_type_ids"] = ["CT06"]
    assert len(CaseDefinition.model_validate(case).case_type_ids) == 1
    snapshot = AssessmentSituation.model_validate(situation())
    assert len(snapshot.observability) == 2
    assert len({o.component_id for o in snapshot.observability}) == 2


def test_multiple_indicators_of_same_component_are_supported():
    value = situation()
    value["observability"][0].update(skill_id="K2.3", component_id="K2.C09", indicator_id="K2.I13")
    value["observability"][1].update(skill_id="K2.3", component_id="K2.C09", indicator_id="K2.I14")
    snapshot = AssessmentSituation.model_validate(value)
    assert len(snapshot.observability) == 2
    assert len({o.component_id for o in snapshot.observability}) == 1


@pytest.mark.parametrize("result", ["FAIL", "NOT_RUN"])
def test_one_missing_required_target_blocks_as_pass(result):
    value = situation()
    value["observability"][1]["qa_result"] = result
    with pytest.raises(ValidationError, match="Required Observability"):
        AssessmentSituation.model_validate(value)
    value["qa_result"] = "FAIL"
    assert AssessmentSituation.model_validate(value).qa_result == "FAIL"


def test_duplicate_indicator_and_scalar_indicator_are_rejected():
    value = situation()
    value["observability"].append(copy.deepcopy(value["observability"][0]))
    with pytest.raises(ValidationError, match="Duplicate AS IndicatorID"):
        AssessmentSituation.model_validate(value)
    value = situation()
    value["indicator_id"] = "K4.I02"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AssessmentSituation.model_validate(value)


def test_static_report_cannot_claim_runtime_success():
    report = verify_directory(OUTPUT)
    report["runtime_execution"] = "PASS"
    with pytest.raises(ValidationError, match="cannot confirm runtime"):
        VerificationReport.model_validate(report)


def test_write_is_deterministic_and_verifies_saved_files(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for directory in (first, second):
        write_package(package(), provenance(), directory)
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}
    (second / "case-package.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_directory(second)


def test_writer_refuses_published_destination_before_writing(tmp_path):
    (tmp_path / "manifest.json").write_text('{"status":"published"}')
    with pytest.raises(ValueError, match="non-draft"):
        write_package(package(), provenance(), tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / "manifest.json"]


def test_verifier_rejects_missing_artifacts(tmp_path):
    write_package(package(), provenance(), tmp_path)
    (tmp_path / "assessment-situation.schema.json").unlink()
    with pytest.raises(ValueError, match="inventory mismatch"):
        verify_directory(tmp_path)


def xlsx_bytes(sheets):
    # Минимальный OOXML, независимый от Office и внешних библиотек.
    from xml.sax.saxutils import escape
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + ''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="r{i}"/>' for i, name in enumerate(sheets, 1)) + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships>' + ''.join(f'<Relationship Id="r{i}" Target="/xl/worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + '</Relationships>')
        for i, rows in enumerate(sheets.values(), 1):
            body = []
            for row in rows:
                cells = []
                for col, value in row["cells"].items():
                    ref = f'{col}{row["row"]}'
                    if isinstance(value, (int, float)):
                        cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                    else:
                        cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
                body.append(f'<row r="{row["row"]}">' + ''.join(cells) + '</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(body) + '</sheetData></worksheet>')
    return output.getvalue()


def test_full_import_from_portable_synthetic_office_container(tmp_path):
    from xml.sax.saxutils import escape
    source = provenance()
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, sheets in source["source_workbooks"].items():
            z.writestr(name, xlsx_bytes(sheets))
        for name, text in source["source_texts"].items():
            if name.endswith(".md"):
                z.writestr(name, text)
            else:
                doc = io.BytesIO()
                with zipfile.ZipFile(doc, "w") as inner:
                    inner.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + escape(text) + '</w:t></w:r></w:p></w:body></w:document>')
                z.writestr(name, doc.getvalue())
    imported, metadata = build_package(archive)
    assert imported == package()
    assert metadata["source_workbooks"] == source["source_workbooks"]
    assert len(metadata["sources"]) == 5


def test_ooxml_reader_preserves_newlines_sparse_cells_and_numeric_time():
    sheets = {"Тест": [{"row": 3, "cells": {"A": "Первая\nвторая", "U": 8}}]}
    assert read_xlsx(xlsx_bytes(sheets)) == sheets

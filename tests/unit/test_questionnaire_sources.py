from pathlib import Path

import pytest

from Api.questionnaire_sources import (
    PARTICIPANT_QUESTIONS, PARTICIPANT_QUESTION_SCHEMA, normalize_answers, parse_csv, public_revision,
)


EXAMPLE = Path("assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv")


def test_csv_example_is_ready_and_preserves_non_w02_answers():
    result = parse_csv(EXAMPLE.read_text())
    assert result["status"] == "ready_for_confirmation"
    assert result["answers"]["C01"]["name"] == "Синтетическая организация"
    assert result["answers"]["C05"]["answer"].startswith("Синтетический")


def test_c22_is_preserved_but_not_used_as_server_confirmation():
    result = parse_csv(EXAMPLE.read_text() + '\nC22,answer,"да"\n')
    assert result["status"] == "ready_for_confirmation"
    assert result["answers"]["C22"]["answer"] == "да"


def test_bom_semicolon_quotes_and_line_breaks_are_supported():
    text = EXAMPLE.read_text().replace(",", ";", 1)
    text = "\ufeff" + text.replace(",", ";")
    result = parse_csv(text)
    assert result["delimiter"] == ";"
    assert not result["errors"]


def test_conflicting_duplicate_is_reported_without_last_write_wins():
    text = EXAMPLE.read_text() + '\nC01,name,"Другое название"\n'
    result = parse_csv(text)
    assert result["status"] == "invalid"
    assert result["answers"]["C01"]["name"] == "Синтетическая организация"
    assert result["errors"][-1]["code"] == "CONFLICTING_VALUE"


def test_all_adapters_use_same_normalized_contract():
    csv_result = parse_csv(EXAMPLE.read_text())
    external = normalize_answers(answers=csv_result["answers"], channel="external_form")
    product = normalize_answers(answers=csv_result["answers"], channel="product_form")
    assert external["answers"] == product["answers"] == csv_result["answers"]


def test_header_must_be_exact():
    with pytest.raises(ValueError, match="QUESTIONNAIRE_HEADER_INVALID"):
        parse_csv("field,question_id,value\nname,C01,Example")


def test_canonical_participant_questions_are_not_customer_authored():
    assert len(PARTICIPANT_QUESTIONS) == 3
    assert all(question.strip().endswith("?") for question in PARTICIPANT_QUESTIONS)
    assert PARTICIPANT_QUESTION_SCHEMA == {
        "variant": "corporate", "version": "1.0", "questions": [
            {"key": "work_situations", "text": PARTICIPANT_QUESTIONS[0]},
            {"key": "decision_situations", "text": PARTICIPANT_QUESTIONS[1]},
            {"key": "constraints_interactions", "text": PARTICIPANT_QUESTIONS[2]},
        ],
    }


def test_public_preview_has_participant_projection_and_safe_diff():
    current = parse_csv(EXAMPLE.read_text())["answers"]
    proposed = {**current, "C02a": {"participant_text": "Новая цель"}}
    row = {"id": 2, "assignment_ref": "assessment-a", "status": "ready_for_confirmation",
           "channel": "csv", "validation_json": {}, "answers_json": proposed, "confirmed_at": None}
    confirmed = {"answers_json": current}
    result = public_revision(row, confirmed_row=confirmed)
    assert result["participant_preview"]["purpose"] == "Новая цель"
    assert result["changes"] == [{
        "field": "purpose",
        "before": current["C02a"]["participant_text"],
        "after": "Новая цель",
    }]
    assert "questionnaire_revision_id" not in result["participant_preview"]
    assert "briefing" not in result

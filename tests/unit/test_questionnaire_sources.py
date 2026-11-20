from pathlib import Path

import pytest

from Api.questionnaire_sources import (
    PARTICIPANT_QUESTIONS, PARTICIPANT_QUESTION_SCHEMA, admin_assignment_readiness,
    normalize_answers, parse_csv, public_revision, template_csv,
)
from Api import questionnaire_sources


EXAMPLE = Path("assessment_definitions/questionnaires/corporate/0.2/example.synthetic.csv")


def test_csv_example_is_ready_and_preserves_non_w02_answers():
    result = parse_csv(EXAMPLE.read_text())
    assert result["status"] == "ready_for_confirmation"
    assert result["answers"]["C01"]["name"] == "Синтетическая организация"
    assert result["answers"]["C05"]["answer"].startswith("Синтетический")
    assert "C04" not in result["answers"]
    assert "responsible_contact" not in result["answers"]["C21"]


def test_c21_is_optional_for_new_csv_and_product_form():
    without_organizer = "\n".join(
        line for line in EXAMPLE.read_text().splitlines() if not line.startswith("C21,")
    ) + "\n"
    csv_result = parse_csv(without_organizer)
    assert csv_result["status"] == "ready_for_confirmation"
    assert "C21" not in csv_result["answers"]
    product = normalize_answers(answers=csv_result["answers"], channel="product_form")
    assert product["status"] == "ready_for_confirmation"


def test_c22_is_preserved_but_not_used_as_server_confirmation():
    result = parse_csv(EXAMPLE.read_text() + '\nC22,answer,"да"\n')
    assert result["status"] == "ready_for_confirmation"
    assert result["answers"]["C22"]["answer"] == "да"


def test_old_csv_and_draft_ignore_removed_fields_without_loosening_other_validation():
    old_csv = Path("assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv").read_text()
    parsed = parse_csv(old_csv)
    assert parsed["status"] == "ready_for_confirmation"
    assert parsed["answers"] == parse_csv(EXAMPLE.read_text())["answers"]
    assert "C04,answer" not in template_csv()
    assert "C21,responsible_contact" not in template_csv()
    old_draft = {"id": 5, "assignment_ref": "assessment-a", "status": "draft", "channel": "csv",
                 "answers_json": parsed["answers"], "raw_source_text": old_csv,
                 "validation_json": {"missing": ["C04.answer", "C21.responsible_contact"], "errors": []}}
    assert public_revision(old_draft)["status"] == "ready_for_confirmation"
    bad = {**old_draft, "raw_source_text": old_csv + 'C99,answer,"unknown"\n'}
    assert public_revision(bad)["status"] == "invalid"


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


@pytest.mark.parametrize("field", ["case_reality_level", "organization_name_usage_rules"])
@pytest.mark.parametrize("channel", ["csv", "product_form", "external_form"])
def test_unknown_context_choice_is_invalid_and_preserves_answer(field, channel):
    source = EXAMPLE.read_text()
    original = parse_csv(source)["answers"]["C17"][field]
    invalid = "Неизвестный вариант"
    if channel == "csv":
        result = parse_csv(source.replace("C17," + field + "," + original,
                                          "C17," + field + "," + invalid))
    else:
        answers = parse_csv(source)["answers"]
        answers["C17"][field] = invalid
        result = normalize_answers(answers=answers, channel=channel)
    assert result["status"] == "invalid"
    assert result["answers"]["C17"][field] == invalid
    assert any(error["code"] == "CONTEXT_CHOICE_UNSUPPORTED" and error["field"] == field
               for error in result["errors"])


def test_approved_and_legacy_context_choices_have_verified_provenance(monkeypatch):
    answers = parse_csv(EXAMPLE.read_text())["answers"]
    assert parse_csv(EXAMPLE.read_text())["applied_policy"]["legacy_context_choices"]["version"] == "1.0"
    answers["C17"] = {
        "case_reality_level": "Близко к реальной работе",
        "organization_name_usage_rules": "Использовать условное название",
    }
    result = normalize_answers(answers=answers, channel="product_form")
    assert result["status"] == "ready_for_confirmation"
    assert "legacy_context_choices" not in result["applied_policy"]
    monkeypatch.setattr(questionnaire_sources, "ADMIN_CHOICES_PACKAGE", Path("/nonexistent-policy"))
    with pytest.raises(ValueError, match="ADMIN_CONTEXT_CHOICES_UNAVAILABLE"):
        normalize_answers(answers=answers, channel="product_form")


def test_missing_legacy_compatibility_policy_rejects_new_preview(monkeypatch):
    answers = parse_csv(EXAMPLE.read_text())["answers"]
    monkeypatch.setattr(questionnaire_sources, "LEGACY_CHOICES_PACKAGE", Path("/nonexistent-policy"))
    with pytest.raises(ValueError, match="QUESTIONNAIRE_LEGACY_CHOICES_UNAVAILABLE"):
        normalize_answers(answers=answers, channel="product_form")


def test_historical_confirmed_revision_remains_readable_without_current_policy(monkeypatch):
    answers = parse_csv(EXAMPLE.read_text())["answers"]
    answers["C04"] = {"answer": "Историческое поле"}
    answers["C21"]["responsible_contact"] = "old@example.test"
    monkeypatch.setattr(questionnaire_sources, "ADMIN_CHOICES_PACKAGE", Path("/nonexistent-policy"))
    row = {"id": 5, "assignment_ref": "old", "status": "confirmed", "channel": "csv",
           "answers_json": answers, "confirmed_at": "2026-11-01T10:00:00Z"}
    saved = public_revision(row)
    assert saved["status"] == "confirmed"
    assert saved["answers_json"]["C17"]["case_reality_level"] == "обобщённый"
    assert "C04" not in saved["answers_json"]
    assert "responsible_contact" not in saved["answers_json"]["C21"]


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
           "source_author": "Синтетический заказчик",
           "channel": "csv", "validation_json": {}, "answers_json": proposed, "confirmed_at": None}
    confirmed = {"id": 1, "assignment_ref": "assessment-a", "answers_json": current}
    result = public_revision(row, confirmed_row=confirmed)
    assert result["participant_preview"]["purpose"] == "Новая цель"
    assert result["changes"] == [{
        "field": "purpose",
        "before": current["C02a"]["participant_text"],
        "after": "Новая цель",
    }]
    assert "questionnaire_revision_id" not in result["participant_preview"]
    assert "briefing" not in result
    assert result["source_author"] == "Синтетический заказчик"


def test_legacy_recipient_fields_are_absent_from_new_projection():
    answers = parse_csv(EXAMPLE.read_text())["answers"]
    answers["C04"] = {"answer": "Результаты увидит только участник"}
    answers["C21"]["responsible_contact"] = "old@example.test"
    row = {"id": 3, "assignment_ref": "assessment-a", "status": "ready_for_confirmation",
           "channel": "csv", "validation_json": {}, "answers_json": answers, "confirmed_at": None,
           "recipient_mapping_json": ["participant", "organization_admin"]}
    result = public_revision(row)
    assert "result_recipients" not in result["participant_preview"]
    assert "recipient_mapping" not in result
    assert "recipient_user_ids" not in result
    assert "C04" not in result["answers_json"]
    assert "responsible_contact" not in result["answers_json"]["C21"]


class _One:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


class _ReadinessConnection:
    def __init__(self, *, confirmed=False, latest=None, total=0, ready=0, in_progress=0):
        self.confirmed = confirmed
        self.latest = latest
        self.total = total
        self.ready = ready
        self.in_progress = in_progress

    def execute(self, query, _params=()):
        if "FROM questionnaire_response_revisions" in query and "briefing_json" in query:
            return _One({
                "id": 7, "assignment_ref": "assessment-a", "confirmed_at": "now",
                "organization_context_version_id": 11,
                "briefing_json": {"purpose": "Цель", "organizer": "HR", "responsible_contact": "hr@example.test",
                                  "results_usage": "Развитие", "result_recipients": "Участник"},
            } if self.confirmed else None)
        if "SELECT status FROM questionnaire_response_revisions" in query:
            return _One({"status": self.latest} if self.latest else None)
        if "SELECT DISTINCT u.id AS user_id" in query:
            assert _params == (3, "assessment-a", "assessment-a")
            return _Many([{"user_id": number + 1} for number in range(self.total)])
        raise AssertionError(query)


class _Many:
    def __init__(self, value):
        self.value = value

    def fetchall(self):
        return self.value


@pytest.fixture
def assigned_sources(monkeypatch):
    monkeypatch.setattr("Api.assessment_assignment_sources.schema_available", lambda _: True)
    monkeypatch.setattr("Api.assessment_assignment_sources.participant_binding",
        lambda connection, **kw: {"assignment_id": kw["user_id"], "questionnaire_revision_id": 7}
            if connection.confirmed else None)
    monkeypatch.setattr("Api.admin_assignment_projection.preparation_for_assignment",
        lambda connection, **kw: {"status": "running" if kw["assignment_id"] <= connection.in_progress else None})


def test_admin_readiness_distinguishes_missing_draft_roles_and_preparation(monkeypatch, assigned_sources):
    def fake_late_readiness(connection, *, user_id, readiness):
        if readiness["status"] != "ready":
            return {"status": "waiting_for_assessment_data", "reason": readiness["reason"]}
        assert readiness["organization_context_version_id"] == 11
        assert readiness["assignment_ref"] == "assessment-a"
        return {
            "status": "ready_to_prepare" if user_id <= connection.ready else "waiting_for_assessment_data",
            "reason": None if user_id <= connection.ready else "W02_ANSWERS_NOT_BOUND",
        }

    monkeypatch.setattr("Api.acquaintance.late_readiness", fake_late_readiness)
    missing = admin_assignment_readiness(_ReadinessConnection(), organization_id=3, assignment_ref="assessment-a")
    assert missing["early"]["status"] == "data_missing"
    assert missing["roles"]["status"] == "not_started"

    draft = admin_assignment_readiness(
        _ReadinessConnection(latest="ready_for_confirmation", total=2, ready=1),
        organization_id=3, assignment_ref="assessment-a",
    )
    assert draft["early"]["status"] == "draft_unconfirmed"
    assert draft["roles"]["status"] == "incomplete"
    assert draft["roles"]["ready"] == 0
    assert draft["roles"]["reasons"] == {"profile_binding": 2}
    assert draft["roles"]["action_view"] == "people"


    incomplete = admin_assignment_readiness(
        _ReadinessConnection(confirmed=True, total=2, ready=1),
        organization_id=3, assignment_ref="assessment-a",
    )
    assert incomplete["early"]["status"] == "ready"
    assert incomplete["roles"]["status"] == "incomplete"
    assert incomplete["roles"]["ready"] == 1

    ready = admin_assignment_readiness(
        _ReadinessConnection(confirmed=True, total=2, ready=2, in_progress=1),
        organization_id=3, assignment_ref="assessment-a",
    )
    assert ready["early"]["status"] == "ready"
    assert ready["context"]["status"] == "ready"
    assert ready["roles"]["status"] == "ready"
    assert ready["status"] == "preparing"


def test_admin_readiness_preserves_late_reasons_and_actions(monkeypatch, assigned_sources):
    reasons = {
        1: "W02_ANSWERS_NOT_BOUND",
        2: "M4_PROFILE_SCOPE_MISMATCH: stale",
        3: "M4_CHECKSUM_MISMATCH: invalid",
    }

    def fake_late_readiness(_connection, *, user_id, readiness):
        assert readiness["assignment_ref"] == "assessment-a"
        return {"status": "waiting_for_assessment_data", "reason": reasons[user_id]}

    monkeypatch.setattr("Api.acquaintance.late_readiness", fake_late_readiness)
    result = admin_assignment_readiness(
        _ReadinessConnection(confirmed=True, total=3),
        organization_id=3, assignment_ref="assessment-a",
    )
    assert result["roles"]["reasons"] == {
        "acquaintance_wait": 1,
        "profile_binding": 1,
        "verification_error": 1,
    }
    assert result["roles"]["action_view"] == "people"
    assert "ожидается завершение знакомства: 1" in result["roles"]["message"]
    assert "связку профиля и роли: 1" in result["roles"]["message"]
    assert "ошибка проверки готовности: 1" in result["roles"]["message"]

from pathlib import Path

import pytest

from Api.questionnaire_sources import (
    PARTICIPANT_QUESTIONS, PARTICIPANT_QUESTION_SCHEMA, admin_assignment_readiness,
    normalize_answers, parse_csv, public_revision, recipient_access_projection,
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
           "source_author": "Синтетический заказчик",
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
    assert result["source_author"] == "Синтетический заказчик"


def test_recipient_projection_ignores_contradictory_free_text():
    answers = parse_csv(EXAMPLE.read_text())["answers"]
    answers["C04"]["answer"] = "Результаты увидит только участник"
    row = {"id": 3, "assignment_ref": "assessment-a", "status": "ready_for_confirmation",
           "channel": "csv", "validation_json": {}, "answers_json": answers, "confirmed_at": None,
           "recipient_mapping_json": ["participant", "organization_admin"]}
    result = public_revision(row)
    assert result["participant_preview"]["result_recipients"] == (
        "Результаты доступны участнику и выбранным представителям заказчика."
    )
    assert recipient_access_projection(["participant"])["result_recipients"] == (
        "Результаты доступны только участнику."
    )


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
        if "assessment_preparation_jobs" in query:
            assert _params == (3, "assessment-a", "assessment-a")
            return _One({"in_progress": self.in_progress})
        if "SELECT DISTINCT u.id AS user_id" in query:
            assert _params == (3, "assessment-a", "assessment-a")
            return _Many([{"user_id": number + 1} for number in range(self.total)])
        if "participant_acquaintance_confirmations" in query:
            user_id = int(_params[0])
            return _One({"personalized_profile_id": user_id} if user_id <= self.ready else None)
        raise AssertionError(query)


class _Many:
    def __init__(self, value):
        self.value = value

    def fetchall(self):
        return self.value


def test_admin_readiness_distinguishes_missing_draft_roles_and_preparation(monkeypatch):
    def fake_late_readiness(connection, *, user_id, readiness):
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
    assert draft["roles"] == {
        "status": "incomplete", "message": "Готовность участников будет проверена после подтверждения ранних сведений.",
        "ready": 0, "total": 2, "reasons": {}, "action_view": "organization-data",
    }

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


def test_admin_readiness_preserves_late_reasons_and_actions(monkeypatch):
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

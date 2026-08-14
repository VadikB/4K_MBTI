from __future__ import annotations

import json

from Api.assessment.interview import InterviewerService, InterviewerTurnResult


class FakeGateway:
    def __init__(
        self,
        *,
        enabled: bool,
        response: str = "",
        responses: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.enabled = enabled
        self.response = response
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[tuple[list[dict[str, str]], float]] = []

    def chat(self, messages, *, temperature=0.3, timeout_seconds=120, routing_key=None):
        self.calls.append((messages, temperature))
        if self.error:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        return self.response


class FakePolicy:
    def __init__(self) -> None:
        self.manual_fallback = InterviewerTurnResult("manual fallback", True, "completed", None, "")
        self.timeout_fallback = InterviewerTurnResult("timeout fallback", True, "timeout", None, "")

    def _fallback_manual_finish_turn(self, **_kwargs):
        return self.manual_fallback

    def _fallback_timeout_turn(self, **_kwargs):
        return self.timeout_fallback

    def _get_interviewer_prompt_text(self, prompt_code, fallback_text, *, prompt_snapshot=None):
        prompts = dict((prompt_snapshot or {}).get("prompts") or {}).get("interviewer", {})
        return str(dict(prompts.get(prompt_code) or {}).get("text") or fallback_text)

    def _parse_json(self, raw):
        return json.loads(raw)

    def _sanitize_interviewer_message(self, text):
        return text.strip()

    def _extract_dialog_assistant_message(self, raw):
        return raw

    def _looks_like_dialog_meta_response(self, text):
        return text.startswith("META:")

    def _build_dialog_forbidden_drift(self, **_kwargs):
        return ["foreign"]

    def _looks_like_dialog_domain_drift(self, text, forbidden):
        return any(item in text for item in forbidden)


class FakeDialogPolicy:
    def looks_like_meta_response(self, text):
        return text.startswith("META:")

    def looks_like_domain_drift(self, text, forbidden):
        return any(item.strip() in text for item in forbidden.split(",") if item.strip())


def test_manual_finish_uses_fallback_without_llm() -> None:
    gateway = FakeGateway(enabled=False)
    policy = FakePolicy()

    result = InterviewerService(gateway=gateway).build_manual_finish_turn(
        policy=policy,
        system_prompt="system",
        dialogue=[],
        case_title="Case",
        case_skills=["K"],
    )

    assert result is policy.manual_fallback
    assert gateway.calls == []


def test_manual_finish_uses_prompt_from_immutable_snapshot() -> None:
    gateway = FakeGateway(enabled=True, response='{"assistant_message":"  Готово  ","result_status":"completed"}')
    snapshot = {"prompts": {"interviewer": {"manual_finish": {"text": "frozen instruction"}}}}

    result = InterviewerService(gateway=gateway).build_manual_finish_turn(
        policy=FakePolicy(),
        system_prompt="system",
        dialogue=[{"role": "user", "content": "finish"}],
        case_title="Case",
        case_skills=["K"],
        prompt_snapshot=snapshot,
    )

    assert result.assistant_message == "Готово"
    assert result.result_status == "completed"
    assert gateway.calls[0][0][1] == {"role": "system", "content": "frozen instruction"}
    assert gateway.calls[0][1] == 0.2


def test_timeout_returns_fallback_when_llm_fails() -> None:
    gateway = FakeGateway(enabled=True, error=RuntimeError("unavailable"))
    policy = FakePolicy()

    result = InterviewerService(gateway=gateway).build_timeout_turn(
        policy=policy,
        system_prompt="system",
        dialogue=[],
        case_title="Case",
    )

    assert result is policy.timeout_fallback


def test_execute_regular_case_turn_parses_json_response() -> None:
    gateway = FakeGateway(enabled=True, response='{"assistant_message":"  Следующий вопрос?  "}')
    fallback = InterviewerTurnResult("fallback", False, "in_progress", None, "")

    result = InterviewerService(gateway=gateway, dialog_policy=FakeDialogPolicy()).execute_case_turn(
        policy=FakePolicy(),
        messages=[{"role": "system", "content": "prompt"}],
        fallback=fallback,
        dialog_case_mode=False,
        routing_key="user:42",
        system_prompt="system",
        company_industry=None,
        user_profile=None,
    )

    assert result.assistant_message == "Следующий вопрос?"
    assert result.result_status == "in_progress"
    assert gateway.calls[0][1] == 0.35


def test_execute_dialog_case_retries_meta_response_in_role() -> None:
    gateway = FakeGateway(enabled=True, responses=["META: analysis", "Рабочая реплика"])
    fallback = InterviewerTurnResult("fallback", False, "in_progress", None, "")

    result = InterviewerService(gateway=gateway, dialog_policy=FakeDialogPolicy()).execute_case_turn(
        policy=FakePolicy(),
        messages=[{"role": "system", "content": "prompt"}],
        fallback=fallback,
        dialog_case_mode=True,
        routing_key="dialog:case",
        system_prompt="system",
        company_industry="industry",
        user_profile={},
    )

    assert result.assistant_message == "Рабочая реплика"
    assert [call[1] for call in gateway.calls] == [0.6, 0.45]
    assert "вышел из роли" in gateway.calls[1][0][-1]["content"]


def test_execute_dialog_case_raises_after_persistent_domain_drift() -> None:
    gateway = FakeGateway(enabled=True, responses=["кандидаты", "кандидаты снова"])
    fallback = InterviewerTurnResult("fallback", False, "in_progress", None, "")

    try:
        InterviewerService(gateway=gateway, dialog_policy=FakeDialogPolicy()).execute_case_turn(
            policy=FakePolicy(),
            messages=[{"role": "system", "content": "prompt"}],
            fallback=fallback,
            dialog_case_mode=True,
            routing_key="dialog:case",
            system_prompt="Инцидент в Service Desk",
            company_industry="industry",
            user_profile={},
        )
    except RuntimeError as exc:
        assert "dialog generation failed" in str(exc)
        assert "domain drift" in str(exc)
    else:
        raise AssertionError("Persistent domain drift must fail a dialog turn")

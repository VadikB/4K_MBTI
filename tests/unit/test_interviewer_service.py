from __future__ import annotations

import json

from Api.assessment.interview import InterviewerService, InterviewerTurnResult


class FakeGateway:
    def __init__(self, *, enabled: bool, response: str = "", error: Exception | None = None) -> None:
        self.enabled = enabled
        self.response = response
        self.error = error
        self.calls: list[tuple[list[dict[str, str]], float]] = []

    def chat(self, messages, *, temperature=0.3, timeout_seconds=120, routing_key=None):
        self.calls.append((messages, temperature))
        if self.error:
            raise self.error
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

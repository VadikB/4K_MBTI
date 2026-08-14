from __future__ import annotations

from typing import Any, Protocol

from Api.assessment.interview.contracts import InterviewerTurnResult
from Api.llm.contracts import LlmMessage


class InterviewGateway(Protocol):
    @property
    def enabled(self) -> bool: ...

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        temperature: float = 0.3,
        timeout_seconds: int = 120,
        routing_key: str | None = None,
    ) -> str: ...


class InterviewerService:
    """Runs interviewer use cases independently from a concrete LLM client facade."""

    def __init__(self, *, gateway: InterviewGateway) -> None:
        self.gateway = gateway

    def build_manual_finish_turn(
        self,
        *,
        policy: Any,
        system_prompt: str,
        dialogue: list[dict[str, str]],
        case_title: str,
        case_skills: list[str],
        prompt_snapshot: dict[str, Any] | None = None,
    ) -> InterviewerTurnResult:
        fallback = policy._fallback_manual_finish_turn(
            case_title=case_title,
            dialogue=dialogue,
            case_skills=case_skills,
        )
        if not self.gateway.enabled:
            return fallback

        fallback_instruction = (
            "Пользователь нажал кнопку завершения кейса. "
            "Нужно только вежливо сообщить, что кейс завершен и диалог сохранен в системе. "
            "Верни JSON-объект только с полем assistant_message."
        )
        instruction = policy._get_interviewer_prompt_text(
            "manual_finish",
            fallback_instruction,
            prompt_snapshot=prompt_snapshot,
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "system", "content": instruction}, *dialogue]
        try:
            parsed = policy._parse_json(self.gateway.chat(messages, temperature=0.2))
            return InterviewerTurnResult(
                assistant_message=policy._sanitize_interviewer_message(
                    str(parsed.get("assistant_message") or fallback.assistant_message)
                ),
                is_case_complete=True,
                result_status=str(parsed.get("result_status") or fallback.result_status),
                completion_score=None,
                evaluator_summary="",
            )
        except Exception:
            return fallback

    def build_timeout_turn(
        self,
        *,
        policy: Any,
        system_prompt: str,
        dialogue: list[dict[str, str]],
        case_title: str,
        prompt_snapshot: dict[str, Any] | None = None,
    ) -> InterviewerTurnResult:
        fallback = policy._fallback_timeout_turn(case_title=case_title, dialogue=dialogue)
        if not self.gateway.enabled:
            return fallback

        fallback_instruction = (
            "Время на прохождение кейса закончилось. "
            "Нужно только сообщить, что кейс завершен из-за окончания времени, а диалог сохранен в системе. "
            "Верни JSON-объект только с полем assistant_message."
        )
        instruction = policy._get_interviewer_prompt_text(
            "timeout_finish",
            fallback_instruction,
            prompt_snapshot=prompt_snapshot,
        )
        messages = [{"role": "system", "content": system_prompt}, {"role": "system", "content": instruction}, *dialogue]
        try:
            parsed = policy._parse_json(self.gateway.chat(messages, temperature=0.2))
            return InterviewerTurnResult(
                assistant_message=policy._sanitize_interviewer_message(
                    str(parsed.get("assistant_message") or fallback.assistant_message)
                ),
                is_case_complete=True,
                result_status=str(parsed.get("result_status") or fallback.result_status),
                completion_score=None,
                evaluator_summary="",
            )
        except Exception:
            return fallback

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

    def execute_case_turn(
        self,
        *,
        policy: Any,
        messages: list[dict[str, str]],
        fallback: InterviewerTurnResult,
        dialog_case_mode: bool,
        routing_key: str,
        system_prompt: str,
        company_industry: str | None,
        user_profile: dict[str, Any] | None,
    ) -> InterviewerTurnResult:
        try:
            raw = self.gateway.chat(
                messages,
                temperature=0.6 if dialog_case_mode else 0.35,
                routing_key=routing_key,
            )
            if dialog_case_mode:
                assistant_message = policy._extract_dialog_assistant_message(raw)
                if policy._looks_like_dialog_meta_response(assistant_message):
                    retry_messages = [
                        *messages,
                        {
                            "role": "system",
                            "content": (
                                "Ты только что вышел из роли. "
                                "Не описывай пользователя, не объясняй свою внутреннюю логику, "
                                "не упоминай навыки, интервью, сценарий, оценку или контекст задания. "
                                "Сейчас верни одну короткую живую реплику собеседника внутри сцены кейса."
                            ),
                        },
                    ]
                    retry_raw = self.gateway.chat(retry_messages, temperature=0.45, routing_key=routing_key)
                    assistant_message = policy._extract_dialog_assistant_message(retry_raw)

                forbidden_drift = policy._build_dialog_forbidden_drift(
                    system_prompt=system_prompt,
                    company_industry=company_industry,
                    user_profile=user_profile,
                )
                if policy._looks_like_dialog_domain_drift(assistant_message, forbidden_drift):
                    retry_messages = [
                        *messages,
                        {
                            "role": "system",
                            "content": (
                                "Ты уехал в чужую предметную область. "
                                "Убери несоответствующие доменные сущности и верни реплику только в рамках этого кейса и профессионального контура."
                            ),
                        },
                    ]
                    retry_raw = self.gateway.chat(retry_messages, temperature=0.4, routing_key=routing_key)
                    assistant_message = policy._extract_dialog_assistant_message(retry_raw)
                if policy._looks_like_dialog_meta_response(assistant_message):
                    raise RuntimeError("DeepSeek returned dialog meta reasoning instead of an in-role reply.")
                if policy._looks_like_dialog_domain_drift(assistant_message, forbidden_drift):
                    raise RuntimeError("DeepSeek returned a dialog reply with domain drift.")
            else:
                parsed = policy._parse_json(raw)
                assistant_message = policy._sanitize_interviewer_message(
                    str(parsed.get("assistant_message") or fallback.assistant_message)
                )
            return InterviewerTurnResult(
                assistant_message=assistant_message,
                is_case_complete=False,
                result_status="in_progress",
                completion_score=None,
                evaluator_summary="",
            )
        except Exception as exc:
            if dialog_case_mode:
                raise RuntimeError(f"DeepSeek dialog generation failed: {exc}") from exc
            return fallback

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

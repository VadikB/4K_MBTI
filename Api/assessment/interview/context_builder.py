from __future__ import annotations

import re
from typing import Any

from Api.case_text_cleanup import cleanup_case_text
from Api.assessment.interview.state_machine import DialogStateMachine


class DialogContextBuilder:
    def __init__(self, *, state_machine: DialogStateMachine | None = None) -> None:
        self.state_machine = state_machine or DialogStateMachine()

    def build_runtime_context(
        self,
        *,
        policy: Any,
        system_prompt: str,
        dialogue: list[dict[str, str]],
    ) -> dict[str, Any]:
        scenario_text = " ".join(item["content"] for item in dialogue if item["role"] == "assistant")
        assistant_messages = [
            str(item["content"] or "").strip()
            for item in dialogue
            if item["role"] == "assistant" and str(item["content"] or "").strip()
        ]
        asked_stages: set[str] = set()
        for message in assistant_messages[-4:]:
            asked_stages.update(self.state_machine.infer_reply_stages(message))
        role = self.state_machine.infer_counterpart_role(f"{system_prompt}\n{scenario_text}")
        is_development_dialog = role == "employee" or any(
            marker in f"{system_prompt}\n{scenario_text}".lower()
            for marker in ("развивающ", "план развития", "план роста", "зона роста", "обратной связ")
        )
        plan = self.state_machine.stage_plan(
            counterpart_role=role,
            is_development_dialog=is_development_dialog,
        )
        next_stage = next((stage for stage in plan if stage not in asked_stages), None)
        return {
            "counterpart_role": role,
            "is_development_dialog": is_development_dialog,
            "asked_stages": asked_stages,
            "next_stage": next_stage,
            "next_stage_label": self.state_machine.stage_label(next_stage),
            "stage_plan": list(plan),
        }

    @staticmethod
    def build_scene_anchor(*, system_prompt: str, case_title: str | None) -> str:
        source = re.sub(r"\s+", " ", cleanup_case_text(system_prompt or "")).strip()
        anchor_parts: list[str] = []
        if str(case_title or "").strip():
            anchor_parts.append(f"Кейс: {str(case_title).strip()}.")

        sections = (
            (r"(?:Сценарий кейса\s*)?(?:Ситуация\s*:?\s*)(.*?)(?=(?:Что известно|Что ограничивает|Что нужно сделать)\s*:?)", "Ситуация"),
            (r"(?:Что известно\s*:?\s*)(.*?)(?=(?:Что ограничивает|Что нужно сделать)\s*:?)", "Что известно"),
            (r"(?:Что ограничивает\s*:?\s*)(.*?)(?=(?:Что нужно сделать)\s*:?)", "Ограничения"),
            (r"(?:Что нужно сделать\s*:?\s*)(.*)$", "Цель разговора"),
        )
        for pattern, label in sections:
            match = re.search(pattern, source, flags=re.IGNORECASE | re.DOTALL)
            if match and match.group(1).strip():
                anchor_parts.append(f"{label}: {match.group(1).strip()}")
        if not anchor_parts and source:
            anchor_parts.append(source[:1200])
        return " ".join(anchor_parts)[:1800].strip()

    @staticmethod
    def build_domain_anchor(
        *,
        policy: Any,
        role_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        user_profile: dict[str, Any] | None,
    ) -> str:
        profile = dict(user_profile or {})
        context_vars = dict(profile.get("user_context_vars") or {})
        domain_profile = dict(context_vars.get("domain_profile") or {})
        domain_label = cleanup_case_text(
            str(
                context_vars.get("domain")
                or profile.get("user_domain")
                or domain_profile.get("domain_label")
                or company_industry
                or ""
            )
        ).strip()
        role_label = cleanup_case_text(str(role_name or position or "")).strip()

        def values(name: str, fallback_name: str) -> list[str]:
            return policy._normalize_string_list(
                context_vars.get(name) or profile.get(fallback_name) or domain_profile.get(name),
                fallback=[],
            )

        lines: list[str] = []
        if role_label:
            lines.append(f"Роль пользователя: {role_label}.")
        if domain_label:
            lines.append(f"Профессиональная область: {domain_label}.")
        for items, label, limit in (
            (values("systems", "user_systems"), "Типовые системы и контуры", 4),
            (values("artifacts", "user_artifacts"), "Типовые рабочие объекты", 4),
            (values("stakeholders", "user_stakeholders"), "Типовые участники взаимодействия", 4),
            (values("constraints", "user_constraints"), "Ограничения рабочей среды", 3),
        ):
            if items:
                lines.append(f"{label}: {', '.join(items[:limit])}.")
        if duties:
            lines.append(f"Описание работы пользователя: {cleanup_case_text(str(duties)).strip()}.")
        if not lines:
            return "Держись профессиональной области, заданной кейсом, и не уезжай в другой домен."
        lines.append(
            "Не подменяй эту профессиональную область другой сферой, не придумывай чужие процессы и участников вне указанного контура."
        )
        return " ".join(lines)[:1600]

    @staticmethod
    def build_forbidden_drift(
        *,
        system_prompt: str,
        company_industry: str | None,
        user_profile: dict[str, Any] | None,
    ) -> str:
        source = cleanup_case_text(
            " ".join(filter(None, [system_prompt, company_industry or "", str((user_profile or {}).get("user_domain") or "")]))
        ).lower()
        forbidden: list[str] = []

        def add(items: list[str]) -> None:
            for item in items:
                if item not in forbidden:
                    forbidden.append(item)

        if any(token in source for token in ("service desk", "sla", "ит", "поддержк", "инцидент", "заявк", "crm", "доступ")):
            add(["кандидаты", "офферы", "рекрутеры", "HR", "маркетинг", "бриф", "креатив", "юристы"])
        if any(token in source for token in ("подбор", "кандидат", "оффер", "hr")):
            add(["service desk", "инцидент", "SLA", "принтер", "CRM", "доступ к папке"])
        if any(token in source for token in ("финанс", "бюджет", "договор", "юрист")):
            add(["кандидаты", "офферы", "Service Desk", "инциденты"])
        if not forbidden:
            add(["чужой домен, не связанный со сценой кейса"])
        return ", ".join(forbidden)

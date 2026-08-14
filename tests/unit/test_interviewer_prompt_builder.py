from Api.assessment.interview.prompt_builder import (
    DIALOG_POLICY_INSTRUCTION,
    DIALOG_SYSTEM_PROMPT,
    InterviewerPromptBuilder,
)


class FakePolicy:
    def _build_dialog_llm_context(self, **_kwargs):
        return {"counterpart_role": "manager"}

    def _get_dialog_role_contract(self, role):
        return f"contract:{role}"

    def _build_dialog_scene_anchor(self, **_kwargs):
        return "scene"

    def _build_dialog_domain_anchor(self, **_kwargs):
        return "domain"

    def _build_dialog_forbidden_drift(self, **_kwargs):
        return "foreign"

    def _get_interviewer_prompt_text(self, prompt_code, fallback_text, *, prompt_snapshot=None, **values):
        prompt = dict((prompt_snapshot or {}).get("prompts") or {}).get("interviewer", {}).get(prompt_code, {})
        return str(prompt.get("text") or fallback_text).format(**values)

    def _infer_dialog_reply_stages(self, _text):
        return set()

    def _infer_dialog_counterpart_role_from_text(self, _text):
        return "manager"

    def _get_dialog_stage_plan(self, **_kwargs):
        return ("agreement", "closure")

    def _get_dialog_stage_label(self, stage):
        return str(stage or "")

    def _normalize_string_list(self, value, *, fallback):
        return list(value) if isinstance(value, list) else fallback


def build_messages(**overrides):
    values = {
        "policy": FakePolicy(),
        "system_prompt": "case system",
        "dialogue": [{"role": "user", "content": "answer"}],
        "case_title": "Case",
        "case_skills": ["K1"],
        "dialog_case_mode": False,
        "interactivity_mode": "interview",
        "format_control_rules": "brief",
        "recommended_answer_length": "short",
        "interviewer_prompt_override": None,
        "role_name": "Role",
        "position": "Position",
        "duties": "Duties",
        "company_industry": "Industry",
        "user_profile": {},
        "prompt_snapshot": None,
    }
    values.update(overrides)
    return InterviewerPromptBuilder().build_case_turn_messages(**values)


def test_follow_up_uses_frozen_snapshot_prompt() -> None:
    snapshot = {
        "prompts": {
            "interviewer": {
                "case_follow_up": {"text": "Frozen {skills} / {recommended_answer_length}"}
            }
        }
    }

    messages = build_messages(prompt_snapshot=snapshot)

    assert messages == [
        {"role": "system", "content": "case system"},
        {"role": "system", "content": "Frozen K1 / short"},
        {"role": "user", "content": "answer"},
    ]


def test_dialog_prompt_has_role_policy_and_case_anchors() -> None:
    messages = build_messages(dialog_case_mode=True, interactivity_mode="dialog")

    assert messages[0] == {"role": "system", "content": DIALOG_SYSTEM_PROMPT}
    assert messages[1] == {"role": "system", "content": DIALOG_POLICY_INSTRUCTION}
    assert "Ты руководитель или менеджер внутри рабочей сцены" in messages[2]["content"]
    assert "Якорь сцены: Кейс: Case." in messages[2]["content"]
    assert "Профессиональный контур пользователя: Роль пользователя: Role." in messages[2]["content"]
    assert messages[-1] == {"role": "user", "content": "answer"}


def test_explicit_prompt_override_takes_precedence() -> None:
    messages = build_messages(interviewer_prompt_override="Override for {skills}")

    assert messages[1] == {"role": "system", "content": "Override for K1"}

from Api.assessment.interview import DialogContextBuilder


class FakePolicy:
    def _infer_dialog_reply_stages(self, text):
        return {"root_cause"} if "почему" in text.lower() else set()

    def _infer_dialog_counterpart_role_from_text(self, text):
        return "employee" if "сотрудник" in text.lower() else "peer"

    def _get_dialog_stage_plan(self, *, counterpart_role, is_development_dialog):
        return ("root_cause", "agreement", "closure")

    def _get_dialog_stage_label(self, stage):
        return f"label:{stage}"

    def _normalize_string_list(self, value, *, fallback):
        if isinstance(value, list):
            return [str(item) for item in value]
        return fallback


def test_runtime_context_selects_first_unasked_stage() -> None:
    context = DialogContextBuilder().build_runtime_context(
        policy=FakePolicy(),
        system_prompt="Разговор с сотрудником",
        dialogue=[{"role": "assistant", "content": "Давайте разберем причину."}],
    )

    assert context["counterpart_role"] == "employee"
    assert context["is_development_dialog"] is True
    assert context["asked_stages"] == {"root_cause"}
    assert context["next_stage"] == "change_commitment"
    assert context["next_stage_label"] == "личное обязательство по изменению поведения"


def test_scene_anchor_extracts_methodological_sections() -> None:
    anchor = DialogContextBuilder.build_scene_anchor(
        system_prompt=(
            "Ситуация: задерживается релиз. "
            "Что известно: команда ждёт решение. "
            "Что ограничивает: срок завтра. "
            "Что нужно сделать: договориться о плане."
        ),
        case_title="Релиз",
    )

    assert anchor.startswith("Кейс: Релиз.")
    assert "Ситуация: задерживается релиз." in anchor
    assert "Ограничения: срок завтра." in anchor
    assert "Цель разговора: договориться о плане." in anchor


def test_domain_anchor_uses_profile_context_without_inventing_values() -> None:
    anchor = DialogContextBuilder.build_domain_anchor(
        policy=FakePolicy(),
        role_name="Руководитель поддержки",
        position=None,
        duties="Контролирует очередь обращений",
        company_industry="IT",
        user_profile={
            "user_context_vars": {
                "domain": "Техническая поддержка",
                "systems": ["Service Desk"],
                "stakeholders": ["Пользователи"],
            }
        },
    )

    assert "Роль пользователя: Руководитель поддержки." in anchor
    assert "Профессиональная область: Техническая поддержка." in anchor
    assert "Типовые системы и контуры: Service Desk." in anchor
    assert "Типовые участники взаимодействия: Пользователи." in anchor


def test_forbidden_drift_is_derived_from_case_domain() -> None:
    forbidden = DialogContextBuilder.build_forbidden_drift(
        system_prompt="Инцидент в Service Desk нарушил SLA",
        company_industry="IT",
        user_profile=None,
    )

    assert "кандидаты" in forbidden
    assert "маркетинг" in forbidden

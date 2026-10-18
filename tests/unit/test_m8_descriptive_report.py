import json

from Api.m8_descriptive_report import build_input, generate, load_package
from test_m8_recommendations import fixture


class Gateway:
    enabled = True

    def __init__(self, output):
        self.output = output
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps(self.output, ensure_ascii=False)


def inputs():
    payload, resolved = fixture()
    results = {
        "id": "results-1",
        "revision_id": payload.pop("results_revision_id"),
        "revision_no": 1,
        "cycle_id": payload["cycle_id"],
        "results": {
            **payload,
            "personalized_profile_snapshot": {
                "content": {
                    "user_context": {
                        "regular_tasks": ["Согласование сроков"],
                        "email": "private@example.invalid",
                    }
                }
            },
            "limitations": ["Проверка гипотез не наблюдалась."],
            "partial_result": None,
        },
    }
    return results, resolved


def valid_output():
    return {
        "summary": ["Участник прямо обозначил цель одной из сторон."],
        "claims": [
            {
                "kind": "explanation",
                "skill_ids": ["K1.1"],
                "basis_refs": ["ia-1"],
                "text": "Вывод основан на явно названной цели.",
                "limitations": ["Проверка предположений не наблюдалась."],
                "context_refs": ["user_context.regular_tasks"],
            },
            {
                "kind": "quote",
                "skill_ids": ["K1.1"],
                "basis_refs": ["ia-1"],
                "text": "Хочет согласовать срок",
                "limitations": [],
                "context_refs": [],
            },
        ],
    }


def test_package_and_grounded_description_are_versioned_and_pii_free():
    results, resolved = inputs()
    gateway = Gateway(valid_output())
    report = generate(results, resolved, gateway=gateway)

    assert load_package()["manifest"]["version"] == "1.0.0"
    assert report["status"] == "ready"
    assert report["claims"][1]["text"] == "Хочет согласовать срок"
    assert "private@example.invalid" not in str(report)
    assert gateway.calls[0][1]["temperature"] == 0
    assert gateway.calls[0][1]["response_format"] == {"type": "json_object"}


def test_input_uses_only_selected_frozen_context():
    results, resolved = inputs()
    model_input, allowed = build_input(results, resolved)

    assert model_input["context"] == [
        {"ref": "user_context.regular_tasks", "text": "Согласование сроков"}
    ]
    assert allowed["quotes"] == {"Хочет согласовать срок"}
    assert "email" not in str(model_input)


def test_forbidden_advice_and_unverified_references_fail_closed():
    results, resolved = inputs()
    cases = []
    advice = valid_output()
    advice["claims"][0]["text"] = "Вам следует попробовать упражнение."
    cases.append(advice)
    foreign_basis = valid_output()
    foreign_basis["claims"][0]["basis_refs"] = ["foreign"]
    cases.append(foreign_basis)
    changed_quote = valid_output()
    changed_quote["claims"][1]["text"] = "Изменённая цитата"
    cases.append(changed_quote)
    foreign_context = valid_output()
    foreign_context["claims"][0]["context_refs"] = ["user_context.email"]
    cases.append(foreign_context)

    for output in cases:
        report = generate(results, resolved, gateway=Gateway(output))
        assert report["status"] == "failed"
        assert report["claims"] == []
        assert report["failure_reason"] == "DESCRIPTION_GENERATION_FAILED"

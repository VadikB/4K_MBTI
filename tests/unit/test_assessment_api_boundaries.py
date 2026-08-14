from __future__ import annotations

import ast
from pathlib import Path

from Api.deepseek_client import DeepSeekClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_application_services_do_not_call_private_deepseek_api() -> None:
    violations: list[str] = []
    for relative_path in (
        "Api/assessment_service.py",
        "Api/agent.py",
        "Api/communication_agent.py",
        "Api/mbti_refinement_service.py",
        "Api/mbti/service.py",
    ):
        tree = ast.parse((PROJECT_ROOT / relative_path).read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "deepseek_client"
                and node.attr.startswith("_")
            ):
                violations.append(f"{relative_path}:{node.lineno}:{node.attr}")

    assert violations == []


def test_public_interviewer_api_delegates_to_components(monkeypatch) -> None:
    client = DeepSeekClient()
    monkeypatch.setattr(client, "_is_dialog_interactivity_mode", lambda value: value == "dialog")
    monkeypatch.setattr(client, "_infer_follow_up_topics_from_text", lambda _text: {"risks"})
    monkeypatch.setattr(client, "_infer_dialog_reply_stages", lambda _text: {"agreement"})

    assert client.is_dialog_mode("dialog") is True
    assert client.infer_follow_up_topics("text") == {"risks"}
    assert client.infer_dialog_reply_stages("text") == {"agreement"}


def test_public_case_generation_api_delegates_to_pipeline(monkeypatch) -> None:
    client = DeepSeekClient()
    monkeypatch.setattr(client, "_detect_domain_family", lambda **_kwargs: "it_support")
    monkeypatch.setattr(client, "_extract_placeholders", lambda _text: ["workflow_name"])
    monkeypatch.setattr(client, "_score_case_text_quality", lambda **_kwargs: {"score": 5})

    assert client.detect_domain_family(position="Support", duties=None, company_industry="IT") == "it_support"
    assert client.extract_personalization_placeholders("{workflow_name}") == ["workflow_name"]
    assert client.score_case_text_quality(case_type_code="F01") == {"score": 5}

from uuid import uuid4
import json
import shutil

import pytest

from Api.m5_generation_lab import GenerationRequest, build_generation_input, generate
import Api.m5_generation_lab as lab

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("role", ["team_lead", "project_product_process_manager"])
def test_generation_preserves_role_and_multiple_indicators(role):
    request = GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role)
    snapshot = build_generation_input(request)
    result = generate(snapshot)
    assert result["base_role"] == role
    assert len(result["observability"]) == 2
    assert snapshot["profile"]["authority"] in result["presentation"]
    assert result["methodological_qa"] == "NOT_RUN"
    assert not result["admitted_for_assessment"]


def test_role_projections_are_distinct_without_user_identity():
    inputs = [build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role))
              for role in ("team_lead", "project_product_process_manager")]
    assert inputs[0]["profile"]["authority"] != inputs[1]["profile"]["authority"]
    assert all("full_name" not in x["profile"] and "contacts" not in x["profile"] for x in inputs)


def test_llm_receives_no_hidden_facts_or_indicator_hints():
    class Gateway:
        enabled = True

        def chat(self, messages, **kwargs):
            assert "Скрытые факты" not in messages[1]["content"]
            assert "K4.I02" not in messages[1]["content"]
            assert "36/180" not in messages[1]["content"]
            return '{"presentation": "Учебная ситуация: после обновления число повторных обращений выросло с 5 до 15. Вы руководите поддержкой. Какие действия предпримете?"}'

    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead", mode="llm"))
    assert generate(snapshot, Gateway())["mode"] == "llm"


def test_llm_failure_does_not_silently_fallback_to_template():
    class Gateway:
        enabled = False

    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead", mode="llm"))
    with pytest.raises(RuntimeError, match="LLM_UNAVAILABLE"):
        generate(snapshot, Gateway())


def test_prompt_preserves_original_content_and_version():
    # Независимый checksum текста SYSTEM_PROMPT до переноса (commit c035e833).
    prompt = lab.load_lab_prompt()
    assert prompt["version"] == "m5-lab-v1"
    assert prompt["checksum"] == "2fdc4d51b1de715f601482d82d8f9d9986ae7240b45a1d1e3e6216df38ed9d44"
    assert lab.digest(prompt["text"].encode("utf-8")) == prompt["checksum"]
    assert prompt["artifact"]["scope"] == "laboratory_only"
    assert prompt["artifact"]["manifest_checksum"] == lab.digest((lab.PROMPT_PACKAGE / "manifest.json").read_bytes())


@pytest.fixture
def prompt_package(tmp_path, monkeypatch):
    path = tmp_path / "prompt"
    shutil.copytree(lab.PROMPT_PACKAGE, path)
    monkeypatch.setattr(lab, "PROMPT_PACKAGE", path)
    return path


@pytest.mark.parametrize("damage", ["missing_prompt", "missing_manifest", "invalid_json", "changed_text", "empty_text", "invalid_utf8", "missing_owner", "unsafe_path", "wrong_scope"])
def test_invalid_prompt_package_rejects_new_input(prompt_package, damage):
    prompt_path = prompt_package / "prompt.md"
    manifest_path = prompt_package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if damage.startswith("missing_") and damage != "missing_owner":
        (prompt_path if damage == "missing_prompt" else manifest_path).unlink()
    elif damage == "invalid_json":
        manifest_path.write_text("{")
    elif damage == "changed_text":
        prompt_path.write_text("Changed synthetic instruction")
    elif damage in {"empty_text", "invalid_utf8"}:
        content = b"  \n" if damage == "empty_text" else b"\xff"
        prompt_path.write_bytes(content)
        manifest["artifacts"][0]["sha256"] = lab.digest(content)
        manifest_path.write_text(json.dumps(manifest))
    else:
        if damage == "missing_owner":
            del manifest["owner"]
        elif damage == "unsafe_path":
            manifest["artifacts"][0]["name"] = "../prompt.md"
        else:
            manifest["scope"] = "assessment"
        manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(lab.LabPromptUnavailable, match="M5_PROMPT_PACKAGE_UNAVAILABLE"):
        build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead"))


@pytest.mark.parametrize("legacy", [False, True])
def test_saved_prompt_survives_package_replacement_and_removal(prompt_package, legacy):
    request = GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead", mode="llm")
    saved = json.loads(json.dumps(build_generation_input(request)))
    if legacy:
        del saved["prompt"]["artifact"]
    original = saved["prompt"]["text"]
    manifest_path = prompt_package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    replacement = "Synthetic replacement for a new test version."
    (prompt_package / "prompt.md").write_text(replacement)
    manifest["version"] = "synthetic-v2"
    manifest["artifacts"][0]["sha256"] = lab.digest(replacement.encode())
    manifest_path.write_text(json.dumps(manifest))
    new_snapshot = build_generation_input(request.model_copy(update={"run_id": uuid4()}))
    assert new_snapshot["prompt"]["text"] == replacement
    assert new_snapshot["prompt"]["version"] == "synthetic-v2"
    (prompt_package / "prompt.md").unlink()

    class Gateway:
        enabled = True

        def chat(self, messages, **kwargs):
            assert messages[0]["content"] == original
            return json.dumps({"presentation": "Synthetic presentation for the saved scenario. " * 3})

    assert generate(saved, Gateway())["mode"] == "llm"

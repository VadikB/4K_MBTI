"""Лаборатория M5: синтетические ролевые прогоны, без подбора M7 и допуска Case."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.build_m5_case_package import M3, OUTPUT, digest, json_bytes, verify_directory


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    case_id: Annotated[str, Field(pattern=r"^CASE-TDISC-0[1-5]$")]
    base_role: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    mode: Literal["template", "llm"] = "template"


class GeneratedPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation: Annotated[str, Field(min_length=80, max_length=8000)]


PROMPT_PACKAGE = Path(__file__).resolve().parents[1] / "assessment_definitions/prompts/m5_generation_lab/v1"


class LabPromptUnavailable(RuntimeError):
    pass


class PromptArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Literal["prompt.md"]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class LabPromptManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    version: Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")]
    status: Literal["draft"]
    scope: Literal["laboratory_only"]
    owner: Annotated[str, Field(pattern=r"\S")]
    source: Annotated[str, Field(pattern=r"\S")]
    artifacts: Annotated[list[PromptArtifact], Field(min_length=1, max_length=1)]


def load_lab_prompt() -> dict:
    """Проверить пакет для нового запуска; исполнение снимка файлов не читает."""
    try:
        manifest_bytes = (PROMPT_PACKAGE / "manifest.json").read_bytes()
        manifest = LabPromptManifest.model_validate_json(manifest_bytes)
        prompt_bytes = (PROMPT_PACKAGE / manifest.artifacts[0].name).read_bytes()
        text = prompt_bytes.decode("utf-8")
        checksum = digest(prompt_bytes)
        if not text.strip() or checksum != manifest.artifacts[0].sha256:
            raise ValueError("Invalid prompt artifact")
    except (OSError, ValueError) as exc:
        raise LabPromptUnavailable("M5_PROMPT_PACKAGE_UNAVAILABLE") from exc
    return {
        "version": manifest.version, "text": text, "checksum": checksum,
        "artifact": {**manifest.model_dump(), "manifest_checksum": digest(manifest_bytes)},
    }

gateway = DeepSeekGateway()


@lru_cache(maxsize=1)
def load_lab_package() -> dict:
    verify_directory(OUTPUT)
    return json.loads((OUTPUT / "case-package.json").read_text())


def ensure_lab_schema(connection) -> None:
    connection.execute("SELECT pg_advisory_xact_lock(501170027)")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS m5_generation_lab_runs (
            run_id UUID PRIMARY KEY,
            created_by BIGINT NOT NULL REFERENCES users(id),
            request_checksum TEXT NOT NULL,
            input_checksum TEXT NOT NULL,
            input_json JSONB NOT NULL,
            output_json JSONB,
            output_checksum TEXT,
            status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
            error_code TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    connection.execute("""
        CREATE OR REPLACE FUNCTION guard_m5_lab_run() RETURNS trigger AS $$
        BEGIN
            IF OLD.status <> 'running' OR
               NEW.run_id IS DISTINCT FROM OLD.run_id OR
               NEW.created_by IS DISTINCT FROM OLD.created_by OR
               NEW.request_checksum IS DISTINCT FROM OLD.request_checksum OR
               NEW.input_checksum IS DISTINCT FROM OLD.input_checksum OR
               NEW.input_json IS DISTINCT FROM OLD.input_json OR
               NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'M5 lab snapshot/result is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.execute("DROP TRIGGER IF EXISTS m5_lab_immutable ON m5_generation_lab_runs")
    connection.execute("""
        CREATE TRIGGER m5_lab_immutable BEFORE UPDATE ON m5_generation_lab_runs
        FOR EACH ROW EXECUTE FUNCTION guard_m5_lab_run()
    """)


def lab_catalog() -> dict:
    package = load_lab_package()
    roles = json.loads(M3.read_text())["base_roles"]
    codes = {c["base_role"] for c in package["cases"]}
    return {
        "source_status": "WORKING", "synthetic": True, "llm_available": gateway.enabled,
        "roles": [{"code": r["code"], "name": r["description"]["name"]} for r in roles if r["code"] in codes],
        "schema_version": package["schema_version"],
        "cases": [{"case_id": c["case_id"], "title": c["title"], "roles": [c["base_role"]],
                   "indicator_ids": [x["indicator_id"] for x in c["indicator_targets"]],
                   "admitted_for_assessment": False} for c in package["cases"]],
    }


def build_generation_input(request: GenerationRequest) -> dict:
    package = load_lab_package()
    case = next((c for c in package["cases"] if c["case_id"] == request.case_id), None)
    if case is None or request.base_role != case["base_role"]:
        raise ValueError("Case недоступен для выбранной роли")
    role = next(r for r in json.loads(M3.read_text())["base_roles"] if r["code"] == request.base_role)
    profile = {
        "kind": "synthetic_profile_projection", "source": "M3 BaseRole; not a PersonalizedProfile M4",
        "base_role": request.base_role, "role_name": role["description"]["name"],
        "responsibility_object": role["card"]["responsibility_object"],
        "authority": role["card"]["independent_authority"],
        "restrictions": role["card"]["role_constraints"],
    }
    # Это явно маркированная синтетическая проекция, не опубликованный профиль M4.
    return {
        "schema_version": 2, "run_id": str(request.run_id), "mode": request.mode,
        "synthetic": True, "admitted_for_assessment": False,
        "case": case, "case_checksum": digest(json_bytes(case)),
        "package_checksum": digest(json_bytes(package)),
        "profile": profile, "profile_checksum": digest(json_bytes(profile)),
        "scenario": case["scenario"],
        "observability": case["indicator_targets"],
        "prompt": load_lab_prompt(),
    }


def generate(input_snapshot: dict, llm=None) -> dict:
    started = monotonic()
    profile = input_snapshot["profile"]
    initial = input_snapshot["case"]["passport"]["InitialSituation"] + "\n\n" + input_snapshot["case"]["passport"]["Trigger"]
    llm_input = {"initial_presentation": initial, "role": profile}
    if input_snapshot["mode"] == "llm":
        active_gateway = llm or gateway
        if not active_gateway.enabled:
            raise RuntimeError("LLM_UNAVAILABLE")
        raw = active_gateway.chat(
            [{"role": "system", "content": input_snapshot["prompt"]["text"]},
             {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False)}],
            temperature=0.2, timeout_seconds=90, routing_key="m5-lab:" + input_snapshot["run_id"],
        )
        presentation = GeneratedPresentation.model_validate_json(raw).presentation
    else:
        presentation = "\n\n".join(["Учебная вымышленная ситуация.", profile["responsibility_object"],
                                      "Ваши полномочия: " + profile["authority"], initial])
    return {
        "presentation": presentation, "base_role": profile["base_role"],
        "mode": input_snapshot["mode"], "synthetic": True,
        "generation_seconds": round(monotonic() - started, 3),
        "observability": input_snapshot["observability"],
        "methodological_qa": "NOT_RUN", "admitted_for_assessment": False,
        "admission_code": "CASE_NOT_ADMITTED",
        "checks": [
            {"code": "role_applicability", "result": "PASS"},
            {"code": "output_structure", "result": "PASS"},
            {"code": "role_authority_semantics", "result": "NOT_RUN"},
            {"code": "invariant_and_observability", "result": "NOT_RUN"},
        ],
    }


def begin_run(connection, *, request: GenerationRequest, user_id: int) -> tuple[dict, bool]:
    checksum = digest(json_bytes(request.model_dump(mode="json")))
    existing = get_run(connection, str(request.run_id))
    if existing is not None:
        if existing["created_by"] != user_id or existing["request_checksum"] != checksum:
            raise ValueError("run_id уже использован с другим запросом")
        return existing, False
    snapshot = build_generation_input(request)
    inserted = connection.execute("""
        INSERT INTO m5_generation_lab_runs (run_id, created_by, request_checksum, input_checksum, input_json, status)
        VALUES (%s, %s, %s, %s, %s::jsonb, 'running') ON CONFLICT (run_id) DO NOTHING RETURNING run_id
    """, (str(request.run_id), user_id, checksum, digest(json_bytes(snapshot)), json.dumps(snapshot, ensure_ascii=False))).fetchone()
    row = get_run(connection, str(request.run_id))
    if row["created_by"] != user_id or row["request_checksum"] != checksum:
        raise ValueError("run_id уже использован с другим запросом")
    return row, inserted is not None


def finish_run(connection, *, run_id: str, output: dict | None, error_code: str | None) -> None:
    connection.execute("""
        UPDATE m5_generation_lab_runs SET status = %s, output_json = %s::jsonb,
            output_checksum = %s, error_code = %s, completed_at = NOW()
        WHERE run_id = %s AND status = 'running'
    """, ("failed" if error_code else "completed", json.dumps(output, ensure_ascii=False) if output else None,
          digest(json_bytes(output)) if output else None, error_code, run_id))


def get_run(connection, run_id: str) -> dict | None:
    row = connection.execute("SELECT * FROM m5_generation_lab_runs WHERE run_id = %s", (run_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["run_id"] = str(result["run_id"])
    result["input_integrity"] = digest(json_bytes(result["input_json"])) == result["input_checksum"]
    result["output_integrity"] = (digest(json_bytes(result["output_json"])) == result["output_checksum"]
                                  if result["output_json"] is not None else None)
    return result

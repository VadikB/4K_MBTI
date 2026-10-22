"""Build the immutable M5 functional-personalization v0.2 draft package."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_case_runtime import checksum
from Api.m5_package import digest, json_bytes, verify_package_directory
from scripts.build_m5_sales_package import build_execution_rules, build_package

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.2"
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
CURRENT_DIRS = ("02_cases", "03_personalization", "04_as", "05_participant", "06_facilitator", "07_generation", "08_qa")


def _selection(source_root: Path, destination: Path) -> Path:
    index = json.loads((source_root / "Package_index_v0.2.json").read_text(encoding="utf-8"))
    selected = destination / "sources"
    selected.mkdir(parents=True)
    files = []
    for item in index["Cases"]:
        for kind, field in (("case", "Case"), ("sales_as", "AS")):
            source = source_root / item[field]["Файл"]
            target = selected / source.name
            shutil.copyfile(source, target)
            actual = digest(target.read_bytes())
            if actual != item[field]["SHA256"]:
                raise ValueError(f"Source checksum mismatch: {item[field]['Файл']}")
            files.append({
                "case_id": item["CaseID"], "kind": kind, "file": f"sources/{target.name}",
                "sha256": actual, "bytes": target.stat().st_size,
            })
    manifest = {
        "handoff_revision": "functional-personalization-v0.2-2026-10-22",
        "reference_main": "d54dbba", "files": files,
    }
    (selected / "manifest.json").write_bytes(json_bytes(manifest))
    return selected


def _copy_supporting_sources(source_root: Path, destination: Path) -> None:
    support = destination / "sources" / "functional-v0.2"
    for name in CURRENT_DIRS:
        shutil.copytree(source_root / name, support / name, dirs_exist_ok=True)
    for name in ("MANIFEST.sha256", "Package_index_v0.2.json", "Decisions_and_next_steps_v0.2.json",
                 "Source_inventory_v0.2.json", "README.txt", "Architect_handoff_v0.2.txt"):
        shutil.copyfile(source_root / name, support / name)


def build(source_root: Path) -> tuple[dict, dict, list[dict], list[dict]]:
    with tempfile.TemporaryDirectory(prefix="p4k-functional-") as temporary:
        package, selection, mapping, preview = build_package(_selection(source_root, Path(temporary)))
    package.update({
        "version": "0.2", "source_status": "WORKING", "runtime_enabled": False,
        "scope": {
            "professional_context": "functional", "base_role": "specialist_expert", "case_count": 9,
            "excluded": ["development_recommendations", "mini_cases"],
        },
        "generation_contract_ref": "sources/functional-v0.2/07_generation/Generation_contract_v0.2.json",
        "generator_instruction_ref": "sources/functional-v0.2/07_generation/Generator_instruction_v0.2.txt",
        "tester_instruction_ref": "sources/functional-v0.2/07_generation/Tester_instruction_v0.2.txt",
        "blockers": ["REAL_LLM_MATRIX_NOT_RUN", "FULL_CYCLE_NOT_RUN", "METHODOLOGY_REVIEW_NOT_APPROVED",
                     "RUNTIME_ADMISSION_DISABLED"],
    })
    return package, selection, mapping, preview


def write_package(source_root: Path, destination: Path = OUTPUT) -> dict:
    if (destination / "manifest.json").exists():
        current = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        if current.get("status") != "draft":
            raise ValueError("Refusing to overwrite a non-draft package")
        shutil.rmtree(destination)
    package, selection, mapping, preview = build(source_root)
    destination.mkdir(parents=True)
    source_dir = destination / "sources"
    source_dir.mkdir()
    for item in selection["files"]:
        source = source_root / next(
            entry[field]["Файл"]
            for entry in json.loads((source_root / "Package_index_v0.2.json").read_text())["Cases"]
            for field in ("Case", "AS") if entry["CaseID"] == item["case_id"] and
            ((field == "Case" and item["kind"] == "case") or (field == "AS" and item["kind"] == "sales_as"))
        )
        shutil.copyfile(source, source_dir / source.name)
    (source_dir / "source-selection-manifest.json").write_bytes(json_bytes(selection))
    _copy_supporting_sources(source_root, destination)
    rules = build_execution_rules(package["cases"])
    rules["owner_task"] = "PERS-05"
    verification = {
        "schema_version": 1, "result": "PASS", "scope": "static_functional_package",
        "case_count": 9, "assessment_situation_count": 9,
        "indicator_target_count": sum(len(case["indicator_targets"]) for case in package["cases"]),
        "character_counts": {case["case_id"]: len(case["characters"]) for case in package["cases"]},
        "package_checksum": checksum(package), "real_llm_matrix": "NOT_RUN", "full_cycle": "NOT_RUN",
        "methodology_admission": "NOT_RUN", "runtime_admission": "DISABLED",
    }
    files = {
        "case-package.json": json_bytes(package), "case.schema.json": json_bytes(CaseVersionV3.model_json_schema()),
        "execution-rules.json": json_bytes(rules), "mapping-report.json": json_bytes(mapping),
        "participant-preview.json": json_bytes(preview), "verification-report.json": json_bytes(verification),
    }
    for name, data in files.items():
        (destination / name).write_bytes(data)
    artifacts = [{"name": name, "sha256": digest(data)} for name, data in sorted(files.items())]
    artifacts.extend(
        {"name": str(path.relative_to(destination)), "sha256": digest(path.read_bytes())}
        for path in sorted(source_dir.rglob("*")) if path.is_file()
    )
    manifest = {
        "schema_version": 3, "id": "m5-functional-personalization-cases", "version": "0.2",
        "status": "draft", "source_status": "WORKING", "runtime_enabled": False, "artifacts": artifacts,
        "dependencies": {"m2": digest(M2.read_bytes()), "m3": digest(M3.read_bytes())},
        "source_selection": {"handoff_revision": selection["handoff_revision"],
                             "reference_main": selection["reference_main"]},
    }
    (destination / "manifest.json").write_bytes(json_bytes(manifest))
    verify_package_directory(destination)
    return verification


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify_package_directory(args.output)
    elif args.source_root is None:
        parser.error("source_root is required unless --verify-only is used")
    else:
        result = write_package(args.source_root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))

"""Compile a versioned M5 bank and preparation rules from a passport-only selection."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.assessment_case_contracts import CaseVersionV4
from Api.cycle_execution_manifest import (
    BATTERY_CASE_PACKAGE, BATTERY_RULE_PACKAGE, BATTERY_V04_CASE_PACKAGE, BATTERY_V04_RULE_PACKAGE,
)
from Api.m5_case_runtime import checksum
from Api.m5_package import digest, json_bytes, verify_package_directory
from Api.m5_passport import compile_passport, load_m2, missing, project_passport
from Api.m5_passport_generation import BANK_PACKAGE, CURRENT_AS_PACKAGE, M2, M3, ROOT, SOURCE_MANIFEST, read_as_package
from Api.m5_runtime_rules import load_runtime_rule_package

RUNTIME_PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.3.0"
BATTERY_PACKAGE = ROOT / BATTERY_CASE_PACKAGE
BATTERY_RUNTIME = ROOT / BATTERY_RULE_PACKAGE
BATTERY_PROVENANCE = ROOT / "docs/evc/tasks/m5-battery-bank/sources.json"
BATTERY_V04_PACKAGE = ROOT / BATTERY_V04_CASE_PACKAGE
BATTERY_V04_RUNTIME = ROOT / BATTERY_V04_RULE_PACKAGE
BATTERY_V04_PROVENANCE = ROOT / "docs/evc/tasks/m5-battery-v04/sources.json"
BATTERY_RELEASES = {
    "v0.3": (BATTERY_PACKAGE, BATTERY_RUNTIME, BATTERY_PROVENANCE),
    "v0.4": (BATTERY_V04_PACKAGE, BATTERY_V04_RUNTIME, BATTERY_V04_PROVENANCE),
}


def _selected(source_root: Path):
    index_path = source_root / "passport-index.json"
    if index_path.is_file():
        yield from json.loads(index_path.read_bytes())["cases"]
    else:
        # The legacy handoff index can bootstrap a passport-only inventory.
        index = json.loads((source_root / "Package_index_v0.2.json").read_bytes())
        for item in index["Cases"]:
            source = item.get("Case") or {}
            yield {"case_id": item["CaseID"], "version": item["CaseVersion"],
                   "path": source.get("Файл"), "sha256": source.get("SHA256")}


def build_bank(source_root: Path, destination: Path = BANK_PACKAGE,
               runtime_destination: Path = RUNTIME_PACKAGE, *, battery: bool = False,
               battery_version: str = "v0.3") -> dict:
    if battery:
        bank, runtime_dir, provenance_path = BATTERY_RELEASES[battery_version]
        provenance = json.loads(provenance_path.read_bytes())
    if battery and source_root.is_file():
        if battery_version == "v0.4" and digest(source_root.read_bytes()) != provenance["battery_archive_sha256"]:
            raise ValueError("M5_BATTERY_ARCHIVE_CHECKSUM_MISMATCH")
        with ZipFile(source_root) as archive, TemporaryDirectory(prefix="m5-battery-") as temporary:
            source = Path(temporary)
            manifest = archive.read("manifest.json")
            entries = _battery_entries(manifest, battery_version, provenance)
            (source / "manifest.json").write_bytes(manifest)
            for entry in entries:
                for kind, ref in entry["file_refs"].items():
                    if not re.fullmatch(r"(?:JSON/Case_SPEC_\d{2}_v\d+\.\d+_WORKING\.json|"
                                        r"Excel/Case_SPEC_\d{2}_v\d+\.\d+_WORKING\.xlsx)", ref["path"]):
                        raise missing(entry["case_id"], entry["version"], "manifest/file_refs/path")
                    data = archive.read(ref["path"])
                    if digest(data) != ref["sha256"]:
                        raise missing(entry["case_id"], entry["version"], f"manifest/file_refs/{kind}/sha256")
                    if kind == "json":
                        file = source / ref["path"]
                        file.parent.mkdir(exist_ok=True)
                        file.write_bytes(data)
            return build_bank(source, destination, runtime_destination, battery=True, battery_version=battery_version)
    m2, m2_ref = load_m2(M2, SOURCE_MANIFEST)
    m3_raw = M3.read_bytes()
    m3 = json.loads(m3_raw)
    _, as_contract_ref, prompt_refs = read_as_package(CURRENT_AS_PACKAGE) if battery else read_as_package()
    cases = []
    files = {}
    source_index = []
    if battery:
        manifest_raw = (source_root / "manifest.json").read_bytes()
        files["sources/manifest.json"] = manifest_raw
        entries = [
            {**item, **item["file_refs"]["json"], "base_role": "specialist_expert"}
            for item in _battery_entries(manifest_raw, battery_version, provenance)
        ]
    else:
        entries = _selected(source_root)
    for entry in entries:
        case_id, version = entry["case_id"], entry["version"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", case_id):
            raise missing(case_id, version, "1 CaseID")
        relative = entry.get("path")
        if not relative or not (source_root / relative).resolve().is_relative_to(source_root.resolve()):
            raise missing(case_id, version, "index/Case/path")
        path = source_root / relative
        if not path.is_file():
            raise missing(case_id, version, "index/Case/file")
        raw = path.read_bytes()
        if digest(raw) != entry.get("sha256"):
            raise missing(case_id, version, "index/Case/sha256")
        original = json.loads(raw)
        if (original.get("CaseID"), original.get("Version")) != (case_id, version):
            raise missing(case_id, version, "index→passport identity")
        passport = original.get("Паспорт") or {}
        if not battery:
            passport = project_passport(passport, case_id, version)
        if not any(key.startswith("7 ") and value == version for key, value in original["Паспорт"].items()):
            raise missing(case_id, version, "7 Version")
        source_name = f"sources/{relative if battery else case_id + '.json'}"
        data = raw if battery else json_bytes({
            "CaseID": case_id, "Version": version, "Status": original["Status"], "Паспорт": passport,
        })
        files[source_name] = data
        source = {"file": source_name, "sha256": digest(data), "pointer": "/Паспорт"}
        case = compile_passport(raw=passport, case_id=case_id, version=version, status=original["Status"],
                                source=source, m2=m2, m3=m3, as_contract_ref=as_contract_ref,
                                selected_base_role=entry.get("base_role"), passport_version="1.2" if battery else "1.1")
        if battery:
            expected = {
                "status": "WORKING", "title": entry["title"], "format": entry["format"],
                "case_type_ids": entry["ct_ids"], "planned_min_minutes": entry["time_min"],
                "planned_max_minutes": entry["time_max"],
            }
            for key, value in expected.items():
                if case[key] != value:
                    raise missing(case_id, version, f"manifest→passport/{key}")
            if (original.get("CURRENT") is not False or
                    [target["indicator_id"] for target in case["indicator_targets"]] != entry["indicator_ids"]):
                raise missing(case_id, version, "manifest→passport/CURRENT или 22")
        cases.append(case)
        source_index.append({"case_id": case_id, "version": version, "path": source_name,
                             "sha256": source["sha256"], "source_sha256": entry.get("source_sha256", digest(raw)),
                             **({"base_role": entry["base_role"]} if "base_role" in entry else {})})
    if not cases or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("M5_PASSPORT_BANK_CASE_SET_INVALID")
    package = {
        "schema_version": 4, "kind": "m5_case_package", "methodology_version": "1.1",
        "version": bank.name if battery else "0.6", "status": "draft",
        "source_status": "WORKING", "runtime_enabled": False,
        "cases": cases, "as_contract_ref": as_contract_ref,
    }
    runtime = {
        "schema_version": 2, "id": "m5-functional-personalization-runtime",
        "version": runtime_dir.name if battery else "1.3.0", "status": "draft", "owner": "PM-04",
    }
    bindings = {
        **runtime, "case_bindings": {
            case["case_id"]: {
                "case_version": case["version"], "case_checksum": checksum(case),
                "event_ids": [item["step_id"] for item in case["scenario"]], "as_contract_ref": as_contract_ref,
            } for case in cases
        },
    }
    rules = {
        "schema_version": 3, "status": "structured_draft", "owner_task": "M5-01",
        "case_bindings": bindings["case_bindings"],
    }
    verification = {
        "schema_version": 1, "result": "PASS", "scope": "static_functional_passport_bank",
        "case_count": len(cases), "target_count": sum(len(case["indicator_targets"]) for case in cases),
        "package_checksum": checksum(package), "methodology_admission": "NOT_RUN", "runtime_admission": "DISABLED",
    }
    if battery:
        targets = [target for case in cases for target in case["indicator_targets"]]
        counts = (len(targets), len({t["indicator_id"] for t in targets}), len({t["skill_id"] for t in targets}))
        totals = json.loads(manifest_raw)["totals"]
        if counts != (totals["assigned_indicators"], totals["distinct_indicators"], totals["distinct_skills"]):
            raise ValueError("M5_BATTERY_TARGET_TOTALS_MISMATCH")
        verification.update(distinct_indicators=counts[1], distinct_skills=counts[2])
    files.update({name: json_bytes(value) for name, value in {
        "passport-index.json": {"schema_version": 1, "cases": source_index},
        "case-package.json": package, "case.schema.json": CaseVersionV4.model_json_schema(),
        "execution-rules.json": rules, "verification-report.json": verification,
    }.items()})
    manifest = {
        "schema_version": 5, "id": "m5-functional-personalization-cases", "version": package["version"],
        "status": "draft", "source_status": "WORKING", "runtime_enabled": False,
        "artifacts": [{"name": name, "sha256": digest(data)} for name, data in sorted(files.items())],
        "compiler": {"id": "m5-functional-json-compiler", "version": "0.6.0",
                     "source_schema_profile": "functional-passport-v1"},
        "dependencies": {"m2": m2_ref["checksum"], "m3": digest(m3_raw)},
        "as_contract_ref": as_contract_ref, "prompt_package": prompt_refs["protocol_package"],
    }
    if battery:
        manifest.update(
            diagnostic_only=True,
            battery_source={"file": "sources/manifest.json", "sha256": digest(manifest_raw),
                            "provenance": provenance},
            compiler={**manifest["compiler"], "version": "0.7.0", "source_schema_profile": "functional-passport-v1.2"},
            runtime_rule_version=runtime["version"],
        )
    runtime_files = {"event-bindings.json": json_bytes(bindings)}
    runtime_files["manifest.json"] = json_bytes({
        **runtime, "source": {"case_package_id": manifest["id"], "case_package_version": package["version"],
                              "as_contract_ref": as_contract_ref},
        "artifacts": [{"name": name, "sha256": digest(data)} for name, data in runtime_files.items()],
    })
    files["manifest.json"] = json_bytes(manifest)
    outputs = ((destination, files), (runtime_destination, runtime_files))
    if destination.resolve() == runtime_destination.resolve():
        raise ValueError("M5_BANK_OUTPUTS_MUST_BE_DISTINCT")
    pending = []
    for directory, inventory in outputs:
        if directory.exists():
            actual = {str(path.relative_to(directory)): path.read_bytes()
                      for path in directory.rglob("*") if path.is_file()}
            if actual != inventory:
                raise ValueError(f"M5_IMMUTABLE_BANK_OUTPUT_CONFLICT:{directory}")
        else:
            pending.append((directory, inventory))
    for directory, inventory in pending:
        directory.parent.mkdir(parents=True, exist_ok=True)
        # A partial write stays in the staging directory. A rerun can finish
        # the second output using an already sealed first directory.
        with TemporaryDirectory(prefix=".m5-bank-", dir=directory.parent) as temporary:
            staging = Path(temporary) / directory.name
            for name, data in inventory.items():
                file = staging / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(data)
            staging.rename(directory)
    verify_package_directory(destination)
    load_runtime_rule_package(runtime_destination, cases, expected_case_package_version=package["version"])
    return verification


def _battery_entries(raw: bytes, battery_version: str, provenance: dict) -> list[dict]:
    if digest(raw) != provenance["battery_manifest_sha256"]:
        raise ValueError("M5_BATTERY_MANIFEST_CHECKSUM_MISMATCH")
    manifest = json.loads(raw)
    if (manifest["version"], manifest["status"], manifest["current"], manifest["base_role"]["code"]) != (
        battery_version, "WORKING", False, "specialist_expert",
    ) or manifest["basis"]["passport_template"]["version"] != "v1.2":
        raise ValueError("M5_BATTERY_MANIFEST_IDENTITY_MISMATCH")
    cases = manifest["cases"]
    if [case["case_id"] for case in cases] != [f"CASE.SPEC.{n:02}" for n in range(1, 10)]:
        raise ValueError("M5_PASSPORT_BANK_CASE_SET_INVALID")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    batteries = parser.add_mutually_exclusive_group()
    for version in BATTERY_RELEASES:
        batteries.add_argument(f"--battery-{version}", dest="battery", action="store_const", const=version,
                               help=f"Compile the diagnostic {version} passport bank.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runtime-output", type=Path)
    args = parser.parse_args()
    bank, runtime = BATTERY_RELEASES[args.battery][:2] if args.battery else (BANK_PACKAGE, RUNTIME_PACKAGE)
    result = build_bank(args.source_root, args.output or bank, args.runtime_output or runtime,
                        battery=bool(args.battery), battery_version=args.battery or "v0.3")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

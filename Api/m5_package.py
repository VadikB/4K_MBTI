"""Общие операции с каталогами пакетов M5, не зависящие от authoring-формата."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Api.assessment_case_contracts import validate_case_version


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def verify_package_directory(destination: Path) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text())
    expected = {"manifest.json"} | {item["name"] for item in manifest["artifacts"]}
    actual = {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError(f"Package inventory mismatch: {sorted(actual ^ expected)}")
    for artifact in manifest["artifacts"]:
        if digest((destination / artifact["name"]).read_bytes()) != artifact["sha256"]:
            raise ValueError(f"Artifact checksum mismatch: {artifact['name']}")
    package = json.loads((destination / "case-package.json").read_text())
    for case in package["cases"]:
        validate_case_version(case)
    if package.get("runtime_enabled") is not False or package.get("status") != "draft":
        raise ValueError("WORKING package cannot be runtime enabled")
    return json.loads((destination / "verification-report.json").read_text())

from __future__ import annotations

import hashlib
import subprocess
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/P4K_PERS_Evidence_2026-10-22.zip"
INCLUDE = (
    ROOT / "docs/evc/evidence/pers-functional-personalization",
    ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.2",
    ROOT / "assessment_definitions/prompts/m6_evidence/v1.0.1",
    ROOT / "assessment_definitions/prompts/m6_indicator_assessment/v1.0.1",
    ROOT / "docs/evc/protocols/m5-functional-personalization-tester-v2.json",
    ROOT / "docs/evc/pers-methodology-export.json",
    ROOT / "docs/evc/reports/pers-functional-personalization.md",
    ROOT / "docs/evc/tasks/pers-functional-personalization.md",
)


def files() -> list[Path]:
    result: list[Path] = []
    for item in INCLUDE:
        result.extend(path for path in item.rglob("*") if path.is_file()) if item.is_dir() else result.append(item)
    return sorted(set(result))


def main() -> None:
    selected = files()
    missing = [str(path) for path in selected if not path.exists()]
    if missing:
        raise SystemExit("Missing evidence: " + ", ".join(missing))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest_lines = []
    for path in selected:
        relative = path.relative_to(ROOT).as_posix()
        manifest_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    metadata = f"commit_sha={commit}\nproduct_version={version}\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in selected:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("MANIFEST.sha256", "\n".join(manifest_lines) + "\n")
        archive.writestr("ARCHIVE-METADATA.txt", metadata)
    print(f"{OUTPUT} files={len(selected)} sha256={hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()

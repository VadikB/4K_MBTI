from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = BASE_DIR / "pyproject.toml"
VERSION_PATTERN = re.compile(r'(?m)^version = "(\d+)\.(\d+)\.(\d+)"$')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Increment the project patch version.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the next patch version without changing files.",
    )
    return parser.parse_args()


def get_current_version() -> tuple[int, int, int]:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise RuntimeError("Could not read current version from pyproject.toml")
    return tuple(int(part) for part in match.groups())


def main() -> int:
    args = parse_args()
    try:
        major, minor, patch = get_current_version()
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    next_version = f"{major}.{minor}.{patch + 1}"
    if args.dry_run:
        print(next_version)
        return 0

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "bump_version.py"), next_version],
        cwd=str(BASE_DIR),
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    print(f"Patch version bumped to {next_version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

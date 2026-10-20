"""CI guard for a consistent, new application release candidate."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib

from release_version import ROOT, check_consistency, parse_version


NON_PRODUCT_PREFIXES = ("docs/", "tests/", ".github/", ".githooks/")
NON_PRODUCT_FILES = {"README.md", "CONTRIBUTING.md", "AGENTS.md", "package-lock.json"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def verify_against_base(base: str, version: str) -> None:
    base_project = tomllib.loads(git("show", f"{base}:pyproject.toml"))
    base_version = str(base_project["project"]["version"])
    parse_version(base_version)
    changed = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    product_changed = any(path not in NON_PRODUCT_FILES and not path.startswith(NON_PRODUCT_PREFIXES) for path in changed)
    if not product_changed:
        return
    if version == base_version:
        raise ValueError(f"Product changed but release version remains {version}")
    if (base_version, version) == ("2.1.37", "2.0.1"):
        if "docs/evc/tasks/rel-version-01.md" not in changed:
            raise ValueError("One-time 2.0.1 transition needs its release card")
    elif tuple(parse_version(version)) <= tuple(parse_version(base_version)):
        raise ValueError(f"Release {version} is not newer than current base {base_version}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", help="Current PR base commit; compare against its release version")
    args = parser.parse_args()
    try:
        version = check_consistency(ROOT)
        if args.base_ref:
            verify_against_base(args.base_ref, version)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Release check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Release check passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

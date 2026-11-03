"""Prepare and verify an application candidate before marking a PR ready."""

from __future__ import annotations

import argparse
import subprocess
import sys

import check_release_version
from prepare_release import main as prepare_release
from release_version import ROOT, check_consistency, next_version


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def refresh_and_require_current_base(base_ref: str) -> None:
    if base_ref == "origin/main":
        subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, check=True)
    merge_base = git("merge-base", "HEAD", base_ref)
    base_sha = git("rev-parse", base_ref)
    if merge_base != base_sha:
        raise ValueError(
            f"Branch is based on stale {base_ref} ({merge_base}); "
            f"update it to {base_sha} before preparing a release candidate"
        )


def changed_product_paths(base_ref: str) -> list[str]:
    paths = set(git("diff", "--name-only", f"{base_ref}...HEAD").splitlines())
    paths.update(git("diff", "--name-only").splitlines())
    paths.update(git("diff", "--name-only", "--cached").splitlines())
    return [
        path for path in sorted(paths)
        if path not in check_release_version.NON_PRODUCT_FILES
        and not path.startswith(check_release_version.NON_PRODUCT_PREFIXES)
    ]


def run(base_ref: str, release_type: str, candidate: str | None) -> int:
    refresh_and_require_current_base(base_ref)
    product_paths = changed_product_paths(base_ref)
    if not product_paths:
        print("Ready preflight passed: no product release change")
        return 0

    current = check_consistency(ROOT)
    base = check_release_version.tomllib.loads(git("show", f"{base_ref}:pyproject.toml"))
    base_version = str(base["project"]["version"])
    if current == base_version:
        expected = next_version(current, release_type)
        if candidate is None:
            print(
                f"Ready preflight requires an approved {release_type} candidate: "
                f"{current} → {expected}. Re-run with --candidate {expected}.",
                file=sys.stderr,
            )
            return 2
        result = prepare_release([release_type, "--candidate", candidate])
        if result:
            return result
    elif candidate is not None and candidate != current:
        print(f"Candidate {candidate} does not match the prepared release {current}", file=sys.stderr)
        return 2

    subprocess.run(["npm", "run", "build:web"], cwd=ROOT, check=True)
    version = check_consistency(ROOT)
    check_release_version.verify_against_base(base_ref, version)
    print(f"Ready preflight passed: release {version}; product paths: {len(product_paths)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--release-type", choices=("major", "minor", "patch"), default="patch")
    parser.add_argument("--candidate")
    args = parser.parse_args(argv)
    try:
        return run(args.base_ref, args.release_type, args.candidate)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Ready preflight failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Compatibility entry point; all writes use the candidate-aware operation."""

from __future__ import annotations

import argparse
import sys

from prepare_release import main as prepare_release
from release_version import ROOT, check_consistency, next_version, parse_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an explicit application release number.")
    parser.add_argument("version", help="MAJOR.MINOR.PATCH")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-new-sequence", action="store_true")
    args = parser.parse_args()
    try:
        parse_version(args.version)
        current = check_consistency(ROOT, check_index=False)
        if args.start_new_sequence:
            release_type = "patch"
        else:
            release_type = next(
                (kind for kind in ("patch", "minor", "major") if next_version(current, kind) == args.version),
                None,
            )
            if release_type is None and args.version == current:
                release_type = "patch"
            if release_type is None:
                raise ValueError("Target is not the next major, minor or patch release")
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    arguments = [release_type, "--candidate", args.version]
    if args.dry_run:
        arguments.append("--dry-run")
    if args.start_new_sequence:
        arguments.append("--start-new-sequence")
    return prepare_release(arguments)


if __name__ == "__main__":
    raise SystemExit(main())

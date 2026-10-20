"""Prepare exactly one application release candidate."""

from __future__ import annotations

import argparse
import sys

from release_version import ROOT, check_consistency, next_version, parse_version, write_updates


def candidate_version(current: str, release_type: str, candidate: str | None, *, start_new_sequence: bool = False) -> str:
    if start_new_sequence:
        if current != "2.1.37" or candidate != "2.0.1" or release_type != "patch":
            raise ValueError("The one-time 2.1.37 → 2.0.1 transition requires patch --candidate 2.0.1")
        return "2.0.1"
    expected = next_version(current, release_type)
    if candidate is None:
        return expected
    parse_version(candidate)
    if candidate != current and candidate != expected:
        raise ValueError(f"Candidate {candidate} is not the {release_type} successor of {current} ({expected})")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a major, minor or patch release candidate.")
    parser.add_argument("release_type", choices=("major", "minor", "patch"))
    parser.add_argument("--candidate", help="Approved target version; repeat with same number is idempotent")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start-new-sequence", action="store_true", help="One-time owner-approved 2.1.37 → 2.0.1")
    args = parser.parse_args(argv)
    try:
        current = check_consistency(ROOT, check_index=False)
        if not args.dry_run and not args.candidate:
            raise ValueError("--candidate is required when writing a release")
        target = candidate_version(current, args.release_type, args.candidate, start_new_sequence=args.start_new_sequence)
        changed = write_updates(ROOT, target, dry_run=args.dry_run)
        if not args.dry_run:
            check_consistency(ROOT)
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{args.release_type}: {current} → {target}; {'would update' if args.dry_run else 'updated'}: {', '.join(changed) or 'nothing'}")
    if not args.dry_run:
        print("Next step: npm run build:web")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

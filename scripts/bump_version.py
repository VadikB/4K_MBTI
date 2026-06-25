from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = BASE_DIR / "pyproject.toml"
UV_LOCK_PATH = BASE_DIR / "uv.lock"
FRONTEND_CONFIG_PATH = BASE_DIR / "web" / "js" / "config.js"

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the project release version in all runtime-critical files.",
    )
    parser.add_argument("version", help="New version in semver format, for example 2.1.1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without writing files.",
    )
    return parser.parse_args()


def validate_version(version: str) -> str:
    normalized = str(version or "").strip()
    if not SEMVER_PATTERN.fullmatch(normalized):
        raise ValueError("Version must match semantic format MAJOR.MINOR.PATCH, for example 2.1.1")
    return normalized


def replace_once(content: str, pattern: re.Pattern[str], replacement: str, *, file_label: str) -> str:
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise RuntimeError(f"Could not update version in {file_label}")
    return updated


def update_text_file(path: Path, pattern: re.Pattern[str], replacement: str, *, dry_run: bool) -> tuple[bool, str]:
    original = path.read_text(encoding="utf-8")
    updated = replace_once(original, pattern, replacement, file_label=str(path))
    changed = updated != original
    if changed and not dry_run:
        path.write_text(updated, encoding="utf-8")
    return changed, str(path.relative_to(BASE_DIR))


def main() -> int:
    args = parse_args()
    try:
        version = validate_version(args.version)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    file_updates = [
        (
            PYPROJECT_PATH,
            re.compile(r'(?m)^version = "\d+\.\d+\.\d+"$'),
            f'version = "{version}"',
        ),
        (
            UV_LOCK_PATH,
            re.compile(r'(?m)^version = "\d+\.\d+\.\d+"$'),
            f'version = "{version}"',
        ),
        (
            FRONTEND_CONFIG_PATH,
            re.compile(r'(?m)^export const APP_RELEASE = "\d+\.\d+\.\d+";$'),
            f'export const APP_RELEASE = "{version}";',
        ),
    ]

    touched: list[str] = []
    try:
        for path, pattern, replacement in file_updates:
            changed, label = update_text_file(path, pattern, replacement, dry_run=args.dry_run)
            if changed:
                touched.append(label)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if touched:
        mode = "Would update" if args.dry_run else "Updated"
        print(f"{mode} version to {version}:")
        for item in touched:
            print(f"  - {item}")
    else:
        print(f"Version is already {version}. No files changed.")

    if not args.dry_run:
        print("Next step: rebuild frontend assets before deploy (bun run build:web or local esbuild build).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

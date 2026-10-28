"""Shared application-release version reads, validation and file updates."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
PROJECT_VERSION_RE = re.compile(r'(?m)^version = "[^"]+"$')
LOCK_ROOT_RE = re.compile(
    r'(?m)(\[\[package\]\]\nname = "agent-4k"\nversion = ")[^"]+("\n)'
)
FRONTEND_VERSION_RE = re.compile(r'(?m)^export const APP_RELEASE = "[^"]*";$')
INDEX_ASSET_VERSION_RE = re.compile(
    r'((?:href|src)="/web/(?:styles/[^"\n]+|dist/main\.js)\?v=)([^"\n]+)(")'
)
INDEX_RELEASE_BADGE_RE = re.compile(r'(data-app-release-number>)([^<]*)(</span>)')


def parse_version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise ValueError("Version must be MAJOR.MINOR.PATCH with three non-negative integers")
    return tuple(int(part) for part in value.split("."))


def next_version(current: str, release_type: str) -> str:
    major, minor, patch = parse_version(current)
    if release_type == "major":
        return f"{major + 1}.0.0"
    if release_type == "minor":
        return f"{major}.{minor + 1}.0"
    if release_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError("Release type must be major, minor or patch")


def read_versions(root: Path = ROOT) -> dict[str, str]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    config = (root / "web/js/config.js").read_text(encoding="utf-8")
    root_packages = [
        item for item in lock.get("package", [])
        if item.get("name") == "agent-4k" and item.get("source") == {"virtual": "."}
    ]
    if len(root_packages) != 1:
        raise ValueError("uv.lock must contain exactly one local agent-4k package")
    frontend = FRONTEND_VERSION_RE.findall(config)
    if len(frontend) != 1:
        raise ValueError("web/js/config.js must define APP_RELEASE exactly once")
    versions = {
        "pyproject.toml": str(project["project"]["version"]),
        "uv.lock": str(root_packages[0]["version"]),
        "web/js/config.js": frontend[0].split('"')[1],
    }
    for value in versions.values():
        parse_version(value)
    return versions


def check_consistency(root: Path = ROOT, *, check_index: bool = True) -> str:
    versions = read_versions(root)
    if len(set(versions.values())) != 1:
        raise ValueError(f"Application release versions disagree: {versions}")
    version = versions["pyproject.toml"]
    if check_index:
        index = (root / "web/index.html").read_text(encoding="utf-8")
        asset_versions = INDEX_ASSET_VERSION_RE.findall(index)
        if not asset_versions or not all(index_version == version for _, index_version, _ in asset_versions):
            raise ValueError("web/index.html asset query versions do not match the application release")
        badges = INDEX_RELEASE_BADGE_RE.findall(index)
        if not badges or any(badge_version != version for _, badge_version, _ in badges):
            raise ValueError("web/index.html visible release versions do not match the application release")
    return version


def _replace_exactly_once(content: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise ValueError(f"Could not update exactly one version in {label}")
    return updated


def prepare_updates(root: Path, version: str) -> dict[Path, str]:
    parse_version(version)
    project_path = root / "pyproject.toml"
    lock_path = root / "uv.lock"
    config_path = root / "web/js/config.js"
    index_path = root / "web/index.html"
    project = project_path.read_text(encoding="utf-8")
    lock = lock_path.read_text(encoding="utf-8")
    config = config_path.read_text(encoding="utf-8")
    index = index_path.read_text(encoding="utf-8")
    updated_index, count = INDEX_ASSET_VERSION_RE.subn(lambda match: match[1] + version + match[3], index)
    if count < 2:
        raise ValueError("Expected CSS and main.js release query versions in web/index.html")
    updated_index = INDEX_RELEASE_BADGE_RE.sub(lambda match: match[1] + version + match[3], updated_index)
    return {
        project_path: _replace_exactly_once(project, PROJECT_VERSION_RE, f'version = "{version}"', "pyproject.toml"),
        lock_path: _replace_exactly_once(lock, LOCK_ROOT_RE, lambda match: match[1] + version + match[2], "uv.lock"),
        config_path: _replace_exactly_once(config, FRONTEND_VERSION_RE, f'export const APP_RELEASE = "{version}";', "web/js/config.js"),
        index_path: updated_index,
    }


def write_updates(root: Path, version: str, *, dry_run: bool = False) -> list[str]:
    updates = prepare_updates(root, version)
    changed = [str(path.relative_to(root)) for path, content in updates.items() if path.read_text(encoding="utf-8") != content]
    if not dry_run:
        for path, content in updates.items():
            if str(path.relative_to(root)) in changed:
                path.write_text(content, encoding="utf-8")
    return changed

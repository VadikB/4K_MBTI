import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_release import candidate_version  # noqa: E402
from release_version import check_consistency, next_version, parse_version, write_updates  # noqa: E402
import check_release_version  # noqa: E402
import prepare_ready_release  # noqa: E402


def test_release_numbers_and_rollovers():
    assert parse_version("2.0.10") == (2, 0, 10)
    assert next_version("2.0.1", "patch") == "2.0.2"
    assert next_version("2.0.1", "minor") == "2.1.0"
    assert next_version("2.0.1", "major") == "3.0.0"
    for invalid in ("", "2.0", "2.0.1.0", "2.0.-1", "02.0.1", " 2.0.1"):
        with pytest.raises(ValueError):
            parse_version(invalid)


def test_candidate_is_idempotent_and_transition_is_one_time():
    assert candidate_version("2.0.1", "patch", "2.0.1") == "2.0.1"
    assert candidate_version("2.0.1", "patch", "2.0.2") == "2.0.2"
    assert candidate_version("2.1.37", "patch", "2.0.1", start_new_sequence=True) == "2.0.1"
    with pytest.raises(ValueError):
        candidate_version("2.0.2", "patch", "2.0.1", start_new_sequence=True)
    with pytest.raises(ValueError):
        candidate_version("2.0.1", "patch", "2.0.3")


def test_dry_run_and_consistency(tmp_path):
    (tmp_path / "web/js").mkdir(parents=True)
    (tmp_path / "web").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "agent-4k"\nversion = "2.0.1"\n')
    (tmp_path / "uv.lock").write_text('version = 1\n\n[[package]]\nname = "agent-4k"\nversion = "2.0.1"\nsource = { virtual = "." }\n')
    (tmp_path / "web/js/config.js").write_text('export const APP_RELEASE = "2.0.1";\n')
    (tmp_path / "web/index.html").write_text('<link href="/web/styles/base.css?v=2.0.1"><script src="/web/dist/main.js?v=2.0.1"></script><span data-app-release-number>2.0.1</span>')
    before = (tmp_path / "web/index.html").read_text()
    assert check_consistency(tmp_path) == "2.0.1"
    assert len(write_updates(tmp_path, "2.0.2", dry_run=True)) == 4
    assert (tmp_path / "web/index.html").read_text() == before
    write_updates(tmp_path, "2.0.2")
    assert check_consistency(tmp_path) == "2.0.2"
    (tmp_path / "web/js/config.js").write_text('export const APP_RELEASE = "2.0.1";\n')
    with pytest.raises(ValueError):
        check_consistency(tmp_path)


def test_ci_requires_immediate_release_successor(monkeypatch):
    def fake_git(*args):
        if args[0] == "show":
            return '[project]\nversion = "2.0.1"'
        return 'web/js/main.js\n'

    monkeypatch.setattr(check_release_version, "git", fake_git)
    with pytest.raises(ValueError, match="remains"):
        check_release_version.verify_against_base("base", "2.0.1")
    with pytest.raises(ValueError, match="not an immediate successor"):
        check_release_version.verify_against_base("base", "2.0.0")
    check_release_version.verify_against_base("base", "2.0.2")
    check_release_version.verify_against_base("base", "2.1.0")
    check_release_version.verify_against_base("base", "3.0.0")
    with pytest.raises(ValueError, match="not an immediate successor"):
        check_release_version.verify_against_base("base", "2.0.3")
    with pytest.raises(ValueError, match="not an immediate successor"):
        check_release_version.verify_against_base("base", "2.2.0")


def test_backend_version_source_matches_release():
    from Api.app_version import get_app_version

    get_app_version.cache_clear()
    assert get_app_version() == check_consistency(Path(__file__).resolve().parents[2])


def test_ready_preflight_does_not_require_release_for_non_product_change(monkeypatch):
    monkeypatch.setattr(prepare_ready_release, "refresh_and_require_current_base", lambda _base: None)
    monkeypatch.setattr(prepare_ready_release, "changed_product_paths", lambda _base: [])
    assert prepare_ready_release.run("origin/main", "patch", None) == 0


def test_ready_preflight_includes_uncommitted_and_staged_paths(monkeypatch):
    outputs = {
        ("diff", "--name-only", "origin/main...HEAD"): "docs/committed.md\n",
        ("diff", "--name-only"): "scripts/prepare_ready_release.py\n",
        ("diff", "--name-only", "--cached"): "web/js/main.js\n",
    }
    monkeypatch.setattr(prepare_ready_release, "git", lambda *args: outputs[args])
    assert prepare_ready_release.changed_product_paths("origin/main") == [
        "scripts/prepare_ready_release.py",
        "web/js/main.js",
    ]


def test_ready_preflight_reports_candidate_before_ready(monkeypatch, capsys):
    monkeypatch.setattr(prepare_ready_release, "refresh_and_require_current_base", lambda _base: None)
    monkeypatch.setattr(prepare_ready_release, "changed_product_paths", lambda _base: ["web/js/main.js"])
    monkeypatch.setattr(prepare_ready_release, "check_consistency", lambda _root: "2.0.47")
    monkeypatch.setattr(
        prepare_ready_release,
        "git",
        lambda *args: '[project]\nversion = "2.0.47"' if args[0] == "show" else "",
    )
    assert prepare_ready_release.run("origin/main", "patch", None) == 2
    assert "2.0.47 → 2.0.48" in capsys.readouterr().err


def test_ready_preflight_prepares_builds_and_verifies(monkeypatch):
    monkeypatch.setattr(prepare_ready_release, "refresh_and_require_current_base", lambda _base: None)
    versions = iter(("2.0.47", "2.0.48"))
    monkeypatch.setattr(prepare_ready_release, "changed_product_paths", lambda _base: ["web/js/main.js"])
    monkeypatch.setattr(prepare_ready_release, "check_consistency", lambda _root: next(versions))
    monkeypatch.setattr(
        prepare_ready_release,
        "git",
        lambda *args: '[project]\nversion = "2.0.47"' if args[0] == "show" else "",
    )
    prepared = []
    monkeypatch.setattr(prepare_ready_release, "prepare_release", lambda args: prepared.append(args) or 0)
    monkeypatch.setattr(prepare_ready_release.subprocess, "run", lambda *args, **kwargs: None)
    verified = []
    monkeypatch.setattr(
        prepare_ready_release.check_release_version,
        "verify_against_base",
        lambda base, version: verified.append((base, version)),
    )
    assert prepare_ready_release.run("origin/main", "patch", "2.0.48") == 0
    assert prepared == [["patch", "--candidate", "2.0.48"]]
    assert verified == [("origin/main", "2.0.48")]


def test_ready_preflight_fetches_and_requires_current_main(monkeypatch):
    runs = []
    monkeypatch.setattr(
        prepare_ready_release.subprocess,
        "run",
        lambda *args, **kwargs: runs.append((args, kwargs)),
    )
    values = {
        ("merge-base", "HEAD", "origin/main"): "base-sha",
        ("rev-parse", "origin/main"): "base-sha",
    }
    monkeypatch.setattr(prepare_ready_release, "git", lambda *args: values[args])
    prepare_ready_release.refresh_and_require_current_base("origin/main")
    assert runs[0][0][0] == ["git", "fetch", "origin", "main"]
    assert runs[0][1]["check"] is True


def test_ready_preflight_rejects_stale_branch(monkeypatch):
    monkeypatch.setattr(prepare_ready_release.subprocess, "run", lambda *args, **kwargs: None)
    values = {
        ("merge-base", "HEAD", "origin/main"): "old-base",
        ("rev-parse", "origin/main"): "current-base",
    }
    monkeypatch.setattr(prepare_ready_release, "git", lambda *args: values[args])
    with pytest.raises(ValueError, match="based on stale origin/main"):
        prepare_ready_release.refresh_and_require_current_base("origin/main")

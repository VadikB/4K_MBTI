import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_release import candidate_version  # noqa: E402
from release_version import check_consistency, next_version, parse_version, write_updates  # noqa: E402
import check_release_version  # noqa: E402


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
    (tmp_path / "web/index.html").write_text('<link href="/web/styles/base.css?v=2.0.1"><script src="/web/dist/main.js?v=2.0.1"></script>')
    before = (tmp_path / "web/index.html").read_text()
    assert check_consistency(tmp_path) == "2.0.1"
    assert len(write_updates(tmp_path, "2.0.2", dry_run=True)) == 4
    assert (tmp_path / "web/index.html").read_text() == before
    write_updates(tmp_path, "2.0.2")
    assert check_consistency(tmp_path) == "2.0.2"
    (tmp_path / "web/js/config.js").write_text('export const APP_RELEASE = "2.0.1";\n')
    with pytest.raises(ValueError):
        check_consistency(tmp_path)


def test_ci_rejects_unchanged_or_stale_release(monkeypatch):
    def fake_git(*args):
        if args[0] == "show":
            return '[project]\nversion = "2.0.1"'
        return 'web/js/main.js\n'

    monkeypatch.setattr(check_release_version, "git", fake_git)
    with pytest.raises(ValueError, match="remains"):
        check_release_version.verify_against_base("base", "2.0.1")
    with pytest.raises(ValueError, match="not newer"):
        check_release_version.verify_against_base("base", "2.0.0")
    check_release_version.verify_against_base("base", "2.0.2")


def test_backend_version_source_matches_release():
    from Api.app_version import get_app_version

    get_app_version.cache_clear()
    assert get_app_version() == check_consistency(Path(__file__).resolve().parents[2])

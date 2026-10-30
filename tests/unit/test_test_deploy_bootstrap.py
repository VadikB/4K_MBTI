"""Run the actual shell procedures against disposable Git repos and fake tools."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = "/home/vadim_bogachev/projects/Agent4K-Test"
DEPLOY = (ROOT / "scripts/deploy_test_remote.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/backend-tests.yml").read_text(encoding="utf-8")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def bootstrap_source() -> str:
    return textwrap.dedent(WORKFLOW.split("<<'REMOTE'\n", 1)[1].split("\n          REMOTE", 1)[0])


@pytest.fixture
def stand(tmp_path: Path) -> dict:
    repo = tmp_path / "test-checkout"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Synthetic deploy test")
    git(repo, "config", "user.email", "deploy@example.invalid")
    (repo / ".gitignore").write_text(".venv/\n.public-origin.json\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "web/dist").mkdir(parents=True)
    (repo / "scripts/retain_previous_frontend_assets.sh").write_bytes(
        (ROOT / "scripts/retain_previous_frontend_assets.sh").read_bytes()
    )
    # This stale script cannot deploy anything. Bootstrap must load the new Git blob.
    (repo / "scripts/deploy_test_remote.sh").write_text("exit 71\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nversion = "2.0.31"\n', encoding="utf-8")
    (repo / "web/dist/main.js").write_text("old-entrypoint", encoding="utf-8")
    (repo / "web/dist/old-HASH.js").write_text("old-hashed-chunk", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Old test deployment")
    old = git(repo, "rev-parse", "HEAD")

    source = DEPLOY.replace(TEST_ROOT, str(repo))
    (repo / "Api").mkdir()
    (repo / "Api/public_origin.py").write_bytes((ROOT / "Api/public_origin.py").read_bytes())
    (repo / "scripts/configure_public_origin.py").write_bytes((ROOT / "scripts/configure_public_origin.py").read_bytes())
    (repo / "scripts/deploy_test_remote.sh").write_text(source, encoding="utf-8")
    (repo / "pyproject.toml").write_text('[project]\nversion = "2.0.34"\n', encoding="utf-8")
    (repo / "web/dist/main.js").write_text("checked-entrypoint", encoding="utf-8")
    git(repo, "rm", "-q", "web/dist/old-HASH.js")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "CI-checked candidate")
    target = git(repo, "rev-parse", "HEAD")

    (repo / "web/dist/main.js").write_text("future-unchecked-entrypoint", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Later main must not be deployed by an older run")
    future = git(repo, "rev-parse", "HEAD")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "--detach", old)
    git(repo, "branch", "-f", "main", old)

    fakebin = tmp_path / "bin"
    log = tmp_path / "commands.log"
    env = dict(os.environ, PATH=f"{fakebin}{os.pathsep}{os.environ['PATH']}",
               SYNTHETIC_DEPLOY_LOG=str(log), SYNTHETIC_ONCE=str(tmp_path / "once"))
    executable(repo / ".venv/bin/pip", "#!/bin/sh\nexit 0\n")
    (repo / ".venv/bin/python").symlink_to(sys.executable)
    executable(fakebin / "npm", """
        #!/bin/sh
        printf 'npm %s\\n' "$*" >> "$SYNTHETIC_DEPLOY_LOG"
        if [ "$*" = 'run build:web' ] && [ "${SYNTHETIC_BUILD_FAIL:-0}" = 1 ] && [ ! -e "$SYNTHETIC_ONCE" ]; then
          touch "$SYNTHETIC_ONCE"
          exit 1
        fi
    """)
    executable(fakebin / "sudo", """
        #!/bin/sh
        test "$*" = '-n systemctl restart agent4k-test.service' || exit 99
        printf 'sudo %s\\n' "$*" >> "$SYNTHETIC_DEPLOY_LOG"
    """)
    executable(fakebin / "curl", """
        #!/bin/sh
        case "$*" in
          *users/version*)
            .venv/bin/python -c 'import json,tomllib,os; print(json.dumps({"version": tomllib.load(open("pyproject.toml","rb"))["project"]["version"], "public_origin": os.getenv("SYNTHETIC_SMOKE_ORIGIN", "https://test.4k-assistant.ru")}))'
            ;;
          *web/dist/main.js*)
            if [ "${SYNTHETIC_SMOKE_FAIL:-0}" = 1 ]; then exit 1; fi
            cat web/dist/main.js
            ;;
          *) exit 98 ;;
        esac
    """)
    return {"repo": repo, "old": old, "target": target, "future": future,
            "source": source, "env": env, "log": log}


def run_deploy(stand: dict, commit: str, *, bootstrap: bool = False, **env) -> subprocess.CompletedProcess:
    repo = stand["repo"]
    if bootstrap:
        command = ["sh", "-c", bootstrap_source().replace(TEST_ROOT, str(repo)), "bootstrap", commit]
    else:
        command = ["sh", "-c", stand["source"], str(repo / "scripts/deploy_test_remote.sh"), commit]
    return subprocess.run(command, env=dict(stand["env"], **env), capture_output=True, text=True)


def test_workflow_preserves_ssh_security_and_pins_ci_commit() -> None:
    assert 'DEPLOY_COMMIT: ${{ github.sha }}' in WORKFLOW
    assert 'sh -s -- "$DEPLOY_COMMIT"' in WORKFLOW
    assert '-o StrictHostKeyChecking=yes' in WORKFLOW
    assert '-o IdentitiesOnly=yes' in WORKFLOW
    assert 'SHA256:WaR/8vp4pqCqig4CjWai9WN0GGW93FJGtDFXf1GgYbo' in WORKFLOW
    assert '/home/user1/' not in WORKFLOW
    assert TEST_ROOT in bootstrap_source()
    subprocess.run(["sh", "-n"], input=bootstrap_source(), text=True, check=True)


def test_bootstrap_uses_checked_git_script_not_stale_checkout(stand: dict) -> None:
    result = run_deploy(stand, stand["target"], bootstrap=True)
    assert result.returncode == 0, result.stderr
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["target"]
    assert (stand["repo"] / "web/dist/main.js").read_text() == "checked-entrypoint"
    assert (stand["repo"] / "web/dist/old-HASH.js").read_text() == "old-hashed-chunk"
    assert stand["future"] not in result.stdout
    assert '"origin": "https://test.4k-assistant.ru"' in (stand["repo"] / ".public-origin.json").read_text()
    ledger = stand["repo"] / ".runtime/deletion-ledger/deletion-intents.jsonl"
    assert ledger.is_file()
    assert ledger.stat().st_mode & 0o777 == 0o600
    assert f"DELETION_LEDGER_PATH={ledger}" in (stand["repo"] / ".env").read_text()


@pytest.mark.parametrize("previous", [None, '{"schema_version":1,"mode":"public","origin":"https://old.example.com"}'])
def test_effective_origin_mismatch_rolls_back_public_config_without_touching_dotenv(stand: dict, previous) -> None:
    config = stand["repo"] / ".public-origin.json"
    dotenv = stand["repo"] / ".env"
    dotenv.write_text("APP_BASE_URL=http://127.0.0.1:8002\nSYNTHETIC_SECRET=not-a-real-secret\n")
    original = dotenv.read_bytes()
    if previous is not None:
        config.write_text(previous)
    result = run_deploy(stand, stand["target"], bootstrap=True,
                        SYNTHETIC_SMOKE_ORIGIN="https://wrong.example.com")
    assert result.returncode == 1
    assert "effective public origin" in result.stderr
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["old"]
    assert dotenv.read_bytes() == original
    if previous is None:
        assert not config.exists()
    else:
        assert config.read_text() == previous


@pytest.mark.parametrize("failure", ["SYNTHETIC_BUILD_FAIL", "SYNTHETIC_SMOKE_FAIL"])
def test_bootstrap_failure_rolls_back_to_original_not_candidate(stand: dict, failure: str) -> None:
    result = run_deploy(stand, stand["target"], bootstrap=True, **{failure: "1"})
    assert result.returncode == 1
    assert f'rolling back to {stand["old"]}' in result.stderr
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["old"]
    assert (stand["repo"] / "web/dist/main.js").read_text() == "old-entrypoint"
    assert 'sudo -n systemctl restart agent4k-test.service' in stand["log"].read_text()


def test_dirty_checkout_is_rejected_without_mutation_or_restart(stand: dict) -> None:
    dirty = stand["repo"] / "pyproject.toml"
    dirty.write_text("user-owned local change", encoding="utf-8")
    result = run_deploy(stand, stand["target"], bootstrap=True)
    assert result.returncode == 1
    assert 'tracked local changes' in result.stderr
    assert dirty.read_text() == "user-owned local change"
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["old"]
    assert not stand["log"].exists()


def test_older_target_is_rejected_without_restart(stand: dict) -> None:
    git(stand["repo"], "switch", "--detach", stand["future"])
    result = run_deploy(stand, stand["target"])
    assert result.returncode == 1
    assert 'behind or divergent' in result.stderr
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["future"]
    assert not stand["log"].exists()


@pytest.mark.parametrize("bootstrap", [False, True])
@pytest.mark.parametrize("commit", ["main", "abc; touch bad", "a" * 39, "f" * 40])
def test_invalid_or_missing_commit_is_rejected_before_deploy(stand: dict, commit: str, bootstrap: bool) -> None:
    result = run_deploy(stand, commit, bootstrap=bootstrap)
    assert result.returncode != 0
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["old"]
    assert not stand["log"].exists()
    assert not (stand["repo"] / "bad").exists()


def test_legacy_invocation_without_commit_still_fast_forwards_main(stand: dict) -> None:
    result = run_deploy(stand, "")
    assert result.returncode == 0, result.stderr
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["future"]


def test_commit_outside_main_is_rejected(stand: dict) -> None:
    git(stand["repo"], "switch", "-c", "unreviewed", stand["old"])
    (stand["repo"] / "foreign.txt").write_text("unreviewed", encoding="utf-8")
    git(stand["repo"], "add", ".")
    git(stand["repo"], "commit", "-qm", "Not in origin/main")
    foreign = git(stand["repo"], "rev-parse", "HEAD")
    git(stand["repo"], "switch", "--detach", stand["old"])
    result = run_deploy(stand, foreign, bootstrap=True)
    assert result.returncode != 0
    assert git(stand["repo"], "rev-parse", "HEAD") == stand["old"]
    assert not stand["log"].exists()

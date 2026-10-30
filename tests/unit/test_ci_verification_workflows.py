from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/backend-tests.yml").read_text(encoding="utf-8")
FULL = (ROOT / ".github/workflows/full-verification.yml").read_text(encoding="utf-8")


def test_pull_request_ci_contains_only_fast_jobs() -> None:
    assert "frontend:\n    if: github.event_name == 'pull_request'" in CI
    assert "pytest:\n    if: github.event_name == 'pull_request'" in CI
    assert "Integration tests" not in CI
    assert "Browser acceptance (isolated bootstrap 10.2)" not in CI


def test_each_pull_request_head_full_verification_covers_all_suites() -> None:
    assert "pull_request:" in FULL
    assert "types: [opened, reopened, synchronize]" in FULL
    assert "run-full-verification" not in FULL
    assert "Require run-full-verification label" not in FULL
    assert "labeled" not in FULL
    assert "workflow_dispatch:" not in FULL
    assert "full-verification:" in FULL
    for step in (
        "Unit tests",
        "HTTP contract smoke tests",
        "Integration tests",
        "Browser acceptance (isolated bootstrap 10.2)",
    ):
        assert f"- name: {step}" in FULL


def test_main_push_deploys_without_repeating_pre_merge_checks() -> None:
    deploy = CI.split("  deploy-test:", 1)[1]
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in deploy
    assert "needs:" not in deploy
    assert "workflow_dispatch:" not in CI

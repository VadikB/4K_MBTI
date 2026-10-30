from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/backend-tests.yml").read_text(encoding="utf-8")
FULL = (ROOT / ".github/workflows/full-verification.yml").read_text(encoding="utf-8")


def test_pull_request_skips_expensive_ci_steps() -> None:
    guard = "if: github.event_name != 'pull_request'"
    for step in (
        "Integration tests",
        "Install browser test dependencies",
        "Install Chromium system dependencies",
        "Install Chromium browser",
        "Browser acceptance (isolated bootstrap 10.2)",
    ):
        fragment = CI.split(f"- name: {step}", 1)[1].split("\n      - ", 1)[0]
        assert guard in fragment


def test_manual_full_verification_covers_all_suites() -> None:
    assert "workflow_dispatch:" in FULL
    assert "full-verification:" in FULL
    for step in (
        "Unit tests",
        "HTTP contract smoke tests",
        "Integration tests",
        "Browser acceptance (isolated bootstrap 10.2)",
    ):
        assert f"- name: {step}" in FULL


def test_main_still_requires_full_ci_before_transition_finishes() -> None:
    assert "needs:\n      - frontend\n      - pytest" in CI
    integration = CI.split("- name: Integration tests", 1)[1].split("\n      - ", 1)[0]
    assert "github.event_name != 'pull_request'" in integration

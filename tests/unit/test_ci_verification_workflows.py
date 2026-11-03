from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/backend-tests.yml").read_text(encoding="utf-8")
FULL = (ROOT / ".github/workflows/full-verification.yml").read_text(encoding="utf-8")
PLAYWRIGHT_CI = (ROOT / "tests/browser/playwright.ci.config.mjs").read_text(encoding="utf-8")


def test_pull_request_ci_contains_only_fast_jobs() -> None:
    assert "frontend:\n    if: github.event_name == 'pull_request'" in CI
    assert "pytest:\n    if: github.event_name == 'pull_request'" in CI
    assert "Integration tests" not in CI
    assert "Browser acceptance (isolated bootstrap 10.2)" not in CI


def test_draft_defers_release_gate_until_ready_for_review() -> None:
    assert "types: [opened, reopened, synchronize, ready_for_review]" in CI
    release_step = CI.split("      - name: Verify application release", 1)[1].split(
        "      - name: Explain deferred draft release", 1
    )[0]
    assert "if: github.event.pull_request.draft == false" in release_step
    deferred_step = CI.split("      - name: Explain deferred draft release", 1)[1].split(
        "      - uses: actions/setup-node@v4", 1
    )[0]
    assert "if: github.event.pull_request.draft == true" in deferred_step


def test_full_verification_runs_only_for_ready_pull_request_heads() -> None:
    assert "pull_request:" in FULL
    assert "types: [opened, reopened, synchronize, ready_for_review]" in FULL
    assert "integration:\n    if: github.event.pull_request.draft == false" in FULL
    assert "browser:\n    if: github.event.pull_request.draft == false" in FULL
    assert "converted_to_draft" not in FULL
    assert "run-full-verification" not in FULL
    assert "Require run-full-verification label" not in FULL
    assert "labeled" not in FULL
    assert "workflow_dispatch:" not in FULL
    for step in ("Integration tests", "Browser acceptance — fast lane"):
        assert f"- name: {step}" in FULL
    assert "- name: Unit tests" not in FULL
    assert "- name: HTTP contract smoke tests" not in FULL


def test_full_verification_cancels_obsolete_run_for_same_pull_request() -> None:
    assert "group: full-verification-${{ github.event.pull_request.number }}" in FULL
    assert "cancel-in-progress: true" in FULL


def test_fast_suites_are_not_duplicated_by_full_verification() -> None:
    for step in ("Unit tests", "HTTP contract smoke tests"):
        assert f"- name: {step}" in CI
        assert f"- name: {step}" not in FULL


def test_full_verification_parallelizes_integration_and_browser_runtime() -> None:
    assert "integration:" in FULL
    assert "browser:" in FULL
    assert "fail-fast: false" in FULL
    for shard in ("1/4", "2/4", "3/4", "4/4"):
        assert f'shard: "{shard}"' in FULL
    assert "BROWSER_SUITE: runtime" in FULL
    assert "--fully-parallel" in FULL
    assert "--shard=${{ matrix.shard }}" in FULL


def test_full_verification_preserves_required_aggregate_check() -> None:
    aggregate = FULL.split("  full-verification:", 1)[1]
    assert "if: always() && github.event.pull_request.draft == false" in aggregate
    assert "needs: [integration, browser]" in aggregate
    assert 'test "$INTEGRATION_RESULT" = "success"' in aggregate
    assert 'test "$BROWSER_RESULT" = "success"' in aggregate


def test_browser_lanes_keep_all_specs_and_separate_evidence() -> None:
    assert "BROWSER_SUITE: fast" in FULL
    assert "BROWSER_SUITE: runtime" in FULL
    assert "tests/browser/auth-r03.spec.mjs" not in FULL
    assert "tests/browser/adm28-real.spec.mjs" not in FULL
    assert "tests/browser/path29-participant.spec.mjs" not in FULL
    assert "browserSuite === 'runtime' ? 'runtime.spec.mjs' : '*.spec.mjs'" in PLAYWRIGHT_CI
    assert "browserSuite === 'fast' ? 'runtime.spec.mjs' : undefined" in PLAYWRIGHT_CI
    assert "path.resolve(process.cwd(), '.test-stand/browser-output')" in PLAYWRIGHT_CI
    assert "path.resolve(process.cwd(), '.test-stand/browser-results.json')" in PLAYWRIGHT_CI
    assert "--config tests/browser/playwright.ci.config.mjs" in FULL
    assert "full-verification-browser-${{ matrix.lane }}" in FULL
    assert "playwright-chromium-${{ runner.os }}-${{ hashFiles('package-lock.json') }}" in FULL


def test_main_push_deploys_without_repeating_pre_merge_checks() -> None:
    deploy = CI.split("  deploy-test:", 1)[1]
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in deploy
    assert "needs:" not in deploy
    assert "workflow_dispatch:" not in CI
    assert "- name: Verify merged application release" in deploy
    assert "python scripts/check_release_version.py --base-ref HEAD^" in deploy
    assert deploy.index("Verify merged application release") < deploy.index("Configure SSH")

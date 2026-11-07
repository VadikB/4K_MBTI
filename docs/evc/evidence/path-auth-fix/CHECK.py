"""Offline integrity/recorded-result check, NOT a fresh product/browser test."""
import hashlib
import json
import re
from pathlib import Path

if not __debug__:
    raise SystemExit("OPTIMIZED_PYTHON_FORBIDDEN")

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def specs(suite):
    yield from suite.get("specs", [])
    for child in suite.get("suites", []):
        yield from specs(child)


def results(document):
    for suite in document["suites"]:
        for spec in specs(suite):
            for test in spec["tests"]:
                yield from test["results"]


def check():
    files = read("FILES.json")
    for name, expected in files.items():
        target = (ROOT / name).resolve()
        assert target.is_relative_to(ROOT), name
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected, name
    before = read("before/browser-results.json")
    assert before["stats"]["unexpected"] == 1 and before["stats"]["expected"] == 0
    failed = list(results(before))
    assert len(failed) == 1 and failed[0]["status"] == "failed"
    assert 'Received string:    ""' in re.sub(r'\x1b\[[0-9;]*m', '', failed[0]["error"]["message"])
    for name, count, failures in [("after/targeted-results.json", 4, 0),
                                  ("after/full-results.json", 117, 2),
                                  ("after/followup-results.json", 1, 1)]:
        document = read(name)
        assert document["stats"]["expected"] == count, name
        assert document["stats"]["unexpected"] == failures, name
        assert all(document["stats"][key] == 0 for key in ["flaky", "skipped"]), name
        assert not document["errors"], name
        runs = list(results(document))
        assert len(runs) == count + failures and all(run["retry"] == 0 for run in runs), name
        assert sum(run["status"] == "passed" for run in runs) == count, name
        assert sum(run["status"] == "timedOut" for run in runs) == failures, name
    auth_specs = 0
    for suite in read("after/full-results.json")["suites"]:
        for spec in specs(suite):
            if spec["file"].endswith('auth-recovery.spec.mjs'):
                auth_specs += 1
                assert all(run["status"] == "passed" for test in spec["tests"] for run in test["results"])
    assert auth_specs == 4
    identity = read("code-identity.json")
    assert identity["base"] == "dea8c44a183c2ac5f4b527e53cdeed0a39bcf454"
    assert identity["main_test_last_verified"] == "946a46cb71e5ca5cc99778f036807d6c193188dc"
    assert identity["version"] == "2.0.68" and identity["runtime_sources_changed"] == [
        "web/js/screen-loaders.js", "web/js/screens/chat.js", "web/js/session.js"]
    assert identity["historical_auth_causality"] == "NOT_ESTABLISHED"
    assert identity["prep_diag_01_root_cause"] == "UNKNOWN"
    assert all(value is False for value in identity["external_actions"].values())
    print(json.dumps({"integrity": "PASS", "scope": "recorded_results_not_fresh_execution",
                      "verified_files": len(files), "before": "FAIL_REPRODUCED", "targeted": 4,
                      "auth_admin_browser": "FAIL_117_PASS_2_TIMEOUT",
                      "followup": "FAIL_1_PASS_1_TIMEOUT", "release_ready": False,
                      "prep_root_cause": "UNKNOWN"}, ensure_ascii=False))


if __name__ == "__main__":
    check()

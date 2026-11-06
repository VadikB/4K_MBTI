"""Tamper negatives for the offline audit; no product/DB/browser/provider imports."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evc/evidence/path-final-audit"
spec = importlib.util.spec_from_file_location("path_final_audit_check", EVIDENCE / "CHECK.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


@pytest.fixture
def copied(tmp_path):
    for source in EVIDENCE.glob("*.json"):
        shutil.copyfile(source, tmp_path / source.name)
    shutil.copyfile(EVIDENCE / "path-start-1.3.txt", tmp_path / "path-start-1.3.txt")
    return tmp_path


def change(directory, name, mutate):
    path = directory / name
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(json.dumps(value))


def test_valid_recorded_audit_preserves_failure_and_unknown(copied):
    result = check.validate_semantics(copied)
    assert result["audit_evidence"] == "PASS"
    assert result["auth_diagnostic"] == "FAIL_REPRODUCED"
    assert result["whole_final_path"] == "NOT_RUN"
    assert result["prep_root_cause"] == "UNKNOWN"


@pytest.mark.parametrize("name,mutate,code", [
    ("audit-matrix.json", lambda j: j["rows"].pop(), "AC_IDENTITIES"),
    ("audit-matrix.json", lambda j: j["rows"][-1].update(id="AC01"), "AC_IDENTITIES"),
    ("audit-matrix.json", lambda j: j.update(final_sha_whole_path="PASS"), "WHOLE_PATH_OVERCLAIM"),
    ("audit-matrix.json", lambda j: j["rows"][-1].update(status="PASS"), "AC_COUNTS"),
    ("audit-matrix.json", lambda j: j.update(real_path_sha=j["code_sha"]), "PAID_SHA_RELABELLED"),
    ("auth-diagnostic-results.json", lambda j: j["stats"].update(expected=1, unexpected=0), "AUTH_FALSE_PASS"),
    ("auth-observation.json", lambda j: j.update(historical_causality="PROVEN"), "AUTH_CAUSAL_OVERCLAIM"),
    ("auth-observation.json", lambda j: j.update(heldChatRequests=0), "AUTH_TRANSPORT"),
    ("prep-review.json", lambda j: j.update(root_cause="AUTH_DIAG"), "PREP_INVENTED_CAUSE"),
    ("source-identities.json", lambda j: j.update(all_recorded_runner_files_unchanged=False), "SOURCE_DRIFT"),
    ("release2068-server-readback.json", lambda j: j.update(actual_sha="wrong"), "DEPLOYMENT_SHA"),
])
def test_tampered_audit_is_rejected(copied, name, mutate, code):
    change(copied, name, mutate)
    with pytest.raises(ValueError, match=code):
        check.validate_semantics(copied)

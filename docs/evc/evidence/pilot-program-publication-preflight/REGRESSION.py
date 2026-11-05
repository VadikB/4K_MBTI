"""Reject tampered preflight evidence without editing files or opening a DB."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
from unittest.mock import patch

directory = Path(__file__).parent
check = directory / "CHECK.py"
readback = directory / "readback.json"
value = json.loads(readback.read_bytes())
read_bytes = Path.read_bytes
real_socket = socket.socket

def check_value(candidate):
    def contents(path):
        return json.dumps(candidate, ensure_ascii=False).encode() if path == readback else read_bytes(path)
    try:
        with patch.object(Path, "read_bytes", contents):
            runpy.run_path(str(check))
    finally:
        socket.socket = real_socket

check_value(value)
mutations = [
    lambda v: v.update(transaction_read_only="off"),
    lambda v: v.update(schema_or_data_writes=True),
    lambda v: v["source_comparison"]["cases"].update(actual_sha256="0" * 64),
    lambda v: v["legacy_1_1_source"]["cases"][0].update(content_checksum="0" * 64),
    lambda v: v["legacy_1_1_source"]["cases"][0]["qa_evidence"][0]["evidence_json"]["origin"].update(synthetic=True),
    lambda v: v["candidate"].update(definition_checksum="0" * 64),
    lambda v: v["program_versions"].append({"version": "1.2"}),
    lambda v: v["legacy_1_1_source"].update(source_code_sha="0" * 40),
    lambda v: v["legacy_1_1_source"].update(contains_user_history=True),
    lambda v: v.update(publisher_owner_authorization="INFERRED_FROM_ROLE"),
    lambda v: v["schema_comparison"].update(actual_metadata_checksum="0" * 64),
]
for number, mutate in enumerate(mutations):
    variant = deepcopy(value)
    mutate(variant)
    try:
        check_value(variant)
    except AssertionError:
        pass
    else:
        raise AssertionError(("UNSAFE_EVIDENCE_ACCEPTED", number))
optimized = subprocess.run([sys.executable, "-O", str(check)], capture_output=True, text=True)
assert optimized.returncode != 0 and "EVIDENCE_CHECK_REQUIRES_ASSERTIONS" in optimized.stderr
print(json.dumps({
    "result": "PASS_PREFLIGHT_EVIDENCE_REGRESSION",
    "positive": 1, "negative_mutations_rejected": len(mutations),
    "optimized_mode_rejected": True,
    "evidence_file_mutations": 0, "database_calls": 0, "llm_calls": 0,
}))

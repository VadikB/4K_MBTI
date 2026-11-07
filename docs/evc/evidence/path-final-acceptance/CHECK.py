"""Проверка сохранённых бесплатных evidence; без сети, БД или provider."""
from __future__ import annotations

import hashlib
import gzip
import json
import re
from pathlib import Path

if not __debug__:
    raise SystemExit("OPTIMIZED_PYTHON_FORBIDDEN")

directory = Path(__file__).resolve().parent
root = directory.parents[3]


def require(condition, message):
    if not condition:
        raise SystemExit("FAIL:" + message)


def read(name):
    return json.loads((directory / name).read_bytes())


def specs(node):
    return list(node.get("specs", [])) + [item for suite in node.get("suites", []) for item in specs(suite)]


manifest = read("FILES.json")
for item in manifest["files"]:
    target = (root / item["path"]).resolve()
    require(target.is_relative_to(root) and target.is_file(), "PATH:" + item["path"])
    data = target.read_bytes()
    require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
            "DIGEST:" + item["path"])

before = read("ac05-before.json")
after = read("browser-final-pass.json")
require(before["stats"]["unexpected"] == 2 and before["stats"]["expected"] == 0, "BEFORE_COUNTS")
require(after["stats"]["expected"] == 100 and after["stats"]["unexpected"] == 0
        and after["stats"]["skipped"] == 0 and after["stats"]["flaky"] == 0
        and not after.get("errors"), "AFTER_COUNTS")
before_cases = [item for item in specs(before) if item["title"].startswith("PATH-START AC05")]
require(len(before_cases) == 2, "BEFORE_CASES")
for item in before_cases:
    errors = "\n".join(error.get("message", "") for test in item["tests"]
                       for result in test["results"] for error in result.get("errors", []))
    errors = re.sub(r"\x1b\[[0-9;]*m", "", errors)
    require('Expected: "error"' in errors and 'Received: "success"' in errors, "FALSE_SUCCESS_REPRO")
    matching = [candidate for candidate in specs(after) if candidate["title"] == item["title"]]
    require(len(matching) == 1 and matching[0]["ok"] is True, "AC05_AFTER")
for title in ["UX-ADM27 org-admin assigns the selected assessment to self and a colleague"] + [
    f"PATH-START viewport {width}: long facts, unknown questionnaire, read-only action"
    for width in (1440, 320, 390, 768)
]:
    matching = [item for item in specs(after) if item["title"] == title]
    require(len(matching) == 1 and matching[0]["ok"] is True, "ROLE_OR_VIEWPORT:" + title)

local = read("local-checks.json")
require(local["result"] == "PASS_LOCAL_CHECKS" and local["build_idempotent"] is True
        and local["unchanged_backend_sources"] is True, "LOCAL_CHECKS")
for item in local["results"]:
    require(item["exit_code"] == 0 and not item["signal"] and not item["error"], "PROCESS:" + item["name"])
    require(hashlib.sha256((directory / item["output"]).read_bytes()).hexdigest() == item["sha256"], "LOG_HASH")
require("pass 140" in gzip.decompress((directory / "frontend.txt.gz").read_bytes()).decode(), "FRONTEND_COUNT")
require("25 passed" in gzip.decompress((directory / "http-and-source.txt.gz").read_bytes()).decode(), "HTTP_SOURCE_COUNT")
require(local["llm_calls"] == 0 and local["working_database_used"] is False
        and local["new_ci"] is False and local["merge"] is False and local["deploy"] is False, "BOUNDARIES")
for filename, expected in local["checked_hashes"].items():
    require(hashlib.sha256((root / filename).read_bytes()).hexdigest() == expected, "CHECKED_CODE:" + filename)
for filename, expected in local["dist_after"].items():
    require(hashlib.sha256((root / "web/dist" / filename).read_bytes()).hexdigest() == expected, "DIST:" + filename)

print(json.dumps({"result": "PASS_RECORDED_ACCEPTANCE_EVIDENCE", "files": len(manifest["files"]),
                  "before_ac05": "2 FALSE SUCCESS", "browser": 100, "frontend": 140,
                  "http_and_source": 25, "paid_runtime": "e63eba67d77fb73f7fb9bb219bc3fe5d3807a909",
                  "new_paid_run": False, "new_ci": False, "deployment_changed": False}))

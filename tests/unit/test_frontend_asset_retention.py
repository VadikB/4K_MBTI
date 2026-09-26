from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "retain_previous_frontend_assets.sh"
DEPLOY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy_test_remote.sh"


def _run_retention(current: Path, previous: Path, days: int = 14) -> None:
    subprocess.run(
        ["sh", str(SCRIPT), str(current), str(previous), str(days)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_previous_hashed_chunk_is_retained_without_replacing_current_entrypoint(tmp_path: Path) -> None:
    current = tmp_path / "current"
    previous = tmp_path / "previous"
    current.mkdir()
    previous.mkdir()
    (current / "main.js").write_text("current entrypoint", encoding="utf-8")
    (current / "admin-dashboard-NEW.js").write_text("new chunk", encoding="utf-8")
    (previous / "main.js").write_text("previous entrypoint", encoding="utf-8")
    (previous / "admin-dashboard-OLD.js").write_text("old chunk", encoding="utf-8")

    _run_retention(current, previous)

    assert (current / "main.js").read_text(encoding="utf-8") == "current entrypoint"
    assert (current / "admin-dashboard-NEW.js").read_text(encoding="utf-8") == "new chunk"
    assert (current / "admin-dashboard-OLD.js").read_text(encoding="utf-8") == "old chunk"


def test_expired_hashed_chunk_is_removed(tmp_path: Path) -> None:
    current = tmp_path / "current"
    previous = tmp_path / "previous"
    current.mkdir()
    previous.mkdir()
    expired = previous / "admin-dashboard-EXPIRED.js"
    expired.write_text("expired chunk", encoding="utf-8")
    old_timestamp = time.time() - 16 * 24 * 60 * 60
    os.utime(expired, (old_timestamp, old_timestamp))

    _run_retention(current, previous)

    assert not (current / expired.name).exists()


def test_test_deploy_installs_frontend_build_dependencies() -> None:
    deploy_script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert deploy_script.count("npm ci --include=dev") == 2

from __future__ import annotations

import os
import subprocess
import sys


def _read_external_transfer_setting(value: str | None) -> str:
    environment = os.environ.copy()
    if value is None:
        environment.pop("ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED", None)
    else:
        environment["ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED"] = value
    script = """
import sys
import types

sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)
from Api.config import settings
print(str(settings.assessment_external_answer_transfer_enabled).lower())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return result.stdout.strip()


def test_external_answer_transfer_is_disabled_by_default() -> None:
    assert _read_external_transfer_setting(None) == "false"


def test_external_answer_transfer_can_be_enabled_explicitly() -> None:
    assert _read_external_transfer_setting("true") == "true"

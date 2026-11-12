"""The release CLI may validate and publish only in an owned synthetic test schema."""
from __future__ import annotations

from contextlib import contextmanager
import sys

import pytest

from scripts import publish_assessment_program
from tests.integration.test_arch30_program_definition_db import program_db


pytestmark = pytest.mark.integration


def test_publisher_dry_run_rejects_invalid_inputs_and_publishes_synthetic_draft(
    program_db, monkeypatch, capsys
):
    connection, _ = program_db

    @contextmanager
    def owned_connection():
        yield connection

    monkeypatch.setattr(publish_assessment_program, "get_connection", owned_connection)
    args = ["publish_assessment_program.py", "--code", "f10-synthetic", "--version", "1.0",
            "--name", "Синтетическая программа", "--assignment-ref", "synthetic-f10",
            "--mode", "dialogue", "--configuration-code", "nine-cases",
            "--role-code", "specialist_expert", "--publisher-user-id", "1"]
    before = connection.execute("SELECT COUNT(*) AS n FROM assessment_program_definitions").fetchone()["n"]
    monkeypatch.setattr(sys, "argv", args)
    assert publish_assessment_program.main() == 0
    output = capsys.readouterr().out
    assert "VALIDATED_ONLY" in output and "checksum=" in output
    assert connection.execute("SELECT COUNT(*) AS n FROM assessment_program_definitions").fetchone()["n"] == before

    for status in ("missing", "draft", "retired"):
        if status != "missing":
            connection.execute("UPDATE assessment_configurations SET status=%s WHERE id=30", (status,))
        argv = args.copy()
        if status == "missing":
            argv[argv.index("nine-cases")] = "missing"
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit, match="must be published"):
            publish_assessment_program.main()
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) AS n FROM assessment_program_definitions").fetchone()["n"] == before

    for dependency, message in (("catalog", "must be published"),
                                ("role", "published version")):
        if dependency == "catalog":
            connection.execute("UPDATE m5_catalogs SET status='retired' WHERE id=20")
        else:
            connection.execute("UPDATE assessment_role_profile_versions SET status='draft' WHERE id=50")
        monkeypatch.setattr(sys, "argv", args)
        with pytest.raises(SystemExit, match=message):
            publish_assessment_program.main()
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) AS n FROM assessment_program_definitions").fetchone()["n"] == before

    monkeypatch.setattr(sys, "argv", [*args, "--publish"])
    assert publish_assessment_program.main() == 0
    row = connection.execute("""SELECT status,definition_checksum,assessment_configuration_id,
        catalog_version_id,source_refs_json FROM assessment_program_definitions
        WHERE code='f10-synthetic' AND version='1.0'""").fetchone()
    assert row["status"] == "published"
    assert row["definition_checksum"] in capsys.readouterr().out
    assert row["assessment_configuration_id"] == 30
    assert row["catalog_version_id"] == 20
    assert row["source_refs_json"] == {"methodology_version_id": 1,
                                       "scenario_version_id": 1,
                                       "prompt_bundle_checksum": "prompt-checksum"}

from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.m5_generation_lab import GenerationRequest, begin_run, ensure_lab_schema, finish_run, generate, get_run


@pytest.mark.integration
def test_m5_lab_persists_both_roles_and_idempotent_artifacts(test_database_url):
    schema = "m5_test_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (7)")
        ensure_lab_schema(connection)
        ensure_lab_schema(connection)
        for role in ("team_lead", "project_product_process_manager"):
            request = GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role)
            row, created = begin_run(connection, request=request, user_id=7)
            assert created
            assert row["input_json"]["profile"]["base_role"] == role
            output = generate(row["input_json"])
            finish_run(connection, run_id=str(request.run_id), output=output, error_code=None)
            saved = get_run(connection, str(request.run_id))
            assert saved["status"] == "completed"
            assert saved["output_integrity"] is True
            assert saved["input_integrity"] is True
            assert len(saved["output_json"]["observability"]) == 2
            duplicate, created = begin_run(connection, request=request, user_id=7)
            assert not created
            assert duplicate["output_json"] == output
            changed = request.model_copy(update={"case_id": "SCR.A02"})
            with pytest.raises(ValueError, match="другим запросом"):
                begin_run(connection, request=changed, user_id=7)
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute("UPDATE m5_generation_lab_runs SET input_json = '{}'::jsonb WHERE run_id = %s", (str(request.run_id),))
        assert connection.execute("SELECT count(*) AS n FROM m5_generation_lab_runs").fetchone()["n"] == 2
        connection.rollback()

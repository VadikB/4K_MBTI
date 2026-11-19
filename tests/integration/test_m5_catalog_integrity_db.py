from __future__ import annotations

import json
from shutil import copytree
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api import m5_case_type_catalog
from Api.m5_catalog_integrity import (
    case_admission,
    catalog_readback,
    publication_plan,
    publish_catalog,
    resolve_configuration_catalog,
)


pytestmark = pytest.mark.integration


def evidence(case, scope, *, result="PASS", origin="human_review", usage_scopes=None):
    payload = {
        "schema_version": 1,
        "eligibility": "user_admission",
        "scope": scope,
        "result": result,
        "case_ref": {"id": case["case_id"], "version": case["case_version"],
                     "checksum": case["content_checksum"]},
        "base_role": case["base_role"],
        "usage_scopes": usage_scopes or ["assessment", "qa"],
        "origin": {"type": origin, "actor_ref": "review:owned-test"},
    }
    return payload, checksum(payload)


def test_catalog_publication_is_exact_idempotent_and_immutable(test_database_url, tmp_path, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "task1011_pytest_" + uuid4().hex
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (7),(8)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO organizations VALUES (11)")
        connection.execute("CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY)")
        ensure_m5_runtime_schema(connection)
        manifest = {"dependencies": {"m2": "b" * 64}}
        package = connection.execute(
            """INSERT INTO m5_packages(package_id,package_version,schema_version,status,source_checksum,
               package_checksum,manifest_json,package_json,runtime_rules_json)
               VALUES ('pkg','1.0',2,'FROZEN',%s,%s,%s::jsonb,'{}'::jsonb,'{}'::jsonb) RETURNING id""",
            ("c" * 64, "d" * 64, json.dumps(manifest)),
        ).fetchone()
        content = {"unresolved_decisions": []}
        case = connection.execute(
            """INSERT INTO m5_case_versions(package_id,case_id,case_version,status,base_role,content_json,content_checksum)
               VALUES (%s,'CASE-01','1.0','FROZEN','team_lead',%s::jsonb,%s) RETURNING *""",
            (package["id"], json.dumps(content), checksum(content)),
        ).fetchone()
        for scope in ("case_format", "case_dialogue", "assessment_situation"):
            payload, digest = evidence(case, scope)
            connection.execute(
                """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                   VALUES (%s,%s,'PASS',%s::jsonb,%s)""",
                (case["id"], scope, json.dumps(payload), digest),
            )

        plan = publication_plan(connection, package_db_id=package["id"],
                                case_version_ids=[case["id"]], usage_scope="assessment",
                                organization_id=11)
        assert plan["publishable"] is True
        catalog_ref = m5_case_type_catalog.load_case_type_catalog().ref.model_dump()
        assert plan["case_type_catalog_ref"] == catalog_ref
        dry_run = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1", dry_run=True,
        )
        assert dry_run["dry_run"] is True
        published = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1",
        )
        repeated = publish_catalog(
            connection, catalog_id="controlled", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]],
            usage_scope="assessment", organization_id=11, published_by=7,
            decision_basis="owned integration review", idempotency_key="publish-1",
        )
        assert repeated["idempotent"] is True
        with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
            publish_catalog(
                connection, catalog_id="controlled", catalog_version="2.0",
                package_db_id=package["id"], case_version_ids=[case["id"]],
                usage_scope="assessment", organization_id=11, published_by=7,
                decision_basis="different request", idempotency_key="publish-1",
            )
        readback = catalog_readback(connection, published["catalog_db_id"])
        assert readback["manifest_checksum"] == published["manifest_checksum"]
        assert readback["manifest"]["case_type_catalog_ref"] == catalog_ref

        old_manifest = readback["manifest"].copy()
        del old_manifest["case_type_catalog_ref"]
        old_manifest["catalog_id"] = "legacy"
        old_request = {**plan, "catalog_id": "legacy", "catalog_version": "1.0",
                       "published_by": 7, "decision_basis": "legacy review"}
        del old_request["case_type_catalog_ref"]
        old_catalog = connection.execute(
            """INSERT INTO m5_catalogs
               (catalog_id,catalog_version,organization_id,usage_scope,package_db_id,manifest_json,
                manifest_checksum,status,published_by,decision_basis,idempotency_key,request_hash,published_at)
               VALUES ('legacy','1.0',11,'assessment',%s,%s::jsonb,%s,'published',7,'legacy review','legacy',%s,NOW())
               RETURNING id""",
            (package["id"], json.dumps(old_manifest), checksum(old_manifest), checksum(old_request)),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO m5_catalog_case_versions(catalog_db_id,case_version_id) VALUES (%s,%s)",
            (old_catalog, case["id"]),
        )
        assert publish_catalog(
            connection, catalog_id="legacy", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[case["id"]], usage_scope="assessment",
            organization_id=11, published_by=7, decision_basis="legacy review", idempotency_key="legacy",
        )["catalog_db_id"] == old_catalog

        copied_catalog = copytree(m5_case_type_catalog.CATALOG_DIR, tmp_path / "case-type-catalog")
        source = copied_catalog / m5_case_type_catalog.SOURCE_NAME
        with monkeypatch.context() as patch:
            patch.setattr(m5_case_type_catalog, "CATALOG_DIR", copied_catalog)
            source.write_bytes(b"substituted source")
            for error in ("CHECKSUM_MISMATCH", "UNAVAILABLE"):
                with pytest.raises(ValueError, match=f"M5_CASE_TYPE_CATALOG_{error}: m5-case-type-catalog@1.0"):
                    publish_catalog(
                        connection, catalog_id="invalid-source", catalog_version="1.0",
                        package_db_id=package["id"], case_version_ids=[case["id"]], usage_scope="assessment",
                        organization_id=11, published_by=7, decision_basis="test source", idempotency_key="bad-source",
                    )
                assert catalog_readback(connection, old_catalog)["manifest"] == old_manifest
                assert catalog_readback(connection, published["catalog_db_id"]) == readback
                source.unlink(missing_ok=True)
        assert connection.execute(
            "SELECT 1 FROM m5_catalogs WHERE catalog_id='invalid-source'"
        ).fetchone() is None

        second_content = {"unresolved_decisions": [], "variant": "disjoint"}
        second_case = connection.execute(
            """INSERT INTO m5_case_versions(package_id,case_id,case_version,status,base_role,content_json,content_checksum)
               VALUES (%s,'CASE-02','1.0','FROZEN','team_lead',%s::jsonb,%s) RETURNING *""",
            (package["id"], json.dumps(second_content), checksum(second_content)),
        ).fetchone()
        for scope in ("case_format", "case_dialogue", "assessment_situation"):
            payload, digest = evidence(second_case, scope)
            connection.execute(
                """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                   VALUES (%s,%s,'PASS',%s::jsonb,%s)""",
                (second_case["id"], scope, json.dumps(payload), digest),
            )
        with pytest.raises(ValueError, match=r"M5_CASE_TYPE_UNKNOWN: CT99 at /case_type_ids/0 .*CASE-02"):
            with connection.transaction():
                connection.execute(
                    "UPDATE m5_case_versions SET content_json=%s::jsonb WHERE id=%s",
                    (json.dumps({**second_content, "schema_version": 3, "case_type_ids": ["CT99"]}), second_case["id"]),
                )
                publication_plan(connection, package_db_id=package["id"], case_version_ids=[second_case["id"]],
                                 usage_scope="assessment")
        second = publish_catalog(
            connection, catalog_id="controlled-disjoint", catalog_version="1.0",
            package_db_id=package["id"], case_version_ids=[second_case["id"]],
            usage_scope="assessment", organization_id=11, published_by=8,
            decision_basis="owned disjoint catalog regression", idempotency_key="publish-2",
        )
        connection.execute(
            "CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,status TEXT,catalog_version_id BIGINT)"
        )
        connection.execute(
            "INSERT INTO assessment_configurations VALUES (101,'published',%s),(102,'published',%s)",
            (published["catalog_db_id"], second["catalog_db_id"]),
        )
        first_ref = resolve_configuration_catalog(connection, configuration_id=101, usage_scope="assessment")
        second_ref = resolve_configuration_catalog(connection, configuration_id=102, usage_scope="assessment")
        assert first_ref["db_id"] != second_ref["db_id"]
        first_members = set(catalog_readback(connection, first_ref["db_id"])["manifest"]["case_version_ids"])
        second_members = set(catalog_readback(connection, second_ref["db_id"])["manifest"]["case_version_ids"])
        assert first_members and second_members and first_members.isdisjoint(second_members)
        with pytest.raises(psycopg.Error, match="Published M5 catalog is immutable"):
            with connection.transaction():
                connection.execute("UPDATE m5_catalogs SET catalog_version='2.0' WHERE id=%s",
                                   (published["catalog_db_id"],))
        with pytest.raises(psycopg.Error, match="Published M5 catalog membership is immutable"):
            with connection.transaction():
                connection.execute("DELETE FROM m5_catalog_case_versions WHERE catalog_db_id=%s",
                                   (published["catalog_db_id"],))

        failing, failing_digest = evidence(case, "case_dialogue", result="FAIL")
        connection.execute(
            """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
               VALUES (%s,'case_dialogue','FAIL',%s::jsonb,%s)""",
            (case["id"], json.dumps(failing), failing_digest),
        )
        blocked = publication_plan(connection, package_db_id=package["id"],
                                   case_version_ids=[case["id"]], usage_scope="assessment")
        assert blocked["publishable"] is False
        assert "QA_EVIDENCE_FAIL:case_dialogue" in blocked["decisions"][0]["reasons"]

        mismatched, mismatched_digest = evidence(case, "case_dialogue")
        mismatched["eligibility"] = "laboratory_only"
        mismatched_digest = checksum(mismatched)
        latest = connection.execute(
            """INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
               VALUES (%s,'case_dialogue','PASS',%s::jsonb,%s) RETURNING id""",
            (case["id"], json.dumps(mismatched), mismatched_digest),
        ).fetchone()
        latest_blocked = publication_plan(connection, package_db_id=package["id"],
                                          case_version_ids=[case["id"]], usage_scope="assessment")
        assert latest_blocked["publishable"] is False
        decision = latest_blocked["decisions"][0]
        assert "QA_EVIDENCE_ELIGIBILITY_MISMATCH:case_dialogue" in decision["reasons"]
        admission = case_admission(connection, case_version_id=case["id"], usage_scope="assessment")
        selected = next(item for item in admission["evidence_considered"]
                        if item["scope"] == "case_dialogue")
        assert selected["id"] == latest["id"]
        connection.rollback()

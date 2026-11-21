from __future__ import annotations

import copy
import json
from contextlib import nullcontext
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import database
from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api.m5_case_type_catalog import load_case_type_catalog
from Api.m5_catalog_integrity import publication_plan
from Api.m5_package import digest, json_bytes
from Api.m5_storage import M5ImportConflict, import_package, package_readback
from Api.m5_storage import prepare_assessment_situation
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_rule_engine import ControlledCharacterAdapter, ControlledSemanticAdapter
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package, resolve_runtime_rules
from Api.m5_scenario_runtime import build_c45, start, submit_turn, trace, transition
from Api.m6_input_resolver import resolve as resolve_m6_input
from scripts.build_m5_sales_package import build_execution_rules
from scripts.build_m5_functional_package import OUTPUT
from scripts import plan_specialist_program_release as release

RUNTIME_PACKAGE = OUTPUT.parent.parent / "functional-personalization-runtime/1.2.0"
FUNCTIONAL_PACKAGES = OUTPUT.parent


@pytest.fixture
def specialist_release_connection(test_database_url, monkeypatch):
    schema = psycopg.sql.Identifier("m5_release_" + uuid4().hex)
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(schema))
        connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(schema))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO organizations VALUES (11)")
        connection.execute(
            "CREATE TABLE assessment_personalized_profiles "
            "(id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, "
            "provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)"
        )
        ensure_m5_runtime_schema(connection)
        connection.execute(
            """INSERT INTO assessment_personalized_profiles
               VALUES (7,'ready','{"base_role":"specialist_expert"}','{}',%s)""", ("7" * 64,),
        )
        connection.commit()
        monkeypatch.setattr(database, "get_connection", lambda: nullcontext(connection))
        try:
            yield connection
        finally:
            connection.rollback()
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(schema))


@pytest.mark.integration
def test_specialist_cli_publishes_after_working_import_and_preserves_snapshots(
    specialist_release_connection, monkeypatch, capsys,
):
    connection = specialist_release_connection

    def run_cli(*args):
        monkeypatch.setattr("sys.argv", ["plan_specialist_program_release.py", "--historical-0.5", *args])
        assert release.main() == 0
        return json.loads(capsys.readouterr().out)["database"]

    draft = run_cli("--apply-import")
    draft_package = draft["readback"]["package"]
    draft_case = draft["readback"]["cases"][0]
    assert draft_package["package_version"] == "0.5"
    assert draft_case["status"] == "WORKING"
    assert draft_package["package_checksum"] == checksum({
        "package": draft_package["package_json"], "manifest": draft_package["manifest_json"],
    })
    case_id, version = draft_case["case_id"], draft_case["case_version"]
    cycle, session = create_cycle_session_for_case(
        connection, personalized_profile_id=7, case_id=case_id, case_version=version,
        created_by=99, usage_scope="qa",
    )
    as_id = str(uuid4())
    as_snapshot = prepare_assessment_situation(
        connection, assessment_situation_id=as_id, case_id=case_id, case_version=version,
        personalized_profile_id=7, cycle_db_id=cycle["id"], session_db_id=session["id"],
        substitutions=[], usage_scope="qa", qa_authorized_by=99,
        policy={"id": "aud-01", "version": "1", "allowed_case_statuses": ["WORKING"],
                "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"]},
        runtime_rule_version_id=draft["runtime"]["id"],
    )
    old_trace = trace(connection, as_id)
    connection.commit()

    publish = ("--publish-admitted-catalog", "--published-by", "99", "--usage-scope", "qa",
               "--organization-id", "11", "--catalog-id", "aud-01", "--idempotency-key", "aud-01")
    monkeypatch.setattr("sys.argv", ["plan_specialist_program_release.py", "--historical-0.5", *publish, "--decision-basis", " "])
    with pytest.raises(ValueError, match="SPECIALIST_ADMISSION_DECISION_BASIS_REQUIRED"):
        release.main()
    assert connection.execute("SELECT count(*) AS n FROM m5_catalogs").fetchone()["n"] == 0
    assert connection.execute("SELECT count(*) AS n FROM m5_packages").fetchone()["n"] == 1

    publish += ("--decision-basis", "AUD-01 synthetic QA evidence")
    first = run_cli(*publish)
    catalog = first["catalog_readback"]
    manifest = catalog["manifest"]
    admitted_package = first["readback"]["package"]
    runtime_db_id = first["runtime"]["id"]
    assert manifest["usage_scope"] == "qa"
    assert manifest["organization_id"] == 11
    assert manifest["case_type_catalog_ref"] == load_case_type_catalog().ref.model_dump()
    assert manifest["package_ref"] == {
        "id": draft_package["package_id"], "version": "0.5-admitted.1-qa",
        "checksum": admitted_package["package_checksum"],
    }
    assert admitted_package["manifest_json"]["source_package_ref"] == {
        "id": draft_package["package_id"], "version": "0.5", "checksum": draft_package["package_checksum"],
    }
    artifacts = {item["name"]: item["sha256"] for item in admitted_package["manifest_json"]["artifacts"]}
    assert artifacts["case-package.json"] == digest(json_bytes(admitted_package["package_json"]))
    assert artifacts["execution-rules.json"] == digest(json_bytes(admitted_package["runtime_rules_json"]))
    assert admitted_package["package_checksum"] == checksum({
        "package": admitted_package["package_json"], "manifest": admitted_package["manifest_json"],
    })
    runtime = connection.execute("SELECT * FROM m5_runtime_rule_versions WHERE id=%s", (runtime_db_id,)).fetchone()
    runtime_ref = manifest["runtime_rule_ref"]
    assert runtime_ref["artifact_version"] == "1.2.1-qa"
    assert runtime_ref["manifest_checksum"] == digest(json_bytes(runtime["manifest_json"]))
    assert runtime_ref["rules_checksum"] == checksum(runtime["rules_json"])
    assert runtime["manifest_json"]["source"]["case_package_version"] == "0.5-admitted.1-qa"

    cases = first["readback"]["cases"]
    assert [item["case_id"] for item in cases] == release.EXPECTED_CASE_IDS
    assert sorted(item["id"] for item in cases) == manifest["case_version_ids"]
    bindings = {}
    for working, admitted in zip(draft["readback"]["cases"], cases, strict=True):
        assert admitted["case_version"] == working["case_version"] + "-admitted.1-qa"
        assert admitted["status"] == "FROZEN"
        row = connection.execute(
            """SELECT binding_json,binding_checksum FROM m5_runtime_rule_case_bindings
               WHERE runtime_rule_version_id=%s AND case_version_id=%s""", (runtime_db_id, admitted["id"]),
        ).fetchone()
        binding = row["binding_json"]
        bindings[admitted["case_id"]] = binding
        assert binding["case_version"] == admitted["case_version"]
        assert binding["case_checksum"] == admitted["content_checksum"]
        assert checksum(binding) == row["binding_checksum"]
        rules, ref = resolve_runtime_rules(
            connection, case_version_id=admitted["id"], case_id=admitted["case_id"],
            legacy_rules={}, catalog_db_id=catalog["id"],
        )
        assert rules["cases"][admitted["case_id"]]["case_version"] == admitted["case_version"]
        assert ref["version"] == "1.2.1-qa"
    binding_artifact = {key: runtime["manifest_json"][key] for key in
                        ("schema_version", "id", "version", "status", "owner")}
    binding_artifact["case_bindings"] = bindings
    assert runtime["manifest_json"]["artifacts"][0]["sha256"] == digest(json_bytes(binding_artifact))
    assessment_plan = publication_plan(
        connection, package_db_id=admitted_package["id"], case_version_ids=manifest["case_version_ids"],
        usage_scope="assessment", runtime_rule_version_id=runtime_db_id,
    )
    assert not assessment_plan["publishable"]
    assert all("QA_EVIDENCE_ORIGIN_NOT_ALLOWED:case_format" in item["reasons"]
               for item in assessment_plan["decisions"])
    with pytest.raises(ValueError, match="M5_RUNTIME_RULE_CATALOG_MISMATCH"):
        resolve_runtime_rules(
            connection, case_version_id=draft_case["id"], case_id=case_id, legacy_rules={},
            catalog_db_id=catalog["id"], runtime_rule_version_id=draft["runtime"]["id"],
        )
    with pytest.raises(ValueError, match="M5_RUNTIME_RULE_CATALOG_MISMATCH"):
        resolve_runtime_rules(
            connection, case_version_id=cases[0]["id"], case_id=case_id, legacy_rules={},
            catalog_db_id=catalog["id"], runtime_rule_version_id=draft["runtime"]["id"],
        )

    repeated_draft = run_cli("--apply-import")
    assert repeated_draft["import"] == {**draft["import"], "created": False}
    assert repeated_draft["readback"] == draft["readback"]
    repeated = run_cli(*publish)
    assert repeated["import"] == {**first["import"], "created": False}
    assert repeated["runtime"] == {**first["runtime"], "created": False}
    assert repeated["catalog"] == {**first["catalog"], "idempotent": True}
    assert repeated["catalog_readback"] == catalog
    counts = connection.execute("""
        SELECT (SELECT count(*) FROM m5_packages) AS packages,
               (SELECT count(*) FROM m5_case_versions) AS cases,
               (SELECT count(*) FROM m5_runtime_rule_versions) AS rules,
               (SELECT count(*) FROM m5_catalogs) AS catalogs,
               (SELECT count(*) FROM m5_qa_evidence) AS evidence
    """).fetchone()
    assert counts == {"packages": 2, "cases": 18, "rules": 2, "catalogs": 1, "evidence": 27}
    for column in ("package_json", "runtime_rules_json"):
        changed = {**admitted_package[column], "changed": True}
        with pytest.raises(M5ImportConflict, match="M5_PACKAGE_VERSION_CONTENT_CONFLICT"):
            import_package(
                connection, manifest=admitted_package["manifest_json"],
                package=changed if column == "package_json" else admitted_package["package_json"],
                execution_rules=changed if column == "runtime_rules_json" else admitted_package["runtime_rules_json"],
            )
    with pytest.raises(ValueError, match="M5_RUNTIME_RULE_VERSION_CONFLICT"):
        import_runtime_rule_version(
            connection, {"manifest": runtime["manifest_json"], "manifest_checksum": runtime["manifest_checksum"],
                         "bindings": {"case_bindings": bindings}},
            {**runtime["rules_json"], "changed": True}, package_db_id=admitted_package["id"],
        )
    ordinary = run_cli(
        "--publish-admitted-catalog", "--published-by", "99", "--decision-basis", "AUD-01 fixture review",
        "--catalog-id", "aud-01-assessment", "--idempotency-key", "aud-01-assessment",
    )
    ordinary_manifest = ordinary["catalog_readback"]["manifest"]
    assert ordinary_manifest["usage_scope"] == "assessment"
    assert ordinary_manifest["package_ref"]["version"] == "0.5-admitted.1"
    assert ordinary_manifest["runtime_rule_ref"]["artifact_version"] == "1.2.1"
    assert set(manifest["case_version_ids"]).isdisjoint(ordinary_manifest["case_version_ids"])
    assert run_cli(*publish)["catalog_readback"] == catalog
    assert trace(connection, as_id) == old_trace
    stored = connection.execute(
        """SELECT case_version_id,snapshot_json,snapshot_checksum,execution_payload_json
           FROM m5_assessment_situations WHERE id=%s""", (as_snapshot["id"],),
    ).fetchone()
    assert stored["case_version_id"] == draft_case["id"]
    assert stored["snapshot_checksum"] == checksum(stored["snapshot_json"])
    assert stored["snapshot_json"]["case_ref"] == as_snapshot["snapshot"]["case_ref"]
    assert stored["execution_payload_json"] == as_snapshot["execution_payload"]


@pytest.mark.integration
@pytest.mark.parametrize("previous_version", ["0.2", "0.3"])
def test_functional_package_round_trip_is_idempotent_and_preserves_old_versions(
    test_database_url, previous_version
):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    previous = FUNCTIONAL_PACKAGES / previous_version
    previous_package = json.loads((previous / "case-package.json").read_text())
    previous_manifest = json.loads((previous / "manifest.json").read_text())
    previous_rules = json.loads((previous / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_functional_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute(
            "CREATE TABLE assessment_personalized_profiles "
            "(id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, "
            "provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)"
        )
        ensure_m5_runtime_schema(connection)
        old_import = import_package(
            connection,
            package=previous_package,
            manifest=previous_manifest,
            execution_rules=previous_rules,
        )
        old_readback_before = package_readback(connection, old_import["package_db_id"])
        old_checksums = {
            item["case_id"]: item["content_checksum"] for item in old_readback_before["cases"]
        }
        first = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        second = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        assert first["created"] is True
        assert second["created"] is False
        old_readback_after = package_readback(connection, old_import["package_db_id"])
        assert {
            item["case_id"]: item["content_checksum"] for item in old_readback_after["cases"]
        } == old_checksums
        assert connection.execute("SELECT count(*) AS count FROM m5_packages").fetchone()["count"] == 2
        assert connection.execute("SELECT count(*) AS count FROM m5_case_versions").fetchone()["count"] == 18
        old_case_id = old_readback_after["cases"][0]["id"]
        new_case_id = package_readback(connection, first["package_db_id"])["cases"][0]["id"]
        catalog_ids = []
        for suffix, package_id, case_version_id in (
            ("old", old_import["package_db_id"], old_case_id),
            ("new", first["package_db_id"], new_case_id),
        ):
            catalog = connection.execute("""
                INSERT INTO m5_catalogs
                    (catalog_id,catalog_version,usage_scope,package_db_id,manifest_json,
                     manifest_checksum,status,published_by,decision_basis,idempotency_key,
                     request_hash,published_at)
                VALUES (%s,'1','qa',%s,%s::jsonb,%s,'published',99,'R03 isolated regression',
                        %s,%s,NOW()) RETURNING id
            """, (
                f"r03-{previous_version}-{suffix}", package_id,
                json.dumps({"case_version_ids": [case_version_id]}),
                f"{previous_version}-{suffix}-manifest", f"{previous_version}-{suffix}-key",
                f"{previous_version}-{suffix}-request",
            )).fetchone()
            connection.execute(
                "INSERT INTO m5_catalog_case_versions(catalog_db_id,case_version_id) VALUES (%s,%s)",
                (catalog["id"], case_version_id),
            )
            catalog_ids.append(int(catalog["id"]))
        linked = connection.execute("""
            SELECT member.catalog_db_id,cv.package_id,cv.content_checksum
            FROM m5_catalog_case_versions member
            JOIN m5_case_versions cv ON cv.id=member.case_version_id
            WHERE member.catalog_db_id=ANY(%s) ORDER BY member.catalog_db_id
        """, (catalog_ids,)).fetchall()
        assert {item["package_id"] for item in linked} == {
            old_import["package_db_id"], first["package_db_id"]
        }
        assert next(item for item in linked if item["package_id"] == old_import["package_db_id"])[
            "content_checksum"
        ] == old_checksums[previous_package["cases"][0]["case_id"]]
        readback = package_readback(connection, first["package_db_id"])
        assert [(item["case_id"], item["case_version"]) for item in readback["cases"]] == [
            (f"CASE.SPEC.{number:02d}", version) for number, version in enumerate(
                ("v0.5", "v0.6", "v0.4", "v0.5", "v0.5", "v0.4", "v0.4", "v0.4", "v0.4"), 1
            )
        ]
        assert sum(item["target_count"] for item in readback["cases"]) == 55
        stored = readback["package"]["runtime_rules_json"]
        assert stored["cases"]["CASE.SPEC.02"]["actorless"] is True
        assert stored["cases"]["CASE.SPEC.07"]["actorless"] is True
        assert stored["cases"]["CASE.SPEC.03"]["scenario"][0]["condition"]
        changed = copy.deepcopy(package)
        changed["cases"][0]["passport"]["16 Инвариантное ядро"] = {"changed": True}
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest, execution_rules=rules)
        connection.rollback()


@pytest.mark.integration
def test_versioned_runtime_rules_execute_all_nine_functional_cases(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    legacy_rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    loaded = load_runtime_rule_package(
        RUNTIME_PACKAGE, package["cases"], expected_case_package_version="0.5"
    )
    compiled = build_execution_rules(package["cases"], loaded["bindings"])
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_functional_runtime_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute(
            "CREATE TABLE assessment_personalized_profiles "
            "(id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, "
            "provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)"
        )
        ensure_m5_runtime_schema(connection)
        import_package(connection, package=package, manifest=manifest, execution_rules=legacy_rules)
        imported_rules = import_runtime_rule_version(connection, loaded, compiled)
        repeated_rules = import_runtime_rule_version(connection, loaded, compiled)
        assert repeated_rules == {**imported_rules, "created": False}
        with pytest.raises(psycopg.Error, match="Versioned M5 runtime rules are immutable"):
            with connection.transaction():
                connection.execute(
                    "UPDATE m5_runtime_rule_versions SET owner='changed' WHERE id=%s",
                    (imported_rules["id"],),
                )
        connection.execute(
            "INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
            (json.dumps({"base_role": "specialist_expert"}), "7" * 64),
        )
        case_by_id = {case["case_id"]: case for case in package["cases"]}
        expected_calls = {case_id: sum(
            len(event.get("speaker_ids") or [])
            for event in binding["events"].values() if event["function"] == "character_reaction"
        ) for case_id, binding in loaded["bindings"]["case_bindings"].items()}
        for case_id, case in case_by_id.items():
            cycle, session = create_cycle_session_for_case(
                connection, personalized_profile_id=7, case_id=case_id,
                case_version=case["version"], created_by=99, usage_scope="qa",
            )
            prepared = prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=case_id,
                case_version=case["version"], personalized_profile_id=7,
                cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]),
                substitutions=[], policy={
                    "id": "pers-runtime-qa", "version": "1",
                    "allowed_case_statuses": ["WORKING"],
                    "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"],
                },
                usage_scope="qa", qa_authorized_by=99,
                runtime_rule_version_id=imported_rules["id"],
            )
            assert prepared["execution_payload"]["runtime_rule_ref"]["version"] == "1.2.0"
            reactions = [item for item in prepared["execution_payload"]["materials"]
                         if item["kind"] == "character_reaction"]
            decisions = {f"{item['material_id']}:character_reaction": "TRUE" for item in reactions}
            responses = {item["material_id"]: f"Ответ {item['speaker_id']}" for item in reactions}
            start(connection, prepared["assessment_situation_id"])
            turn = submit_turn(
                connection, assessment_situation_id=prepared["assessment_situation_id"],
                request_id=f"runtime-{case_id}", turn_id=str(uuid4()), content="Проверочный содержательный ход",
                semantic_adapter=ControlledSemanticAdapter(decisions),
                character_adapter=ControlledCharacterAdapter(responses),
            )
            calls = [item for item in turn["events"] if item["event_type"] == "character_response"]
            assert len(calls) == expected_calls[case_id]
            if case_id in {"CASE.SPEC.02", "CASE.SPEC.07"}:
                assert calls == []
            if case_id == "CASE.SPEC.01":
                transition(connection, assessment_situation_id=prepared["assessment_situation_id"],
                           action="scenario_end", reason="A01 preservation", request_id="a01-end")
                transition(connection, assessment_situation_id=prepared["assessment_situation_id"],
                           action="close", reason="A01 preservation", request_id="a01-close")
                handoff = build_c45(connection, prepared["assessment_situation_id"])
                _, m6_input = resolve_m6_input(connection, str(handoff["handoff_id"]))
                source_targets = {
                    item["IndicatorID"]: item
                    for item in case["author_assessment_situation"]["IndicatorObservability"]
                }
                assert len(m6_input["indicator_targets"]) == len(source_targets)
                for target in m6_input["indicator_targets"]:
                    source = source_targets[target["indicator_id"]]
                    assert target["observation_condition"] == source["Конкретное условие"]
                    assert target["material_refs"] == source["Материалы и факты"]
                    assert target["adaptation_constraints"] == source["Что сохранить при адаптации"]
                    assert target["invariant_refs"] == source["Связанные инварианты"]
        connection.rollback()


@pytest.mark.integration
def test_passport_bank_cli_build_import_publish_and_replay(specialist_release_connection, monkeypatch, capsys):
    from Api.m5_passport_generation import BANK_PACKAGE
    from scripts.build_m5_passport_bank import RUNTIME_PACKAGE as passport_rules

    connection = specialist_release_connection

    def cli(*options):
        monkeypatch.setattr("sys.argv", ["plan_specialist_program_release.py", *options])
        assert release.main() == 0
        return json.loads(capsys.readouterr().out)["database"]

    previous = cli("--historical-0.5", "--apply-import")
    old_case = previous["readback"]["cases"][0]
    old_id = str(uuid4())
    cycle, session = create_cycle_session_for_case(
        connection, personalized_profile_id=7, case_id=old_case["case_id"], case_version=old_case["case_version"],
        created_by=99, usage_scope="qa",
    )
    prepare_assessment_situation(
        connection, assessment_situation_id=old_id, case_id=old_case["case_id"], case_version=old_case["case_version"],
        personalized_profile_id=7, cycle_db_id=cycle["id"], session_db_id=session["id"], substitutions=[],
        usage_scope="qa", qa_authorized_by=99, runtime_rule_version_id=previous["runtime"]["id"],
        policy={"id": "history-fixture", "version": "1", "allowed_case_statuses": ["WORKING"],
                "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"]},
    )
    old_trace = trace(connection, old_id)
    passport_01 = cli("--passport-01", "--apply-import")
    assert passport_01["import"]["created"] and passport_01["runtime"]["created"]
    assert read_rules_version(connection, passport_01["runtime"]["id"]) == "1.3.0"
    draft = cli("--apply-import")
    assert not draft["import"]["created"] and draft["runtime"]["created"]
    assert draft["import"]["package_db_id"] == passport_01["import"]["package_db_id"]
    assert len(draft["readback"]["cases"]) == 9
    assert not cli("--apply-import")["runtime"]["created"]
    assert read_rules_version(connection, draft["runtime"]["id"]) == "1.4.0"
    assert load_runtime_rule_package(passport_rules, json.loads(
        (BANK_PACKAGE / "case-package.json").read_bytes())["cases"])["manifest"]["schema_version"] == 2
    common = ("--publish-admitted-catalog", "--published-by", "99", "--organization-id", "11",
              "--catalog-id", "passport-bank-fixture", "--decision-basis", "isolated synthetic test")
    monkeypatch.setattr("sys.argv", ["plan_specialist_program_release.py", *common])
    with pytest.raises(ValueError, match="M5_PASSPORT_BANK_ASSESSMENT_EVIDENCE_REQUIRED"):
        release.main()
    old_publication = cli("--passport-01", *common, "--usage-scope", "qa")
    published = cli(*common, "--usage-scope", "qa")
    repeat = cli(*common, "--usage-scope", "qa")
    assert old_publication["catalog"]["catalog_db_id"] != published["catalog"]["catalog_db_id"]
    assert read_rules_version(connection, old_publication["runtime"]["id"]) == "1.3.1-qa"
    assert published["catalog"]["catalog_db_id"] == repeat["catalog"]["catalog_db_id"]
    assert not repeat["import"]["created"] and not repeat["runtime"]["created"]
    assert read_rules_version(connection, published["runtime"]["id"]) == "1.4.1-qa"
    for case in published["readback"]["cases"]:
        content = connection.execute("SELECT content_json FROM m5_case_versions WHERE id=%s",
                                     (case["id"],)).fetchone()["content_json"]
        assert content["schema_version"] == 4
        assert "author_assessment_situation" not in content
        assert content["case_type_ids"]
        assert case["content_checksum"] == checksum(content)
    saved = package_readback(connection, previous["import"]["package_db_id"])
    assert saved["package"]["package_checksum"] == previous["readback"]["package"]["package_checksum"]
    assert [row["id"] for row in saved["cases"]] == [row["id"] for row in previous["readback"]["cases"]]
    assert trace(connection, old_id) == old_trace
    readback = published["catalog_readback"]
    assert readback["manifest_checksum"] == checksum(readback["manifest"])
    assert len(readback["manifest"]["case_version_ids"]) == 9
    assert readback["manifest"]["case_type_catalog_ref"] == load_case_type_catalog().ref.model_dump()


def read_rules_version(connection, runtime_version_id):
    return connection.execute(
        "SELECT artifact_version FROM m5_runtime_rule_versions WHERE id=%s", (runtime_version_id,)
    ).fetchone()["artifact_version"]

"""BANK-01 readback and Cycle pinning in an isolated PostgreSQL schema."""
import json
from uuid import uuid4

import pytest

from Api.assessment_contexts import create_personalized_profile
from Api.cycle_execution_manifest import resolve_cycle_dependency
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import case_admission, publication_plan, resolve_configuration_catalog
from Api.m5_cycle_runtime import create_cycle_session_for_case, read_cycle, start_session
from Api.m5_package import digest
from Api.m5_passport import load_m2
from Api.m5_passport_generation import M2, SOURCE_MANIFEST
from Api.m5_runtime_rules import resolve_runtime_rules
from Api.m5_storage import M5ImportConflict, import_package, prepare_assessment_situation
from scripts.build_m5_passport_bank import BATTERY_PACKAGE, BATTERY_RUNTIME
from scripts.plan_specialist_program_release import publish_diagnostic_battery
from tests.integration.test_m10_product_path_db import product_db


def install_battery(connection):
    return publish_diagnostic_battery(
        connection, published_by=99, organization_id=10,
        catalog_id="specialist-battery-diagnostic", catalog_version="0.7-qa",
        idempotency_key="bank-01-isolated", decision_basis="BANK-01 synthetic source readback",
    )


def pointer(original, ref):
    value = original
    for token in ref.split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


@pytest.mark.integration
def test_battery_import_readback_and_explicit_diagnostic_cycles(product_db):
    with product_db() as connection:
        receipt = install_battery(connection)
        repeated = install_battery(connection)
        assert receipt["import"]["created"] and not repeated["import"]["created"]
        assert receipt["runtime"]["created"] and not repeated["runtime"]["created"]
        assert not receipt["catalog"]["idempotent"] and repeated["catalog"]["idempotent"]
        assert receipt["catalog_readback"] == repeated["catalog_readback"]
        package = receipt["readback"]["package"]
        cases = receipt["readback"]["cases"]
        assert len(cases) == 9
        catalog = receipt["catalog"]["catalog_db_id"]
        rules_id = receipt["runtime"]["id"]
        manifest = json.loads((BATTERY_PACKAGE / "sources/manifest.json").read_bytes())
        m2, _ = load_m2(M2, SOURCE_MANIFEST)
        with pytest.raises(M5ImportConflict, match="M5_PACKAGE_VERSION_CONTENT_CONFLICT"):
            import_package(connection, package={**package["package_json"], "variant": "different"},
                           manifest=package["manifest_json"], execution_rules=package["runtime_rules_json"])
        with pytest.raises(ValueError, match="M5_DIAGNOSTIC_CATALOG_REQUIRES_SCOPED_QA"):
            publication_plan(connection, package_db_id=package["id"], case_version_ids=[row["id"] for row in cases],
                             usage_scope="assessment", organization_id=10, runtime_rule_version_id=rules_id)

        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT")
        connection.execute("""INSERT INTO assessment_configurations
            (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (2,1,'published','bank-01-qa','Synthetic BANK-01 QA',%s)""", (catalog,))
        context = connection.execute("""SELECT organization_context_version_id,user_context_version_id
            FROM assessment_personalized_profiles WHERE id=%s""", (product_db.profile_id,)).fetchone()
        role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND r.scope='base' AND v.status='published'""").fetchone()["id"]
        qa_profile = create_personalized_profile(
            connection, user_id=99, assessment_configuration_id=2, role_profile_version_id=role, **context,
        )["id"]
        with pytest.raises(ValueError, match="M5_CATALOG_USAGE_SCOPE_MISMATCH"):
            resolve_configuration_catalog(connection, configuration_id=2, usage_scope="assessment")

        indicators, skills = set(), set()
        target_count = 0
        for row, entry in zip(cases, manifest["cases"], strict=True):
            case_id, version = entry["case_id"], entry["version"]
            assert (row["case_id"], row["case_version"], row["base_role"], row["status"]) == (
                case_id, version, "specialist_expert", "WORKING",
            )
            assert not case_admission(connection, case_version_id=row["id"], usage_scope="qa")["admitted"]
            case = connection.execute("SELECT content_json FROM m5_case_versions WHERE id=%s", (row["id"],)).fetchone()["content_json"]
            raw = (BATTERY_PACKAGE / "sources" / entry["file_refs"]["json"]["path"]).read_bytes()
            original = json.loads(raw)
            assert case["passport"] == original["Паспорт"]
            assert case["passport_source"]["sha256"] == digest(raw) == entry["file_refs"]["json"]["sha256"]
            assert (case["planned_min_minutes"], case["planned_max_minutes"]) == (entry["time_min"], entry["time_max"])
            assert case["case_type_ids"] == entry["ct_ids"]
            assert case["format"] == entry["format"]
            scen = original["Паспорт"]["17 Сценарий Dialogue"]
            materials = connection.execute("""SELECT material_id,content_json FROM m5_case_materials
                WHERE case_version_id=%s ORDER BY display_order""", (row["id"],)).fetchall()
            assert [item["material_id"] for item in materials if item["content_json"]["participant_visible_initially"]] == (
                scen["17.1 Старт"]["Последовательность предъявления"]
            )
            steps = connection.execute("""SELECT content_json FROM m5_case_scenario_steps
                WHERE case_version_id=%s ORDER BY display_order""", (row["id"],)).fetchall()
            assert steps and [item["content_json"] for item in steps] == case["scenario"]
            for item in case["materials"] + case["scenario"]:
                assert item["content"] == pointer(original, item["source"]["pointer"])
            if case["format"] == "Письменный":
                finish = case["passport_sources"]["17.4/E02_SUBMISSION"]
                assert pointer(original, finish["pointer"]) == scen["17.4 Завершение"]
            rules, ref = resolve_runtime_rules(connection, case_version_id=row["id"], case_id=case_id,
                                               legacy_rules={}, catalog_db_id=catalog)
            assert ref["version"] == "1.5.0"
            assert rules["case_bindings"][case_id]["case_checksum"] == row["content_checksum"] == checksum(case)
            targets = connection.execute("""SELECT target_json FROM m5_case_targets
                WHERE case_version_id=%s ORDER BY display_order""", (row["id"],)).fetchall()
            targets = [record["target_json"] for record in targets]
            assert [target["indicator_id"] for target in targets] == entry["indicator_ids"]
            for target in targets:
                indicator = target["indicator_id"]
                indicators.add(indicator)
                skills.add(target["skill_id"])
                norm = m2[indicator]
                assert (target["m2_version"], target["skill_id"], target["component_id"], target["normative_source"]) == (
                    norm["m2_version"], norm["skill_id"], norm["component_id"], norm["source"],
                )
                original_target = pointer(original, target["source"]["pointer"])
                assert target["scenario_locations"] == original_target["Место в сценарии"]
                assert target["event_condition"] == original_target["Условие возникновения"]
                assert target["observable_action"] == original_target["Доступная форма проявления"]
                assert target["validity_risk"] == original_target["Риск потери"]
            target_count += len(targets)

            cycle, session = create_cycle_session_for_case(
                connection, personalized_profile_id=qa_profile, case_id=case_id, case_version=version,
                created_by=99, usage_scope="qa", diagnostic=True,
            )
            frozen = read_cycle(connection, str(cycle["cycle_id"]))
            assert frozen["catalog_ref_json"]["selected_case"]["content_checksum"] == row["content_checksum"]
            assert frozen["execution_manifest_json"]["runtime_refs"]["catalog_ref"] == frozen["catalog_ref_json"]
            assert resolve_cycle_dependency(frozen, "m5_functional_package") == BATTERY_PACKAGE
            assert resolve_cycle_dependency(frozen, "m5_functional_runtime") == BATTERY_RUNTIME
            assert resolve_cycle_dependency(frozen, "m5_functional_as").name == "v3"
            with pytest.raises(ValueError, match="M5_BATTERY_PREPARATION_NOT_ENABLED"):
                start_session(connection, session_id=str(session["session_id"]))
            with pytest.raises(ValueError, match="M5_BATTERY_PREPARATION_NOT_ENABLED"):
                prepare_assessment_situation(
                    connection, assessment_situation_id=str(uuid4()), case_id=case_id, case_version=version,
                    personalized_profile_id=qa_profile, cycle_db_id=cycle["id"], session_db_id=session["id"],
                    substitutions=[], policy={}, usage_scope="qa", qa_authorized_by=99,
                )

        assert (target_count, len(indicators), len(skills)) == (55, 39, 14)
        assert connection.execute("SELECT count(*) AS n FROM m5_assessment_situations").fetchone()["n"] == 0


@pytest.mark.integration
def test_existing_cycle_resumes_and_prepares_next_after_battery_install(product_db, monkeypatch, tmp_path):
    from tests.integration.test_m10_product_path_db import (
        test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases as product_path,
    )

    frozen = {}

    def install_after_first_as(connection, cycle_id, first_as):
        frozen["cycle"] = read_cycle(connection, cycle_id)
        frozen["first_as"] = first_as
        frozen["snapshot"] = connection.execute(
            "SELECT snapshot_json,execution_payload_json FROM m5_assessment_situations WHERE assessment_situation_id=%s",
            (first_as,),
        ).fetchone()
        install_battery(connection)

    product_path(product_db, monkeypatch, tmp_path, True, False, None, None,
                 passport_bank=True, after_first_prepared=install_after_first_as)
    with product_db() as connection:
        cycle = read_cycle(connection, str(frozen["cycle"]["cycle_id"]))
        assert cycle["execution_manifest_checksum"] == frozen["cycle"]["execution_manifest_checksum"]
        assert cycle["execution_manifest_json"] == frozen["cycle"]["execution_manifest_json"]
        assert cycle["catalog_ref_json"] == frozen["cycle"]["catalog_ref_json"]
        assert resolve_cycle_dependency(cycle, "m5_functional_as").name == "v3"
        cases = connection.execute("""SELECT situation.assessment_situation_id,
                situation.snapshot_json,situation.execution_payload_json,package.package_version
            FROM m5_assessment_situations situation
            JOIN m5_case_versions cv ON cv.id=situation.case_version_id
            JOIN m5_packages package ON package.id=cv.package_id
            WHERE situation.cycle_db_id=%s ORDER BY situation.id""", (cycle["id"],)).fetchall()
        assert len(cases) == 2
        assert str(cases[0]["assessment_situation_id"]) == frozen["first_as"]
        assert {key: cases[0][key] for key in frozen["snapshot"]} == frozen["snapshot"]
        assert cases[0]["package_version"].startswith("0.6")
        assert cases[1]["package_version"] == cases[0]["package_version"]

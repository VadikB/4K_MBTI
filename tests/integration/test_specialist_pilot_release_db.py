import json
import shutil
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from Api import assessment_contexts, assessment_programs, database, pilot_plan_binding
from Api.assessment_methodology_publication import publish_m2_qa_configuration
from Api.assessment_role_profiles import publish_base_roles
from Api.m5_catalog_integrity import case_admission, publish_catalog, resolve_configuration_catalog, resolve_profile_base_role
from Api.m5_cycle_runtime import create_cycle, create_session, read_cycle, start_session
from Api.m5_storage import import_package
from Api.m7_planning_package import methodology_targets
from Api.org_access import LOCAL_SUPERADMIN_EMAIL
from Api.schema_bootstrap import bootstrap_base
from scripts.plan_specialist_program_release import PACKAGE_DIR, build_admitted_materials
from scripts.release_specialist_pilot import RELEASE_DIR, ROOT, load_release, release, release_configuration


@pytest.fixture
def release_db(test_database_url, monkeypatch):
    name = "specialist_release_pytest_" + uuid4().hex
    admin = psycopg.connect(test_database_url, autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(test_database_url, dbname=name)

    @contextmanager
    def connect():
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            yield connection

    try:
        monkeypatch.setattr(database, "get_connection", connect)
        with connect() as connection:
            bootstrap_base(connection)
        database.ensure_core_schema()
        yield connect
    finally:
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        admin.close()


def seed_baseline(connection):
    publisher = connection.execute("INSERT INTO users(email) VALUES(%s) RETURNING id",
                                   (LOCAL_SUPERADMIN_EMAIL,)).fetchone()["id"]
    participant = connection.execute("INSERT INTO users(email) VALUES('participant@example.test') RETURNING id").fetchone()["id"]
    reason = "Isolated publication regression fixture"
    m2 = publish_m2_qa_configuration(connection, published_by_user_id=publisher, decision_basis=reason)
    role_package = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1"
    publish_base_roles(connection, package=json.loads((role_package / "base_roles.json").read_bytes()),
                       manifest=json.loads((role_package / "manifest.json").read_bytes()),
                       published_by_user_id=publisher, decision_basis=reason)
    role_id = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
        JOIN assessment_role_profiles p ON p.id=v.role_profile_id WHERE p.code='specialist_expert'""").fetchone()["id"]
    package, _, _ = build_admitted_materials(reason)
    bank = import_package(connection, package=package, manifest=json.loads((PACKAGE_DIR / "manifest.json").read_bytes()))
    catalog = publish_catalog(connection, catalog_id="specialist-pilot", catalog_version="1.0",
                              package_db_id=bank["package_db_id"], case_version_ids=[], usage_scope="assessment",
                              published_by=publisher, decision_basis=reason, idempotency_key="fixture-catalog")
    config = release_configuration(connection, code="specialist_pilot_v1", baseline={**m2, "name": "Baseline"},
                                   catalog_id=catalog["catalog_db_id"], publisher=publisher, reason=reason)
    manifest, _ = load_release(RELEASE_DIR)
    program = assessment_programs.publish_definition(
        connection, program={**manifest["program"], "version": "1.2",
                             "assessment_configuration_id": config["id"], "catalog_version_id": catalog["catalog_db_id"],
                             "source_refs_json": {key: config[key] for key in (
                                 "methodology_version_id", "scenario_version_id", "prompt_bundle_checksum")}},
        role_ids=[role_id], publisher_user_id=publisher,
    )
    org = connection.execute("INSERT INTO organizations(code,name) VALUES('fixture','Fixture') RETURNING id").fetchone()["id"]
    connection.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,admission_source)
        VALUES(%s,%s,'member','admin_add')""", (org, participant))
    context = assessment_contexts.create_organization_context_draft(connection, organization_id=org, definition={
        "name": "Fixture", "organization_type": "компания", "industry": "образование",
        "activity_description": "Техническая проверка", "case_reality_level": "обобщённый",
        "organization_name_usage_rules": "Не указывать название",
    })
    assessment_contexts.publish_organization_context(connection, version_id=context, confirmed_by_user_id=publisher)
    user_context = assessment_contexts.create_user_context_draft(
        connection, user_id=participant, identity={"full_name": "Fixture"},
        professional={"regular_tasks": ["Проверять технические примеры"]},
    )
    assessment_contexts.confirm_user_context(connection, version_id=user_context, user_id=participant)
    profile = assessment_contexts.create_personalized_profile(
        connection, user_id=participant, assessment_configuration_id=config["id"],
        organization_context_version_id=context, user_context_version_id=user_context, role_profile_version_id=role_id,
    )
    catalog_ref = resolve_configuration_catalog(connection, configuration_id=config["id"], usage_scope="assessment")
    cycle = create_cycle(connection, personalized_profile_id=profile["id"], created_by=participant,
                         selected_role_ref=resolve_profile_base_role(connection, role_profile_version_id=role_id),
                         target_set=methodology_targets(["K1", "K2", "K3", "K4"]), catalog_ref=catalog_ref,
                         time_budget_seconds=7200, calendar_window_seconds=259200, parameter_sources={})
    cycle_id = str(cycle["cycle_id"])
    session = create_session(connection, cycle_id=cycle_id, created_by=participant)
    start_session(connection, session_id=str(session["session_id"]))
    return publisher, participant, org, program, cycle_id


@pytest.mark.integration
def test_authorized_release_without_human_forms_is_idempotent_and_preserves_started_cycle(release_db, tmp_path):
    with release_db() as connection:
        publisher, participant, org, baseline, cycle_id = seed_baseline(connection)
        previous_cycle = read_cycle(connection, cycle_id)

    bad = tmp_path / "altered"
    shutil.copytree(RELEASE_DIR, bad)
    proposal_file = bad / "m7-proposal.json"
    proposal_file.write_bytes(proposal_file.read_bytes() + b" ")
    with release_db() as connection:
        with pytest.raises(ValueError, match="PILOT_PLAN_RELEASE_SOURCE_CHECKSUM_MISMATCH"):
            release(connection, directory=bad, publisher=publisher, principal="fixture-deployer")
        with pytest.raises(PermissionError, match="configuration.publish"):
            release(connection, directory=RELEASE_DIR, publisher=participant, principal="fixture-deployer")
        assert [row["version"] for row in assessment_programs.list_published(connection)] == ["1.2"]
        first = release(connection, directory=RELEASE_DIR, publisher=publisher, principal="fixture-deployer")
        assert first["result"] == "published"
        assert first["catalog_version"] == "1.4.4"
        assert connection.execute("SELECT count(*) AS n FROM m5_qa_evidence").fetchone()["n"] == 0
        assert read_cycle(connection, cycle_id) == previous_cycle
        assert connection.execute("SELECT count(*) AS n FROM organization_assessment_program_connections").fetchone()["n"] == 0
        program = connection.execute("SELECT * FROM assessment_program_definitions WHERE id=%s",
                                     (first["program_id"],)).fetchone()
        plan = pilot_plan_binding.validate_published_program(connection, program)
        assert plan.get("owner_decision") is None
        assert plan["publisher_release"]["publisher_user_id"] == publisher
        members = connection.execute("SELECT case_version_id FROM m5_catalog_case_versions WHERE catalog_db_id=%s",
                                     (first["catalog_db_id"],)).fetchall()
        assert len(members) == 9
        for member in members:
            assert case_admission(connection, **member, usage_scope="assessment",
                                  catalog_db_id=first["catalog_db_id"])["admitted"]
        assessment_programs.connect(connection, organization_id=org, program_definition_id=first["program_id"],
                                    actor_user_id=publisher, operation_id="isolated-connect")
        assert read_cycle(connection, cycle_id) == previous_cycle
    with release_db() as connection:
        repeat = release(connection, directory=RELEASE_DIR, publisher=publisher, principal="fixture-deployer")
        assert repeat == {**first, "result": "existing"}
        rows = assessment_programs.list_published(connection)
        assert [(row["id"], row["version"]) for row in rows] == [(baseline["id"], "1.2"), (first["program_id"], "2.0")]
        assert read_cycle(connection, cycle_id) == previous_cycle

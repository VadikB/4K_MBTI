import json
import shutil
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from Api import assessment_contexts, assessment_programs, cycle_execution_manifest, database, m5_cycle_runtime, pilot_plan_binding
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
from tests.unit.test_m5_review_clarification import CLARITY, ClarifyingGateway


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


@pytest.fixture
def pin_original_evidence_mechanism(monkeypatch):
    """The operator recovery targets a Cycle created on TEST 2.1.85."""
    dependencies = {**cycle_execution_manifest.DEFAULT_DEPENDENCIES,
                    "m6_evidence": "assessment_definitions/prompts/m6_evidence/v1.0.1"}

    def build_frozen_manifest(**kwargs):
        return cycle_execution_manifest.build_manifest(**kwargs, dependencies=dependencies)

    monkeypatch.setattr(m5_cycle_runtime, "build_manifest", build_frozen_manifest)


@pytest.fixture
def opened_specialist_pilot(release_db, monkeypatch, request):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from Api import auth_service, product_cycle_preparation_queue as preparation, routes
    from Api import web_session_service as sessions
    from Api.llm import deepseek_gateway
    from Api.preparation_observation import read as observation_read
    from tests.integration.test_m5_battery_v04_db import V04Gateway

    with release_db() as connection:
        publisher, _, org, _, _ = seed_baseline(connection)
        # Use a fresh participant so that no pre-existing Cycle can satisfy the test.
        participant = connection.execute(
            "INSERT INTO users(email, full_name) VALUES('v7-start@example.test', 'Синтетический участник') RETURNING id"
        ).fetchone()["id"]
        connection.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,admission_source)
            VALUES(%s,%s,'member','admin_add')""", (org, participant))
        administrator_id = connection.execute(
            "INSERT INTO users(email) VALUES('v7-org-admin@example.test') RETURNING id"
        ).fetchone()["id"]
        connection.execute("""INSERT INTO organization_memberships
            (organization_id,user_id,role,admission_source,is_participant)
            VALUES(%s,%s,'admin','admin_add',FALSE)""", (org, administrator_id))
        published = release(connection, directory=RELEASE_DIR, publisher=publisher, principal="fixture-deployer")
        assessment_programs.connect(connection, organization_id=org, program_definition_id=published["program_id"],
                                    actor_user_id=publisher, operation_id="v7-start-connect")

    monkeypatch.setattr(routes, "get_connection", release_db)
    monkeypatch.setattr(preparation, "get_connection", release_db)
    monkeypatch.setattr(sessions, "get_connection", release_db)
    monkeypatch.setattr(auth_service, "get_connection", release_db)
    auth_service.auth_service.ensure_schema()
    gateway = getattr(request, "param", V04Gateway)()
    monkeypatch.setattr(deepseek_gateway, "DeepSeekGateway", lambda **_: gateway)
    sessions.web_session_service.ensure_schema()
    app = FastAPI()
    app.include_router(routes.router)

    with TestClient(app) as administrator, TestClient(app) as client:
        administrator.cookies.set(routes.SESSION_COOKIE_NAME, sessions.web_session_service.create_session(administrator_id))
        client.cookies.set(routes.SESSION_COOKIE_NAME, sessions.web_session_service.create_session(participant))
        admin_path = f"/users/admin/organizations/{org}"
        form = administrator.post(admin_path + "/questionnaire/preview", json={
            "assignment_ref": "specialist-pilot", "source_author": "Синтетическая организация",
            "idempotency_key": "v7-start-questionnaire", "channel": "csv",
            "csv_text": (ROOT / "assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv").read_text(),
        })
        assert form.status_code == 201, form.text
        confirmed = administrator.post(admin_path + f"/questionnaire/{form.json()['id']}/confirm",
                                       json={"recipients": ["participant"]})
        assert confirmed.status_code == 200, confirmed.text
        assigned = administrator.post(admin_path + "/assessment-assignments", json={
            "user_ids": [participant], "assignment_ref": "specialist-pilot", "operation_id": "v7-start-assignment",
        })
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["items"][0]["status"] == "assigned", assigned.text
        assignment_id = assigned.json()["items"][0]["assignment_id"]

        acquaintance = f"/users/{participant}/acquaintance"
        initial = client.get(acquaintance).json()
        assert initial["readiness"]["status"] == "ready", initial["readiness"]
        assert initial["prepared_plan"] is None
        consent = client.post(acquaintance + "/consent", json={
            "version": initial["readiness"]["briefing"]["consent_version"],
        })
        assert consent.status_code == 200, consent.text
        answers = client.put(acquaintance + "/answers", json={"confirm": True, "answers": {
            "answer_1": "Сверяю рабочие предложения с требованиями и обсуждаю решения с коллегами.",
            "answer_2": "Готовлю рекомендации, решение согласовывает руководитель.",
            "answer_3": "Использую карточки задач и материалы проверок.",
        }})
        assert answers.status_code == 200, answers.text
        resolved = client.post(acquaintance + "/resolve-profile")
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["late_readiness"]["status"] == "ready_to_prepare"

        operation_id = "v7-start-preparation"
        queued = client.post("/users/assessment/cycles/prepare", json={
            "idempotency_key": operation_id, "selected_skills": ["K1", "K2", "K3", "K4"],
        })
        assert queued.status_code == 202, queued.text
        worker = preparation.product_cycle_preparation_queue
        job = worker._claim()
        assert job["operation_id"] == operation_id
        worker._process(job)
        operation = client.get(f"/users/assessment/cycles/preparation/{operation_id}")
        assert operation.status_code == 200, operation.text
        assert operation.json()["status"] == "completed", operation.text
        roles = {call[0].split(":")[1] for call in gateway.calls}
        assert roles == {"generation", "tester", "challenger"}

        state = client.get(acquaintance).json()
        plan = state["prepared_plan"]
        readiness = plan["start_readiness"]
        cycle_id = plan["cycle_id"]
        assert state["assignment_id"] == assignment_id
        assert readiness["can_start"] is True and readiness["reasons"] == [], readiness
        assert readiness["plan_revision_id"] == plan["revision_id"]
        assert readiness["cycle_id"] == cycle_id
        assert readiness["pilot_admission"]["program_ref"]["version"] == "2.0"
        with release_db() as connection:
            before = read_cycle(connection, cycle_id)
            assert before["started_at"] is None and before["consumed_seconds"] == 0
            assert before["catalog_ref_json"]["version"] == "1.4.4"
            assert observation_read(connection, "cycle", operation_id)["status"] == "completed"

        request = {"cycle_id": cycle_id, "idempotency_key": "v7-start-click"}
        opened = client.post("/users/assessment/cycles/start", json=request)
        assert opened.status_code == 201, opened.text
        runtime = opened.json()["runtime"]
        first = runtime["current_situation"]
        assert first["assessment_situation_id"] == readiness["assessment_situation_id"]
        assert first["status"] == "active" and first["participant_payload"]
        assert runtime["trace"]
        with release_db() as connection:
            started_at = read_cycle(connection, cycle_id)["started_at"]
            assert started_at is not None
        yield SimpleNamespace(
            client=client, worker=worker, assignment_id=assignment_id, cycle_id=cycle_id, cycle_db_id=before["id"],
            first=first, started_at=started_at, participant_id=participant, start_request=request, gateway=gateway,
        )


@pytest.mark.integration
def test_synthetic_assignment_opens_the_prepared_v7_card_and_keeps_start_time(release_db, opened_specialist_pilot):
    pilot = opened_specialist_pilot
    assert pilot.client.post("/users/assessment/cycles/start", json=pilot.start_request).status_code == 201
    returned = pilot.client.get(f"/users/assessment/cycles/{pilot.cycle_id}/runtime")
    assert returned.status_code == 200, returned.text
    assert returned.json()["current_situation"] == pilot.first
    with release_db() as connection:
        assert read_cycle(connection, pilot.cycle_id)["started_at"] == pilot.started_at
        assert connection.execute("""SELECT count(*) AS n FROM m5_cycles WHERE assignment_id=%s""",
                                  (pilot.assignment_id,)).fetchone()["n"] == 1
        assert connection.execute("""SELECT count(*) AS n FROM m5_cycle_time_intervals
            WHERE cycle_db_id=%s AND interval_type='collecting'""", (pilot.cycle_db_id,)).fetchone()["n"] == 1
    assert {call[0].split(":")[1] for call in pilot.gateway.calls} == {"generation", "tester", "challenger"}


@pytest.mark.integration
@pytest.mark.parametrize("opened_specialist_pilot", [ClarifyingGateway], indirect=True)
def test_first_and_next_on_published_program_replay_targeted_clarification(release_db, opened_specialist_pilot):
    from Api import assessment_start_readiness
    from tests.integration.test_m5_battery_scenario_db import submit
    from tests.integration.test_m10_product_path_db import _resolve_interim_for_finish

    pilot = opened_specialist_pilot
    as_id = pilot.first["assessment_situation_id"]
    runtime_path = f"/users/assessment/cycles/{pilot.cycle_id}/runtime"
    next_path = f"/users/assessment/m7/cycles/{pilot.cycle_id}"

    def verify_saved(situation_id, operation_id, expected_case):
        with release_db() as connection:
            cycle = read_cycle(connection, pilot.cycle_id)
            assert cycle_execution_manifest.resolve_review_response(cycle) == (
                ROOT / cycle_execution_manifest.M5_REVIEW_RESPONSE_PACKAGE
            )
            saved = connection.execute(
                """SELECT execution_payload_json #>'{ai_operations,functional_personalization}' AS trace
                   FROM m5_assessment_situations WHERE assessment_situation_id=%s AND cycle_db_id=%s""",
                (situation_id, pilot.cycle_db_id),
            ).fetchone()["trace"]
        assert saved["source_snapshot"]["case_version"]["case_id"] == expected_case
        assert saved["source_snapshot"]["refs"]["protocol_package"]["version"] == "7.0.0"
        assert saved["source_snapshot"]["refs"]["review_response"]["version"] == "1.0.0"
        batch = saved["tester"]["provider_operation"]["batches"][0]
        assert batch["clarification"]["accepted_check_ids"] == [CLARITY]
        assert saved["repair"] is None
        for _ in range(2):
            assessment_start_readiness.functional_gate(
                saved, operation_id=operation_id, cycle=cycle, case_version=saved["source_snapshot"]["case_version"],
            )

    verify_saved(as_id, "v7-start-preparation", "CASE.SPEC.02")
    submit(release_db, as_id, "Сопоставляю подтверждённые сроки и сообщаю предел проверки.", {}, control="FINAL")
    with release_db() as connection:
        _resolve_interim_for_finish(connection, release_db, as_id, user_id=pilot.participant_id)
    closed = pilot.client.post(next_path + "/finish-situation", json={"idempotency_key": "task10-finish-first"})
    assert closed.status_code == 200, closed.text
    next_id = "next:" + as_id
    queued = pilot.client.post(next_path + "/next", json={"idempotency_key": next_id, "after_assessment_situation_id": as_id})
    assert queued.status_code == 201, queued.text
    job = pilot.worker._claim()
    assert job["operation_id"] == next_id
    pilot.worker._process(job)
    operation = pilot.client.get(f"/users/assessment/cycles/preparation/{next_id}")
    assert operation.json()["status"] == "completed", operation.text
    ready = pilot.client.get(runtime_path).json()["next_presentation"]
    next_as = ready["assessment_situation_id"]
    assert next_as != as_id
    verify_saved(next_as, next_id, "CASE.SPEC.03")
    presented = pilot.client.post(next_path + "/present-next", json=ready)
    assert presented.status_code == 201, presented.text
    assert presented.json()["runtime"]["current_situation"]["assessment_situation_id"] == next_as

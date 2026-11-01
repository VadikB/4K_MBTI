"""ADM-LAYOUT-31/P06: cancellation generations and cancel/start serialization."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from Api import assessment_assignment_cancellation as cancellation
from Api import assessment_assignment_sources


pytestmark = pytest.mark.integration


def _schema(connection, name: str) -> None:
    connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(name)))


def _setup(connection, name: str) -> None:
    connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
    _schema(connection, name)
    connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
    connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
    connection.execute("INSERT INTO users VALUES(1),(2); INSERT INTO organizations VALUES(10)")
    connection.execute("""CREATE TABLE organization_assessment_assignments(
        id BIGSERIAL PRIMARY KEY,organization_id BIGINT NOT NULL REFERENCES organizations(id),
        recipient_user_id BIGINT NOT NULL REFERENCES users(id),assignment_ref TEXT NOT NULL,
        created_by_user_id BIGINT REFERENCES users(id),questionnaire_revision_id BIGINT,
        status TEXT NOT NULL,operation_id TEXT NOT NULL,request_fingerprint TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),revoked_at TIMESTAMP,generation_no INTEGER NOT NULL DEFAULT 1)""")
    connection.execute("""CREATE UNIQUE INDEX uq_active_assignment
        ON organization_assessment_assignments(organization_id,recipient_user_id,assignment_ref)
        WHERE status='active' AND revoked_at IS NULL""")
    connection.execute("CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY)")
    connection.execute("""CREATE TABLE m5_cycles(
        id BIGSERIAL PRIMARY KEY,owner_user_id BIGINT NOT NULL,organization_id BIGINT,
        assignment_id BIGINT REFERENCES organization_assessment_assignments(id),
        personalized_profile_id BIGINT,
        usage_scope TEXT NOT NULL DEFAULT 'assessment',status TEXT NOT NULL,started_at TIMESTAMPTZ)""")
    connection.execute("""CREATE TABLE organization_assessment_source_bindings(
        id BIGSERIAL PRIMARY KEY,assignment_id BIGINT NOT NULL REFERENCES organization_assessment_assignments(id),
        questionnaire_revision_id BIGINT NOT NULL,assessment_configuration_id BIGINT NOT NULL,
        role_profile_version_id BIGINT NOT NULL,assigned_by_user_id BIGINT NOT NULL,
        operation_id TEXT NOT NULL,created_at TIMESTAMP NOT NULL DEFAULT NOW(),UNIQUE(assignment_id,operation_id))""")
    connection.execute("""CREATE TABLE participant_acquaintance_confirmations(
        id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL,organization_id BIGINT NOT NULL,
        assignment_ref TEXT NOT NULL,questionnaire_revision_id BIGINT,
        personalized_profile_id BIGINT)""")
    cancellation.ensure_schema(connection)
    connection.commit()


def _assignment(connection, ref: str, generation: int = 1) -> int:
    return int(connection.execute("""INSERT INTO organization_assessment_assignments
        (organization_id,recipient_user_id,assignment_ref,created_by_user_id,status,operation_id,
         request_fingerprint,generation_no) VALUES(10,2,%s,1,'active',%s,'fixture',%s) RETURNING id""",
        (ref, f"assign-{ref}-{generation}", generation)).fetchone()["id"])


def test_cancel_is_idempotent_and_new_assignment_is_new_generation(test_database_url):
    schema = "adm31_cancel_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        first_id = _assignment(connection, "assessment-a")
        first = cancellation.cancel(connection, organization_id=10, assignment_id=first_id,
                                    actor_user_id=1, operation_id="cancel-operation-01")
        replay = cancellation.cancel(connection, organization_id=10, assignment_id=first_id,
                                     actor_user_id=1, operation_id="cancel-operation-01")
        replay_with_new_key = cancellation.cancel(connection, organization_id=10, assignment_id=first_id,
                                                  actor_user_id=1, operation_id="cancel-operation-02")
        second_id = _assignment(connection, "assessment-a", 2)
        assert first["status"] == replay["status"] == replay_with_new_key["status"] == "revoked"
        assert second_id != first_id
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (first_id,)).fetchone()["status"] == "revoked"
        assert connection.execute("SELECT COUNT(*) AS value FROM organization_assessment_assignment_audit").fetchone()["value"] == 1
        connection.rollback()


def test_reassignment_clones_immutable_sources_into_new_generation(test_database_url):
    schema = "adm31_rebind_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        first_id = _assignment(connection, "assessment-a")
        connection.execute("""INSERT INTO organization_assessment_source_bindings
            (assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,
             assigned_by_user_id,operation_id) VALUES(%s,71,81,91,1,'bind-first')""", (first_id,))
        connection.execute("""INSERT INTO participant_acquaintance_confirmations
            (user_id,organization_id,assignment_ref,questionnaire_revision_id,personalized_profile_id)
            VALUES(2,10,'assessment-a',71,501)""")
        cancellation.cancel(connection, organization_id=10, assignment_id=first_id,
                            actor_user_id=1, operation_id="cancel-before-rebind")
        second_id = _assignment(connection, "assessment-a", 2)
        rebound = assessment_assignment_sources.bind(
            connection, assignment_id=second_id, organization_id=10,
            configuration_id=81, role_version_id=91, questionnaire_revision_id=71,
            actor_user_id=1, operation_id="bind-second",
        )
        assert rebound["assignment_id"] == second_id
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (first_id,)).fetchone()["status"] == "revoked"
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (second_id,)).fetchone()["status"] == "active"
        connection.rollback()


def test_cancel_rejects_started_cycle_and_unknown_legacy_link(test_database_url):
    schema = "adm31_started_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        started_id = _assignment(connection, "started")
        connection.execute("INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,status,started_at) VALUES(2,10,%s,'active',NOW())", (started_id,))
        with pytest.raises(cancellation.CancellationError, match="ASSIGNMENT_ALREADY_STARTED"):
            cancellation.cancel(connection, organization_id=10, assignment_id=started_id,
                                actor_user_id=1, operation_id="cancel-started-01")
        connection.rollback()
        _schema(connection, schema)
        legacy_id = _assignment(connection, "legacy")
        connection.execute("INSERT INTO assessment_personalized_profiles VALUES(501)")
        connection.execute("""INSERT INTO organization_assessment_source_bindings
            (assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,
             assigned_by_user_id,operation_id) VALUES(%s,71,81,91,1,'bind-legacy')""", (legacy_id,))
        connection.execute("""INSERT INTO participant_acquaintance_confirmations
            (user_id,organization_id,assignment_ref,questionnaire_revision_id,personalized_profile_id)
            VALUES(2,10,'legacy',71,501)""")
        connection.execute("""INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,personalized_profile_id,status)
            VALUES(2,10,NULL,501,'prepared')""")
        with pytest.raises(cancellation.CancellationError, match="ASSIGNMENT_LINK_UNKNOWN"):
            cancellation.cancel(connection, organization_id=10, assignment_id=legacy_id,
                                actor_user_id=1, operation_id="cancel-legacy-01")
        connection.rollback()


@pytest.mark.parametrize("status", ["active", "paused", "interrupted", "collection_closed", "calculated", "failed"])
def test_cancel_rejects_every_started_cycle_state(test_database_url, status):
    schema = "adm31_state_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        assignment_id = _assignment(connection, "started-" + status)
        connection.execute("INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,status,started_at) VALUES(2,10,%s,%s,NOW())",
                           (assignment_id, status))
        with pytest.raises(cancellation.CancellationError, match="ASSIGNMENT_ALREADY_STARTED"):
            cancellation.cancel(connection, organization_id=10, assignment_id=assignment_id,
                                actor_user_id=1, operation_id="cancel-state-" + status)
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (assignment_id,)).fetchone()["status"] == "active"
        connection.rollback()


def test_operation_key_cannot_be_reused_for_another_assignment(test_database_url):
    schema = "adm31_key_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        first_id = _assignment(connection, "first")
        second_id = _assignment(connection, "second")
        cancellation.cancel(connection, organization_id=10, assignment_id=first_id,
                            actor_user_id=1, operation_id="same-operation-key")
        with pytest.raises(cancellation.CancellationError, match="ASSIGNMENT_CANCEL_IDEMPOTENCY_CONFLICT"):
            cancellation.cancel(connection, organization_id=10, assignment_id=second_id,
                                actor_user_id=1, operation_id="same-operation-key")
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (second_id,)).fetchone()["status"] == "active"
        connection.rollback()


def test_unrelated_legacy_cycle_does_not_block_exact_assignment(test_database_url):
    schema = "adm31_unrelated_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        unrelated_id = _assignment(connection, "historical-other")
        target_id = _assignment(connection, "target")
        connection.execute("INSERT INTO assessment_personalized_profiles VALUES(501)")
        connection.execute("""INSERT INTO organization_assessment_source_bindings
            (assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,
             assigned_by_user_id,operation_id) VALUES(%s,72,81,91,1,'bind-other')""", (unrelated_id,))
        connection.execute("""INSERT INTO participant_acquaintance_confirmations
            (user_id,organization_id,assignment_ref,questionnaire_revision_id,personalized_profile_id)
            VALUES(2,10,'historical-other',72,501)""")
        connection.execute("""INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,personalized_profile_id,status)
            VALUES(2,10,NULL,501,'prepared')""")
        result = cancellation.cancel(connection, organization_id=10, assignment_id=target_id,
                                     actor_user_id=1, operation_id="cancel-unrelated-01")
        assert result["status"] == "revoked"
        assert connection.execute("SELECT status FROM organization_assessment_assignments WHERE id=%s", (unrelated_id,)).fetchone()["status"] == "active"
        connection.rollback()


def test_audit_failure_rolls_back_assignment_change(test_database_url):
    schema = "adm31_rollback_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _setup(connection, schema)
        assignment_id = _assignment(connection, "rollback")
        connection.commit()
        connection.execute("""CREATE FUNCTION reject_cancel_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$""")
        connection.execute("""CREATE TRIGGER reject_cancel_audit BEFORE INSERT ON organization_assessment_assignment_audit
            FOR EACH ROW EXECUTE FUNCTION reject_cancel_audit()""")
        connection.commit()
        with pytest.raises(psycopg.DatabaseError, match="synthetic audit failure"):
            cancellation.cancel(connection, organization_id=10, assignment_id=assignment_id,
                                actor_user_id=1, operation_id="cancel-rollback-01")
        connection.rollback()
        _schema(connection, schema)
        row = connection.execute("SELECT status,revoked_at FROM organization_assessment_assignments WHERE id=%s", (assignment_id,)).fetchone()
        assert row == {"status": "active", "revoked_at": None}
        assert connection.execute("SELECT COUNT(*) AS value FROM organization_assessment_cancellation_operations").fetchone()["value"] == 0


def test_parallel_cancels_produce_one_transition_and_safe_replay(test_database_url):
    schema = "adm31_parallel_cancel_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as setup:
        _setup(setup, schema)
        assignment_id = _assignment(setup, "parallel-cancel")
        setup.commit()

    def run_cancel(operation_id: str) -> str:
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            _schema(connection, schema)
            result = cancellation.cancel(connection, organization_id=10, assignment_id=assignment_id,
                                         actor_user_id=1, operation_id=operation_id)
            connection.commit()
            return result["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run_cancel, ["parallel-cancel-01", "parallel-cancel-02"]))
    assert outcomes == ["revoked", "revoked"]
    with psycopg.connect(test_database_url, row_factory=dict_row) as verify:
        _schema(verify, schema)
        assert verify.execute("SELECT COUNT(*) AS value FROM organization_assessment_assignment_audit").fetchone()["value"] == 1
        assert verify.execute("SELECT COUNT(*) AS value FROM organization_assessment_cancellation_operations").fetchone()["value"] == 2


def test_parallel_new_assignments_keep_one_active_generation(test_database_url):
    schema = "adm31_parallel_assign_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as setup:
        _setup(setup, schema)

    def assign(operation_id: str) -> int | None:
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            _schema(connection, schema)
            row = connection.execute("""INSERT INTO organization_assessment_assignments
                (organization_id,recipient_user_id,assignment_ref,created_by_user_id,status,operation_id,request_fingerprint)
                VALUES(10,2,'parallel-assignment',1,'active',%s,'fixture')
                ON CONFLICT (organization_id,recipient_user_id,assignment_ref)
                WHERE status='active' AND revoked_at IS NULL DO NOTHING RETURNING id""", (operation_id,)).fetchone()
            connection.commit()
            return int(row["id"]) if row else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(assign, ["parallel-assign-01", "parallel-assign-02"]))
    assert sum(value is not None for value in results) == 1
    with psycopg.connect(test_database_url, row_factory=dict_row) as verify:
        _schema(verify, schema)
        assert verify.execute("""SELECT COUNT(*) AS value FROM organization_assessment_assignments
            WHERE status='active' AND revoked_at IS NULL""").fetchone()["value"] == 1


def test_started_side_wins_cancel_start_race(test_database_url):
    schema = "adm31_race_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as setup:
        _setup(setup, schema)
        assignment_id = _assignment(setup, "race")
        setup.execute("INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,status) VALUES(2,10,%s,'prepared')", (assignment_id,))
        setup.commit()

    lock_acquired = Event()
    allow_commit = Event()

    def start() -> str:
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            _schema(connection, schema)
            connection.execute("SELECT pg_advisory_xact_lock(2)")
            connection.execute("UPDATE m5_cycles SET status='active',started_at=NOW() WHERE assignment_id=%s", (assignment_id,))
            lock_acquired.set()
            assert allow_commit.wait(timeout=5)
            connection.commit()
            return "started"

    def cancel() -> str:
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            _schema(connection, schema)
            try:
                cancellation.cancel(connection, organization_id=10, assignment_id=assignment_id,
                                    actor_user_id=1, operation_id="cancel-race-01")
                connection.commit()
                return "cancelled"
            except cancellation.CancellationError as exc:
                connection.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        start_future = pool.submit(start)
        assert lock_acquired.wait(timeout=5)
        cancel_future = pool.submit(cancel)
        allow_commit.set()
        assert (start_future.result(), cancel_future.result()) == ("started", "ASSIGNMENT_ALREADY_STARTED")


def test_cancelled_side_wins_cancel_start_race(test_database_url):
    schema = "adm31_cancel_first_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as setup:
        _setup(setup, schema)
        assignment_id = _assignment(setup, "cancel-first")
        setup.execute("INSERT INTO m5_cycles(owner_user_id,organization_id,assignment_id,status) VALUES(2,10,%s,'prepared')", (assignment_id,))
        setup.commit()
        cancellation.cancel(setup, organization_id=10, assignment_id=assignment_id,
                            actor_user_id=1, operation_id="cancel-first-01")
        setup.commit()

    with psycopg.connect(test_database_url, row_factory=dict_row) as start:
        _schema(start, schema)
        start.execute("SELECT pg_advisory_xact_lock(2)")
        active = start.execute("""SELECT 1 FROM organization_assessment_assignments
            WHERE id=%s AND status='active' AND revoked_at IS NULL FOR UPDATE""", (assignment_id,)).fetchone()
        assert active is None
        assert start.execute("SELECT status,started_at FROM m5_cycles WHERE assignment_id=%s", (assignment_id,)).fetchone() == {
            "status": "prepared", "started_at": None,
        }

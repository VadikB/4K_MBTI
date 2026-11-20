from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_questionnaire_source_schema
from Api.questionnaire_sources import (
    admin_assignment_readiness, assignment_readiness, confirm, parse_csv, public_revision, save_preview,
)
from Api.m8_report_access import ensure_schema as ensure_report_access_schema


pytestmark = pytest.mark.integration
EXAMPLE = Path("assessment_definitions/questionnaires/corporate/0.2/example.synthetic.csv")


def test_csv_preview_confirmation_is_idempotent_and_publishes_provenance(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "questionnaire_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,full_name TEXT,email TEXT)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY,code TEXT,name TEXT,is_active BOOLEAN DEFAULT TRUE,updated_at TIMESTAMP DEFAULT NOW())")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,recipient_email TEXT,purpose TEXT,
            assignment_ref TEXT,created_by_user_id BIGINT,revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE organization_assessment_assignments(
            organization_id BIGINT,recipient_user_id BIGINT,assignment_ref TEXT,status TEXT,
            revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE participant_acquaintance_confirmations(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,organization_id BIGINT,assignment_ref TEXT,
            personalized_profile_id BIGINT,questionnaire_revision_id BIGINT,confirmed_at TIMESTAMP DEFAULT NOW())""")
        connection.execute("""CREATE TABLE assessment_preparation_jobs(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,status TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        connection.execute("CREATE TABLE m5_cycles(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE m8_reports(id UUID PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES(1,'Участник','participant@example.test'),(2,'Администратор','admin@example.test')")
        connection.execute("INSERT INTO organizations(id,code,name) VALUES(10,'org-a','Организация А'),(20,'org-b','Организация Б')")
        connection.execute("""CREATE TABLE assessment_organization_contexts(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT NOT NULL REFERENCES organizations(id),
            code TEXT NOT NULL,created_at TIMESTAMP NOT NULL DEFAULT NOW(),UNIQUE(organization_id,code))""")
        connection.execute("""CREATE TABLE assessment_organization_context_versions(
            id BIGSERIAL PRIMARY KEY,organization_context_id BIGINT NOT NULL REFERENCES assessment_organization_contexts(id),
            version INTEGER NOT NULL,status TEXT NOT NULL,definition_json JSONB NOT NULL,
            source_manifest_json JSONB NOT NULL DEFAULT '{}'::jsonb,checksum TEXT NOT NULL,
            confirmed_by_user_id BIGINT REFERENCES users(id),confirmed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),UNIQUE(organization_context_id,version))""")
        ensure_questionnaire_source_schema(connection)
        ensure_report_access_schema(connection)
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin')")
        connection.execute("""INSERT INTO organization_invitations(
            organization_id,recipient_email,purpose,assignment_ref,created_by_user_id,revoked_at)
            VALUES
              (10,'participant@example.test','personal_registration','synthetic-assignment',2,NULL),
              (10,'admin@example.test','personal_registration','synthetic-assignment',1,NULL),
              (10,'participant@example.test','personal_registration','second-assignment',2,NULL),
              (10,'admin@example.test','personal_registration','second-assignment',1,NOW())""")

        kwargs = dict(
            organization_id=10, assignment_ref="synthetic-assignment", channel="csv",
            template_variant="corporate", template_version="0.2", answers={},
            raw_text=EXAMPLE.read_text(), uploaded_by=1,
            source_author="Синтетический заказчик", idempotency_key="preview-1",
        )
        preview = save_preview(connection, **kwargs)
        replay = save_preview(connection, **kwargs)
        assert preview["id"] == replay["id"]
        assert preview["status"] == "ready_for_confirmation"
        assert public_revision(preview)["source_author"] == "Синтетический заказчик"
        assert public_revision(preview)["effective_confirmed"] is None
        assert admin_assignment_readiness(connection, organization_id=10,
                                          assignment_ref="synthetic-assignment")["early"]["status"] == "draft_unconfirmed"
        for channel in ("csv", "product_form"):
            for field in ("case_reality_level", "organization_name_usage_rules"):
                invalid_answers = parse_csv(EXAMPLE.read_text())["answers"]
                old_value = invalid_answers["C17"][field]
                invalid_answers["C17"][field] = "Неизвестный вариант"
                invalid = save_preview(connection, **{
                    **kwargs, "channel": channel, "answers": invalid_answers,
                    "raw_text": EXAMPLE.read_text().replace(
                        f"C17,{field},{old_value}", f"C17,{field},Неизвестный вариант",
                    ) if channel == "csv" else None,
                    "idempotency_key": f"invalid-{channel}-{field}",
                })
                projected = public_revision(invalid)
                assert projected["status"] == "invalid"
                assert projected["answers_json"]["C17"][field] == "Неизвестный вариант"
                assert any(error["field"] == field and error["code"] == "CONTEXT_CHOICE_UNSUPPORTED"
                           for error in projected["validation_json"]["errors"])
                with pytest.raises(ValueError, match="QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION"):
                    confirm(connection, revision_id=invalid["id"], organization_id=10, confirmed_by=2)
        assert connection.execute("SELECT name FROM organizations WHERE id=10").fetchone()["name"] == "Организация А"
        assert connection.execute("SELECT COUNT(*) AS n FROM assessment_organization_context_versions").fetchone()["n"] == 0
        old_form = save_preview(connection, **{
            **kwargs, "channel": "product_form", "raw_text": None,
            "answers": parse_csv(EXAMPLE.read_text())["answers"], "idempotency_key": "old-form-draft",
        })
        connection.execute("""UPDATE questionnaire_response_revisions
            SET answers_json=jsonb_set(answers_json,'{C17,case_reality_level}',
                '"Неизвестный вариант"'::jsonb),validation_json='{"errors":[],"missing":[]}'::jsonb,
                status='ready_for_confirmation' WHERE id=%s""", (old_form["id"],))
        with pytest.raises(ValueError, match="QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION"):
            confirm(connection, revision_id=old_form["id"], organization_id=10, confirmed_by=2)
        assert connection.execute("SELECT COUNT(*) AS n FROM assessment_organization_context_versions").fetchone()["n"] == 0
        # The product form supplies the early minimum, without optional C02b.
        connection.execute("UPDATE questionnaire_response_revisions SET answers_json=answers_json-'C02b' WHERE id=%s", (preview['id'],))

        confirmed = confirm(
            connection, revision_id=preview["id"], organization_id=10,
            confirmed_by=2,
        )
        assert confirmed["status"] == "confirmed"
        version = connection.execute(
            "SELECT * FROM assessment_organization_context_versions WHERE id=%s",
            (confirmed["organization_context_version_id"],),
        ).fetchone()
        assert version["status"] == "published"
        assert version["definition_json"]["name"] == "Синтетическая организация"
        assert connection.execute("SELECT id,code,name FROM organizations WHERE id=10").fetchone() == {
            "id": 10, "code": "org-a", "name": "Синтетическая организация",
        }
        assert connection.execute("SELECT name FROM organizations WHERE id=20").fetchone()["name"] == "Организация Б"
        assert "participant_briefing" not in version["definition_json"]
        assert confirmed["briefing_json"]["purpose"]
        assert "result_recipients" not in confirmed["briefing_json"]
        assert "recipient_mapping" not in confirmed["briefing_json"]
        assert "authorized_recipients" not in confirmed["briefing_json"]
        assert "responsible_contact" not in confirmed["briefing_json"]
        assert confirmed["briefing_json"]["assignment_ref"] == "synthetic-assignment"
        assert version["source_manifest_json"]["questionnaire_revision_id"] == preview["id"]
        assert version["source_manifest_json"]["channel"] == "csv"
        assert version["source_manifest_json"]["admin_context_choices"]["version"] == "1.0"
        assert version["source_manifest_json"]["legacy_context_choices"]["version"] == "1.0"
        assert confirm(
            connection, revision_id=preview["id"], organization_id=10,
            confirmed_by=2,
        )["organization_context_version_id"] == confirmed["organization_context_version_id"]
        assert connection.execute("SELECT COUNT(*) AS n FROM questionnaire_response_revisions WHERE id=%s AND status='confirmed'",
                                  (preview["id"],)).fetchone()["n"] == 1
        rename_answers = parse_csv(EXAMPLE.read_text())["answers"]
        rename_answers["C01"]["name"] = "Новое название"
        conflicting = save_preview(connection, **{
            **kwargs, "channel": "product_form", "raw_text": None,
            "answers": rename_answers, "idempotency_key": "preview-name-conflict",
        })
        connection.execute("UPDATE organizations SET name='Параллельная правка' WHERE id=10")
        with pytest.raises(ValueError, match="QUESTIONNAIRE_ORGANIZATION_NAME_CONFLICT"):
            confirm(connection, revision_id=conflicting["id"], organization_id=10, confirmed_by=2)
        assert connection.execute("SELECT name FROM organizations WHERE id=10").fetchone()["name"] == "Параллельная правка"
        assert connection.execute("SELECT status FROM questionnaire_response_revisions WHERE id=%s", (conflicting["id"],)).fetchone()["status"] != "confirmed"
        connection.execute("UPDATE organizations SET name='Синтетическая организация' WHERE id=10")
        failing = save_preview(connection, **{
            **kwargs, "channel": "product_form", "raw_text": None,
            "answers": rename_answers, "idempotency_key": "preview-publish-failure",
        })
        from Api import questionnaire_sources
        original_publish = questionnaire_sources.publish_organization_context
        monkeypatch.setattr(questionnaire_sources, "publish_organization_context",
                            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic publish failure")))
        with pytest.raises(RuntimeError, match="synthetic publish failure"):
            with connection.transaction():
                confirm(connection, revision_id=failing["id"], organization_id=10, confirmed_by=2)
        monkeypatch.setattr(questionnaire_sources, "publish_organization_context", original_publish)
        assert connection.execute("SELECT name FROM organizations WHERE id=10").fetchone()["name"] == "Синтетическая организация"
        assert connection.execute("SELECT status FROM questionnaire_response_revisions WHERE id=%s", (failing["id"],)).fetchone()["status"] != "confirmed"
        incomplete = save_preview(connection, **{
            **kwargs, "channel": "product_form", "raw_text": None,
            "answers": {"C01": {"name": "Новый неполный черновик"}},
            "idempotency_key": "preview-incomplete-next",
        })
        assert incomplete["status"] == "draft"
        assert public_revision(incomplete, confirmed_row=confirmed)["effective_confirmed"]["id"] == confirmed["id"]
        assert admin_assignment_readiness(connection, organization_id=10,
                                          assignment_ref="synthetic-assignment")["early"]["status"] == "ready"
        assert admin_assignment_readiness(connection, organization_id=10,
                                          assignment_ref="missing-assignment")["early"]["status"] == "data_missing"
        assert confirm(connection, revision_id=preview["id"], organization_id=10,
                       confirmed_by=2)["id"] == preview["id"]

        stale = save_preview(connection, **{
            **kwargs, "idempotency_key": "preview-stale",
            "raw_text": EXAMPLE.read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Устаревшая цель",
            ),
        })
        stale_other_assignment = save_preview(connection, **{
            **kwargs, "assignment_ref": "parallel-assignment",
            "idempotency_key": "preview-parallel-assignment",
        })
        fresh = save_preview(connection, **{
            **kwargs, "idempotency_key": "preview-fresh",
            "raw_text": EXAMPLE.read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Новая опубликованная цель",
            ),
        })
        projection = public_revision(fresh, confirmed_row=confirmed)
        assert projection["participant_preview"]["purpose"] == "Новая опубликованная цель"
        assert projection["is_first_publication"] is False
        assert {item["field"] for item in projection["changes"]} == {
            "purpose",
        }
        assert "questionnaire_revision_id" not in projection["participant_preview"]
        confirm(connection, revision_id=fresh["id"], organization_id=10,
                confirmed_by=2)
        with pytest.raises(ValueError, match="QUESTIONNAIRE_REVISION_CONFLICT"):
            confirm(connection, revision_id=stale["id"], organization_id=10,
                    confirmed_by=2)
        with pytest.raises(ValueError, match="QUESTIONNAIRE_CONTEXT_VERSION_CONFLICT"):
            confirm(connection, revision_id=stale_other_assignment["id"], organization_id=10,
                    confirmed_by=2)

        second_kwargs = {
            **kwargs, "assignment_ref": "second-assignment", "idempotency_key": "preview-2",
            "template_version": "0.1",
            "raw_text": Path("assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv").read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Отдельная цель второй оценки",
            ),
        }
        second = save_preview(connection, **second_kwargs)
        assert second["answers_json"] == parse_csv(EXAMPLE.read_text().replace(
            "Познакомиться с форматом оценки и получить развивающую обратную связь",
            "Отдельная цель второй оценки",
        ))["answers"]
        connection.execute("""UPDATE questionnaire_response_revisions
            SET status='draft',validation_json='{"errors":[],"missing":["C04.answer","C21.responsible_contact"]}'::jsonb
            WHERE id=%s""", (second["id"],))
        saved_old_draft = connection.execute("SELECT * FROM questionnaire_response_revisions WHERE id=%s",
                                             (second["id"],)).fetchone()
        assert public_revision(saved_old_draft)["status"] == "ready_for_confirmation"
        confirm(connection, revision_id=second["id"], organization_id=10,
                confirmed_by=2)
        without_organizer = parse_csv(EXAMPLE.read_text())["answers"]
        without_organizer.pop("C21")
        without_organizer["C17"].update({
            "case_reality_level": "Близко к реальной работе",
            "organization_name_usage_rules": "Использовать условное название",
        })
        manual = save_preview(connection, **{
            **kwargs, "assignment_ref": "manual-assignment", "channel": "product_form",
            "raw_text": None, "answers": without_organizer,
            "idempotency_key": "preview-manual",
        })
        assert manual["status"] == "ready_for_confirmation"
        manual_confirmed = confirm(connection, revision_id=manual["id"], organization_id=10,
                                   confirmed_by=2)
        assert manual_confirmed["status"] == "confirmed"
        manual_version = connection.execute(
            "SELECT source_manifest_json FROM assessment_organization_context_versions WHERE id=%s",
            (manual_confirmed["organization_context_version_id"],),
        ).fetchone()
        assert manual_version["source_manifest_json"]["admin_context_choices"] == {
            "id": "admin-organization-context-choices", "version": "1.0",
            "sha256": "b76cb4b804de2916b074f4070858f7e4fb53e87328ad03191c2b21ace7feaf8a",
        }
        assert "legacy_context_choices" not in manual_version["source_manifest_json"]
        assert manual_confirmed["briefing_json"]["organizer"] == ""
        assert assignment_readiness(connection, organization_id=10,
                                    assignment_ref="manual-assignment")["status"] == "ready"
        first_ready = assignment_readiness(
            connection, organization_id=10, assignment_ref="synthetic-assignment",
        )
        second_ready = assignment_readiness(
            connection, organization_id=10, assignment_ref="second-assignment",
        )
        assert first_ready["briefing"]["purpose"] != second_ready["briefing"]["purpose"]
        first_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="synthetic-assignment",
        )
        second_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="second-assignment",
        )
        missing_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="missing-assignment",
        )
        assert first_admin["assignment_ref"] == "synthetic-assignment"
        assert second_admin["assignment_ref"] == "second-assignment"
        assert first_admin["roles"]["total"] == 2
        assert second_admin["roles"]["total"] == 1
        assert missing_admin["roles"]["total"] == 0
        assert first_admin["early"]["status"] == second_admin["early"]["status"] == "ready"
        assert missing_admin["early"]["status"] == "data_missing"

        # Direct self-assignment works without a registration invitation. Overlap
        # with legacy and foreign/revoked assignments must not inflate the count.
        connection.execute("DELETE FROM organization_invitations WHERE recipient_email='admin@example.test'")
        connection.execute("""INSERT INTO organization_assessment_assignments VALUES
            (10,2,'synthetic-assignment','active',NULL),
            (10,1,'synthetic-assignment','active',NULL),
            (10,2,'second-assignment','active',NOW()),
            (20,2,'second-assignment','active',NULL),
            (10,2,'other-assignment','active',NULL)""")
        connection.execute("INSERT INTO assessment_preparation_jobs(user_id,status) VALUES(2,'running')")
        direct = admin_assignment_readiness(connection, organization_id=10, assignment_ref="synthetic-assignment")
        assert direct["roles"]["total"] == 2
        # An unscoped old job cannot prove preparation of this assignment.
        assert direct["preparation"]["status"] == "idle"
        assert admin_assignment_readiness(connection, organization_id=10,
                                          assignment_ref="second-assignment")["roles"]["total"] == 1

        with pytest.raises(ValueError, match="QUESTIONNAIRE_REVISION_NOT_FOUND"):
            confirm(
                connection, revision_id=preview["id"], organization_id=20,
                confirmed_by=2,
            )
        connection.rollback()


@pytest.fixture
def readiness_db(test_database_url):
    """Real M4 snapshots and questionnaire lifecycle, synthetic isolated records."""
    import json
    from Api.database import ensure_role_profile_schema, ensure_assessment_context_schema
    from Api.assessment_role_profiles import publish_base_roles
    from Api import assessment_contexts as contexts
    with psycopg.connect(test_database_url, row_factory=dict_row) as c:
        schema = 'adm_fix_pytest_' + uuid4().hex
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
        tables = {
            'user_platform_roles': 'user_id bigint,platform_role_id bigint,revoked_at timestamp',
            'platform_role_permissions': 'platform_role_id bigint',
            'assessment_program_definitions': 'id bigint,code text,version text,name text,assignment_ref text,mode text,status text,assessment_configuration_id bigint,catalog_version_id bigint,source_refs_json jsonb,definition_checksum text',
            'organization_assessment_program_connections': 'id bigint,organization_id bigint,program_definition_id bigint,connected_at timestamp,is_current boolean',
            'users': 'id bigint PRIMARY KEY,full_name text,email text,selected_role_profile_version_id bigint',
            'organizations': 'id bigint PRIMARY KEY,code text,name text,is_active boolean,updated_at timestamp',
            'organization_memberships': 'organization_id bigint,user_id bigint,role text',
            'organization_invitations': 'id bigint,organization_id bigint,recipient_email text,purpose text,assignment_ref text,created_by_user_id bigint,revoked_at timestamp',
            'organization_assessment_assignments': 'id bigint PRIMARY KEY,organization_id bigint,recipient_user_id bigint,assignment_ref text,status text,revoked_at timestamp',
            'organization_assessment_source_bindings': 'id bigint,assignment_id bigint,questionnaire_revision_id bigint,assessment_configuration_id bigint,role_profile_version_id bigint,created_at timestamp DEFAULT NOW()',
            'participant_acquaintance_confirmations': 'id bigserial PRIMARY KEY,user_id bigint,organization_id bigint,assignment_ref text,questionnaire_revision_id bigint,personalized_profile_id bigint,confirmed_at timestamp DEFAULT NOW()',
            'assessment_methodologies': 'id bigint PRIMARY KEY',
            'assessment_methodology_versions': 'id bigint PRIMARY KEY,methodology_id bigint,status text,definition_json jsonb',
            'assessment_configurations': 'id bigint PRIMARY KEY,methodology_version_id bigint,status text',
            'user_sessions': 'id bigint PRIMARY KEY,user_id bigint,execution_snapshot_json jsonb,execution_checksum text',
            'assessment_preparation_jobs': 'id bigint PRIMARY KEY,user_id bigint,operation_id text,status text,created_at timestamp',
            'product_cycle_preparation_operations': 'id bigint,operation_id text,status text,user_id bigint,request_json jsonb,created_at timestamp,result_json jsonb',
            'm5_cycles': 'id bigint,cycle_id text,status text,owner_user_id bigint,organization_id bigint,assignment_id bigint,usage_scope text,personalized_profile_id bigint,created_at timestamp,collection_closed_at timestamp',
        }
        for table, columns in tables.items():
            c.execute('CREATE TABLE ' + table + '(' + columns + ')')
        c.execute("INSERT INTO users VALUES(1,'Участник А','a@example.test',NULL),(2,'Администратор','admin@example.test',NULL),(3,'Участник Б','b@example.test',NULL)")
        c.execute("INSERT INTO organizations VALUES(10,'synthetic','Синтетическая организация',TRUE,NOW()),(20,'foreign','Чужая',TRUE,NOW())")
        c.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(10,3,'member')")
        c.execute('INSERT INTO assessment_methodologies VALUES(1)')
        c.execute("INSERT INTO assessment_methodology_versions VALUES(1,1,'published','{\"methodology_version\":\"1.1\"}')")
        c.execute("INSERT INTO assessment_configurations VALUES(1,1,'published')")
        ensure_role_profile_schema(c)
        ensure_assessment_context_schema(c)
        ensure_questionnaire_source_schema(c)
        package = Path('assessment_definitions/role_profiles/competencies_4k/1.1')
        roles = publish_base_roles(c, package=json.loads((package/'base_roles.json').read_text()),
            manifest=json.loads((package/'manifest.json').read_text()), published_by_user_id=2,
            decision_basis='synthetic ADM-FIX-01 regression')
        role_id = roles['version_ids'][0]
        c.execute('UPDATE users SET selected_role_profile_version_id=%s', (role_id,))
        def preview(key, text=None):
            return save_preview(c, organization_id=10, assignment_ref='A', channel='csv',
                template_variant='corporate', template_version='0.2', answers={},
                raw_text=text or EXAMPLE.read_text(), uploaded_by=2, source_author='', idempotency_key=key)
        revision = confirm(c, revision_id=preview('initial')['id'], organization_id=10, confirmed_by=2)
        def assign(user_id, assignment_id, revision):
            c.execute("INSERT INTO organization_assessment_assignments VALUES(%s,10,%s,'A','active',NULL)", (assignment_id,user_id))
            c.execute('INSERT INTO organization_assessment_source_bindings(id,assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id) VALUES(%s,%s,%s,1,%s)',
                      (assignment_id,assignment_id,revision['id'],role_id))
            user_context = contexts.create_user_context_draft(c, user_id=user_id,
                identity={'full_name': 'Синтетический участник'}, professional={})
            contexts.confirm_user_context(c, version_id=user_context, user_id=user_id)
            profile = contexts.create_personalized_profile(c, user_id=user_id, assessment_configuration_id=1,
                organization_context_version_id=revision['organization_context_version_id'],
                role_profile_version_id=role_id, user_context_version_id=user_context)
            c.execute("INSERT INTO participant_acquaintance_confirmations(user_id,organization_id,assignment_ref,questionnaire_revision_id,personalized_profile_id) VALUES(%s,10,'A',%s,%s)",
                      (user_id,revision['id'],profile['id']))
            return profile
        c.commit()
        try:
            yield c, revision, assign, preview
        finally:
            c.rollback()
            c.execute('SET search_path TO public')
            c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))
            c.commit()


def test_admin_readiness_uses_frozen_revision_and_real_late_gate(readiness_db):
    c, original, assign, preview = readiness_db
    profile_a = assign(1, 41, original)
    before = c.execute('SELECT * FROM assessment_personalized_profiles ORDER BY id').fetchall()
    first = admin_assignment_readiness(c, organization_id=10, assignment_ref='A')
    assert first['roles']['ready'] == 1
    fresh = confirm(c, revision_id=preview('next')['id'], organization_id=10, confirmed_by=2)
    assert fresh['organization_context_version_id'] != original['organization_context_version_id']
    assert admin_assignment_readiness(c, organization_id=10, assignment_ref='A')['roles']['ready'] == 1
    profile_b = assign(3, 42, fresh)
    assert admin_assignment_readiness(c, organization_id=10, assignment_ref='A')['roles']['ready'] == 2
    after = c.execute('SELECT * FROM assessment_personalized_profiles ORDER BY id').fetchall()
    assert after[0] == before[0]
    assert after[0]['checksum'] == profile_a['checksum']
    assert after[1]['checksum'] == profile_b['checksum']
    # The exact current confirmation points at a profile of another revision.
    c.execute('UPDATE participant_acquaintance_confirmations SET personalized_profile_id=%s WHERE user_id=3', (profile_a['id'],))
    mismatch = admin_assignment_readiness(c, organization_id=10, assignment_ref='A')
    assert mismatch['roles']['ready'] == 1
    assert mismatch['roles']['reasons']['profile_binding'] == 1
    c.execute('DELETE FROM participant_acquaintance_confirmations WHERE user_id=1')
    missing = admin_assignment_readiness(c, organization_id=10, assignment_ref='A')
    assert missing['roles']['ready'] == 0
    assert missing['roles']['reasons']['acquaintance_wait'] == 1


def test_questionnaire_http_read_save_and_confirm_after_acquaintance(readiness_db, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import routes
    from Api import org_access
    c, original, assign, preview = readiness_db
    @contextmanager
    def connection():
        yield c
    actor = SimpleNamespace(id=2, email='admin@example.test')
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', lambda _: actor)
    # Empty synthetic configuration; membership checks and program validation are real.
    for setting in ('superadmin_emails_raw','org_admin_emails_raw','org_member_domains_raw','org_names_raw'):
        monkeypatch.setattr(org_access.settings, setting, '')
    app = FastAPI()
    app.include_router(routes.router)
    prefix = '/users/admin/organizations/10/questionnaire'
    with TestClient(app, raise_server_exceptions=False) as http:
        def save(key):
            response = http.post(prefix+'/preview', json={'assignment_ref':'A','csv_text':EXAMPLE.read_text(),'idempotency_key':key})
            assert response.status_code == 201, response.text
            read = http.get(prefix+'/'+str(response.json()['id']))
            assert read.status_code == 200
            assert read.json()['answers_json'] == response.json()['answers_json']
            return response.json()
        assert http.get(prefix).status_code == 200
        save('before-acquaintance')
        assign(1, 41, original)
        c.commit()
        response = http.get(prefix)
        assert response.status_code == 200, response.text
        assert response.json()['items'][0]['readiness']['roles']['ready'] == 1
        saved = save('after-acquaintance')
        assert saved['readiness']['roles']['ready'] == 1
        invalid_csv = EXAMPLE.read_text().replace('C17,case_reality_level,обобщённый',
                                                   'C17,case_reality_level,Неизвестный вариант')
        invalid = http.post(prefix+'/preview', json={
            'assignment_ref': 'A', 'csv_text': invalid_csv, 'idempotency_key': 'invalid-http-csv',
        })
        assert invalid.status_code == 201, invalid.text
        assert invalid.json()['status'] == 'invalid'
        assert invalid.json()['answers_json']['C17']['case_reality_level'] == 'Неизвестный вариант'
        assert http.post(prefix+'/'+str(invalid.json()['id'])+'/confirm', json={}).status_code == 409
        from Api import questionnaire_sources
        original_package = questionnaire_sources.ADMIN_CHOICES_PACKAGE
        monkeypatch.setattr(questionnaire_sources, 'ADMIN_CHOICES_PACKAGE', Path('/nonexistent-policy'))
        unavailable = http.post(prefix+'/'+str(saved['id'])+'/confirm', json={})
        assert unavailable.status_code == 409
        assert unavailable.json()['detail'] == 'ADMIN_CONTEXT_CHOICES_UNAVAILABLE'
        monkeypatch.setattr(questionnaire_sources, 'ADMIN_CHOICES_PACKAGE', original_package)
        confirmed = http.post(prefix+'/'+str(saved['id'])+'/confirm', json={})
        assert confirmed.status_code == 200, confirmed.text
        exact = http.get(prefix+'/'+str(saved['id']))
        assert exact.status_code == 200 and exact.json()['status'] == 'confirmed'
        assert exact.json()['answers_json'] == confirmed.json()['answers_json']
        response = http.get(prefix)
        assert response.status_code == 200, response.text
        assert response.json()['items'][0]['readiness']['roles']['ready'] == 1
        fresh = c.execute('SELECT * FROM questionnaire_response_revisions WHERE id=%s', (saved['id'],)).fetchone()
        assign(3, 42, fresh)
        profile_a = c.execute('SELECT personalized_profile_id FROM participant_acquaintance_confirmations WHERE user_id=1').fetchone()['personalized_profile_id']
        c.execute('UPDATE participant_acquaintance_confirmations SET personalized_profile_id=%s WHERE user_id=3', (profile_a,))
        c.commit()
        mismatch = http.get(prefix)
        assert mismatch.status_code == 200
        assert mismatch.json()['items'][0]['readiness']['roles']['reasons'] == {'profile_binding':1}
        c.execute('DELETE FROM participant_acquaintance_confirmations WHERE user_id=3')
        c.commit()
        missing = http.get(prefix)
        assert missing.status_code == 200
        assert missing.json()['items'][0]['readiness']['roles']['reasons'] == {'acquaintance_wait':1}
        import json
        bound = c.execute('SELECT personalized_profile_id FROM participant_acquaintance_confirmations WHERE user_id=1').fetchone()
        c.execute("INSERT INTO product_cycle_preparation_operations VALUES(1,'http-exact','running',1,%s::jsonb,NOW(),NULL)",
            (json.dumps({'organization_id':10,'assignment_ref':'A','assignment_id':41,
                'questionnaire_revision_id':original['id'],'personalized_profile_id':bound['personalized_profile_id']}),))
        c.commit()
        for _ in range(2):
            response = http.get(prefix)
            assert response.status_code == 200
            assert response.json()['items'][0]['readiness']['preparation']['status'] == 'in_progress'
        assert c.execute('SELECT COUNT(*) AS n FROM product_cycle_preparation_operations').fetchone()['n'] == 1
        # Platform admin uses the same readiness and exact read routes.
        c.execute("INSERT INTO users VALUES(5,'Суперадминистратор',%s,NULL)", (routes.ADMIN_EMAIL,))
        c.commit()
        actor = SimpleNamespace(id=5, email=routes.ADMIN_EMAIL)
        assert http.get(prefix).status_code == 200
        super_saved = save('superadmin-after')
        super_confirmed = http.post(prefix+'/'+str(super_saved['id'])+'/confirm', json={})
        assert super_confirmed.status_code == 200, super_confirmed.text
        assert super_confirmed.json()['readiness'] is not None
        assert http.get(prefix+'/'+str(super_saved['id'])).json()['status'] == 'confirmed'
        c.execute("INSERT INTO users VALUES(4,'Чужой администратор','foreign@example.test',NULL)")
        c.execute("INSERT INTO organization_memberships VALUES(20,4,'admin')")
        c.commit()
        actor = SimpleNamespace(id=4, email='foreign@example.test')
        assert http.get(prefix).status_code == 403
        assert http.post(prefix+'/preview', json={'assignment_ref':'A','csv_text':EXAMPLE.read_text(),'idempotency_key':'foreign'}).status_code == 403
        assert http.get(prefix+'/'+str(saved['id'])).status_code == 403
        assert http.post(prefix+'/'+str(saved['id'])+'/confirm', json={}).status_code == 403


@pytest.mark.parametrize('status', ['queued', 'running'])
def test_summary_preparation_is_exact_and_read_only(readiness_db, status):
    import json
    from Api.admin_assignment_projection import preparation_for_assignment
    c, revision, assign, preview = readiness_db
    previous = assign(1, 40, revision)
    c.execute("UPDATE organization_assessment_assignments SET status='revoked',revoked_at=NOW() WHERE id=40")
    profile = assign(1, 41, revision)
    request = {'organization_id':10,'assignment_ref':'A','assignment_id':41,
        'questionnaire_revision_id':revision['id'],'personalized_profile_id':profile['id']}
    c.execute("INSERT INTO product_cycle_preparation_operations VALUES(1,'exact',%s,1,%s::jsonb,NOW(),NULL)", (status,json.dumps(request)))
    for identifier, changes in enumerate([
        {'organization_id':20}, {'assignment_id':99}, {'assignment_ref':'B'},
        {'questionnaire_revision_id':999}, {'personalized_profile_id':999},
    ], start=2):
        c.execute("INSERT INTO product_cycle_preparation_operations VALUES(%s,%s,'failed',1,%s::jsonb,NOW()+INTERVAL '1 minute',NULL)",
                  (identifier,'foreign-'+str(identifier),json.dumps({**request,**changes})))
    c.execute("INSERT INTO product_cycle_preparation_operations VALUES(9,'other-user','failed',3,%s::jsonb,NOW()+INTERVAL '1 minute',NULL)", (json.dumps(request),))
    # Previous generation of the same participant has a newer legacy job.
    c.execute("INSERT INTO assessment_preparation_jobs(id,user_id,operation_id,status,personalized_profile_id,created_at) VALUES(1,1,'old','failed',%s,NOW()+INTERVAL '2 minutes')", (previous['id'],))
    counts = c.execute('SELECT COUNT(*) AS n FROM product_cycle_preparation_operations').fetchone()
    assert preparation_for_assignment(c, assignment_id=41) == {'operation_id':'exact','status':status}
    for _ in range(2):
        result = admin_assignment_readiness(c, organization_id=10, assignment_ref='A')
        assert result['roles']['ready'] == 1
        assert result['preparation']['status'] == 'in_progress'
        assert result['status'] == 'preparing'
    assert c.execute('SELECT COUNT(*) AS n FROM product_cycle_preparation_operations').fetchone() == counts
    c.execute("UPDATE product_cycle_preparation_operations SET status='completed' WHERE id=1")
    # An unrelated running job never changes this assignment's idle summary.
    c.execute("UPDATE product_cycle_preparation_operations SET status='running' WHERE id>1")
    assert admin_assignment_readiness(c, organization_id=10, assignment_ref='A')['preparation']['status'] == 'idle'


def test_missing_context_is_a_readiness_reason(readiness_db):
    from Api.acquaintance import late_readiness
    c, revision, assign, preview = readiness_db
    assign(1, 41, revision)
    result = late_readiness(c, user_id=1, readiness={'status':'ready', 'organization_id':10,
        'assignment_ref':'A', 'questionnaire_revision_id':revision['id'], 'assignment_id':41})
    assert result['status'] == 'waiting_for_assessment_data'
    assert result['reason'] == 'W02_PROFILE_ASSIGNMENT_SCOPE_MISMATCH'
    unbound = preview('missing-context')
    # Compatibility fixture: an old confirmed record has no context reference.
    c.execute("UPDATE questionnaire_response_revisions SET status='confirmed',confirmed_at=NOW() WHERE id=%s", (unbound['id'],))
    assert assignment_readiness(c, organization_id=10, assignment_ref='A',
        questionnaire_revision_id=unbound['id']) == {
        'status':'draft','reason':'organization_context_version','missing':['context']}

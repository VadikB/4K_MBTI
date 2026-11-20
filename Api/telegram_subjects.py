"""Opaque external assessment subjects; never an authentication/provisioning API."""

from __future__ import annotations

from uuid import UUID


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS telegram_assessment_subjects (
        external_subject_ref UUID PRIMARY KEY,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        runtime_owner_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE OR REPLACE FUNCTION protect_telegram_subject() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Telegram assessment subject bindings are immutable'; END
        $$ LANGUAGE plpgsql""")
    connection.execute(
        "DROP TRIGGER IF EXISTS telegram_subject_immutable ON telegram_assessment_subjects"
    )
    connection.execute("""CREATE TRIGGER telegram_subject_immutable BEFORE UPDATE OR DELETE
        ON telegram_assessment_subjects FOR EACH ROW EXECUTE FUNCTION protect_telegram_subject()""")


def resolve(connection, *, external_subject_ref: str, organization_id: int) -> dict:
    """Caller authorizes the configured organization/subject before calling."""
    subject = str(UUID(external_subject_ref))
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("tg-subject:" + subject,),
    )
    previous = connection.execute(
        "SELECT * FROM telegram_assessment_subjects WHERE external_subject_ref=%s",
        (subject,),
    ).fetchone()
    if previous:
        if int(previous["organization_id"]) != organization_id:
            raise ValueError("SUBJECT_ORGANIZATION_CONFLICT")
        return {"external_subject_ref": subject, "status": "existing"}
    organization = connection.execute(
        "SELECT id FROM organizations WHERE id=%s AND is_active=TRUE",
        (organization_id,),
    ).fetchone()
    if not organization:
        raise ValueError("SUBJECT_ORGANIZATION_NOT_AVAILABLE")
    # users is the legacy runtime owner FK, not an account: no email, credentials,
    # user_identities, web roles, verification, sessions or authentication grant.
    owner = connection.execute(
        """INSERT INTO users(full_name,email,role_id,job_description,phone,company_industry)
        VALUES(%s,NULL,NULL,NULL,NULL,NULL) RETURNING id""",
        ("subject:" + subject,),
    ).fetchone()
    connection.execute(
        """INSERT INTO telegram_assessment_subjects
        (external_subject_ref,organization_id,runtime_owner_id) VALUES(%s,%s,%s)""",
        (subject, organization_id, owner["id"]),
    )
    connection.execute(
        """INSERT INTO organization_memberships
        (organization_id,user_id,role,admission_source,admitted_at)
        VALUES(%s,%s,'member','admin_add',NOW())""",
        (organization_id, owner["id"]),
    )
    return {"external_subject_ref": subject, "status": "provisioned"}


def load(connection, subject: str, organization_id: int) -> dict:
    row = connection.execute(
        """SELECT * FROM telegram_assessment_subjects
        WHERE external_subject_ref=%s AND organization_id=%s""",
        (str(UUID(subject)), organization_id),
    ).fetchone()
    if not row:
        raise ValueError("SUBJECT_NOT_FOUND")
    return dict(row)

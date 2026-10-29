"""Validate and create one explicit Specialist pilot assignment binding."""

from __future__ import annotations

import argparse

from Api import assessment_assignment_sources
from Api.database import get_connection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--assignment-ref", required=True)
    parser.add_argument("--configuration-id", type=int, required=True)
    parser.add_argument("--role-profile-version-id", type=int, required=True)
    parser.add_argument("--actor-user-id", type=int, required=True)
    parser.add_argument("--binding-version", default="specialist-pilot/1")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with get_connection() as connection:
        assessment_assignment_sources.ensure_schema(connection)
        configuration = connection.execute("""SELECT configuration.id,configuration.status,
                catalog.status AS catalog_status,catalog.usage_scope
            FROM assessment_configurations configuration
            JOIN m5_catalogs catalog ON catalog.id=configuration.catalog_version_id
            WHERE configuration.id=%s""", (args.configuration_id,)).fetchone()
        role = connection.execute("""SELECT version.id,version.status,version.methodology_version,profile.code
            FROM assessment_role_profile_versions version
            JOIN assessment_role_profiles profile ON profile.id=version.role_profile_id
            WHERE version.id=%s""", (args.role_profile_version_id,)).fetchone()
        if not configuration or configuration["status"] != "published":
            raise SystemExit("Configuration must exist and be published.")
        if configuration["catalog_status"] != "published" or configuration["usage_scope"] != "assessment":
            raise SystemExit("Configuration catalog is not admitted for assessment.")
        if not role or role["status"] != "published" or role["code"] != "specialist_expert":
            raise SystemExit("Role version must be the published specialist_expert role.")
        if str(role["methodology_version"]) != "1.1":
            raise SystemExit("Role methodology version must be 1.1.")
        existing = connection.execute("""SELECT * FROM organization_assessment_pilot_bindings
            WHERE organization_id=%s AND assignment_ref=%s""",
            (args.organization_id, args.assignment_ref)).fetchone()
        expected = (args.configuration_id, args.role_profile_version_id, args.binding_version)
        if existing and (existing["assessment_configuration_id"], existing["role_profile_version_id"],
                         existing["binding_version"]) != expected:
            raise SystemExit("Binding already exists with different immutable sources.")
        if args.apply and not existing:
            connection.execute("""INSERT INTO organization_assessment_pilot_bindings
                (organization_id,assignment_ref,binding_version,assessment_configuration_id,
                 role_profile_version_id,configured_by_user_id) VALUES(%s,%s,%s,%s,%s,%s)""",
                (args.organization_id, args.assignment_ref, args.binding_version,
                 args.configuration_id, args.role_profile_version_id, args.actor_user_id))
            connection.commit()
        print({"status": "existing" if existing else "validated", "apply": args.apply,
               "organization_id": args.organization_id, "assignment_ref": args.assignment_ref,
               "binding_version": args.binding_version, "role": "specialist_expert"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

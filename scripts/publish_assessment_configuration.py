"""Validate or publish an immutable assessment configuration through the release service."""
from __future__ import annotations

import argparse

from Api.assessment_authoring_service import assessment_authoring_service
from Api.database import get_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or publish an assessment configuration.")
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--methodology-code", required=True)
    parser.add_argument("--methodology-version", required=True)
    parser.add_argument("--scenario-code", required=True)
    parser.add_argument("--scenario-version", required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--catalog-version", required=True)
    parser.add_argument("--publisher-user-id", type=int, required=True)
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


def _resolve_dependencies(connection, args: argparse.Namespace) -> dict:
    methodology = connection.execute(
        """SELECT version_row.id,version_row.status
           FROM assessment_methodologies parent
           JOIN assessment_methodology_versions version_row ON version_row.methodology_id=parent.id
           WHERE parent.code=%s
             AND (version_row.version::text=%s OR version_row.definition_json->>'methodology_version'=%s)""",
        (args.methodology_code, args.methodology_version, args.methodology_version),
    ).fetchall()
    if len(methodology) != 1 or methodology[0]["status"] != "published":
        raise SystemExit("Exactly one published methodology version must match.")
    scenario = connection.execute(
        """SELECT version_row.id,version_row.status
           FROM assessment_scenarios parent
           JOIN assessment_scenario_versions version_row ON version_row.scenario_id=parent.id
           WHERE parent.code=%s AND version_row.version::text=%s""",
        (args.scenario_code, args.scenario_version),
    ).fetchall()
    if len(scenario) != 1 or scenario[0]["status"] != "published":
        raise SystemExit("Exactly one published scenario version must match.")
    catalog = connection.execute(
        """SELECT id,status,usage_scope FROM m5_catalogs
           WHERE catalog_id=%s AND catalog_version=%s""",
        (args.catalog_id, args.catalog_version),
    ).fetchall()
    if len(catalog) != 1 or catalog[0]["status"] != "published" \
            or catalog[0]["usage_scope"] != "assessment":
        raise SystemExit("Exactly one published assessment catalog must match.")
    return {
        "methodology_version_id": int(methodology[0]["id"]),
        "scenario_version_id": int(scenario[0]["id"]),
        "catalog_version_id": int(catalog[0]["id"]),
    }


def main() -> int:
    args = parse_args()
    with get_connection() as connection:
        refs = _resolve_dependencies(connection, args)
        existing = connection.execute(
            "SELECT * FROM assessment_configurations WHERE code=%s", (args.code,),
        ).fetchone()
        if existing is not None:
            exact = existing["name"] == args.name and all(
                int(existing[key]) == value for key, value in refs.items()
            )
            if not exact:
                raise SystemExit("Configuration code already exists with different immutable refs.")
            if existing["status"] == "published":
                print(f"ALREADY_PUBLISHED configuration={args.code} id={existing['id']} ")
                connection.rollback()
                return 0
            if existing["status"] != "draft":
                raise SystemExit("Only an exact draft configuration can be published.")
            configuration = dict(existing)
        else:
            configuration = assessment_authoring_service.create_configuration(
                connection, code=args.code, name=args.name,
                methodology_version_id=refs["methodology_version_id"],
                scenario_version_id=refs["scenario_version_id"],
                catalog_version_id=refs["catalog_version_id"],
                actor_user_id=args.publisher_user_id,
                comment="Create accepted assessment configuration through release CLI.",
            )
        published = assessment_authoring_service.publish_configuration(
            connection, configuration_id=int(configuration["id"]), make_default=False,
            actor_user_id=args.publisher_user_id,
            comment="Publish accepted assessment configuration through release CLI.",
        )
        print(
            f"configuration={args.code} id={published['id']} "
            f"catalog_version_id={published['catalog_version_id']} "
            f"checksum={published['prompt_bundle_checksum']}"
        )
        if not args.publish:
            connection.rollback()
            print("VALIDATED_ONLY: transaction rolled back; rerun with --publish through the authorized release process.")
            return 0
        connection.commit()
        print(f"PUBLISHED id={published['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

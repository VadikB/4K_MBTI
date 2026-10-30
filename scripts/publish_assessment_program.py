"""Release command for an immutable ProgramDefinition; publication is always explicit."""
from __future__ import annotations

import argparse
import json

from Api import assessment_programs
from Api.database import get_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Validate or publish an assessment program version.')
    parser.add_argument('--code', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--assignment-ref', required=True)
    parser.add_argument('--mode', required=True)
    parser.add_argument('--configuration-code', required=True)
    parser.add_argument('--role-code', action='append', required=True)
    parser.add_argument('--publisher-user-id', type=int, required=True)
    parser.add_argument('--publish', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with get_connection() as connection:
        configuration = connection.execute("""SELECT c.id,c.status,c.catalog_version_id,
                c.methodology_version_id,c.scenario_version_id,c.prompt_bundle_checksum,
                catalog.status AS catalog_status,catalog.usage_scope
            FROM assessment_configurations c
            JOIN m5_catalogs catalog ON catalog.id=c.catalog_version_id
            WHERE c.code=%s""", (args.configuration_code,)).fetchone()
        if not configuration or configuration['status'] != 'published' \
                or configuration['catalog_status'] != 'published' \
                or configuration['usage_scope'] != 'assessment':
            raise SystemExit('Configuration and its assessment catalog must be published.')
        roles = connection.execute("""SELECT rv.id,r.code,rv.status
            FROM assessment_role_profile_versions rv
            JOIN assessment_role_profiles r ON r.id=rv.role_profile_id
            WHERE r.code=ANY(%s) ORDER BY r.code,rv.version DESC""", (args.role_code,)).fetchall()
        resolved = {}
        for row in roles:
            if row['code'] not in resolved and row['status'] == 'published':
                resolved[row['code']] = int(row['id'])
        if set(resolved) != set(args.role_code):
            raise SystemExit('Every allowed role code must have a published version.')
        role_ids = [resolved[code] for code in args.role_code]
        source_refs = {
            'methodology_version_id': int(configuration['methodology_version_id']),
            'scenario_version_id': int(configuration['scenario_version_id']),
            'prompt_bundle_checksum': configuration['prompt_bundle_checksum'],
        }
        checksum = assessment_programs.definition_checksum(code=args.code, version=args.version,
            name=args.name, assignment_ref=args.assignment_ref, mode=args.mode,
            configuration_id=int(configuration['id']), role_version_ids=role_ids,
            catalog_version_id=int(configuration['catalog_version_id']), source_refs=source_refs)
        print(f'program={args.code}@{args.version} configuration={args.configuration_code} '
              f'roles={",".join(args.role_code)} checksum={checksum}')
        if not args.publish:
            connection.rollback()
            print('VALIDATED_ONLY: rerun with --publish through the authorized release process.')
            return 0
        row = connection.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,
             catalog_version_id,source_refs_json,definition_checksum,published_by_user_id)
            VALUES(%s,%s,%s,%s,%s,'draft',%s,%s,%s::jsonb,%s,%s) RETURNING id""",
            (args.code,args.version,args.name,args.assignment_ref,args.mode,
             configuration['id'],configuration['catalog_version_id'],json.dumps(source_refs),
             checksum,args.publisher_user_id)).fetchone()
        for order, role_id in enumerate(role_ids):
            connection.execute("""INSERT INTO assessment_program_allowed_roles
                (program_definition_id,role_profile_version_id,display_order) VALUES(%s,%s,%s)""",
                (row['id'],role_id,order))
        connection.execute("""UPDATE assessment_program_definitions
            SET status='published',published_at=NOW() WHERE id=%s""", (row['id'],))
        connection.commit()
        print(f'PUBLISHED id={row["id"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

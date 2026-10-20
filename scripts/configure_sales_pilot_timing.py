#!/usr/bin/env python3
"""Dry-run/apply the approved Sales pilot program timing revision."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VALUES = {"time_budget_seconds": 7200, "calendar_window_seconds": 259200}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization-id", required=True, type=int)
    parser.add_argument("--configuration-id", required=True, type=int)
    parser.add_argument("--actor-id", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from Api.database import get_connection
    from Api.m7_parameter_resolution import ensure_schema, save_revision

    with get_connection() as connection:
        ensure_schema(connection)
        scope = connection.execute(
            """SELECT o.is_active AS organization_active,c.status AS configuration_status
               FROM organizations o CROSS JOIN assessment_configurations c
               WHERE o.id=%s AND c.id=%s""",
            (args.organization_id, args.configuration_id),
        ).fetchone()
        if not scope or not scope["organization_active"] or scope["configuration_status"] != "published":
            raise SystemExit("Sales pilot organization/configuration scope is not eligible")
        current = connection.execute(
            """SELECT id,revision_no,values_json,values_checksum FROM m7_parameter_revisions
               WHERE source_scope='program' AND organization_id=%s
                 AND assessment_configuration_id=%s AND status='published'""",
            (args.organization_id, args.configuration_id),
        ).fetchone()
        preview = {
            "mode": "apply" if args.apply else "dry-run",
            "scope": {"organization_id": args.organization_id,
                      "assessment_configuration_id": args.configuration_id},
            "actor_id": args.actor_id,
            "requested_values": VALUES,
            "current_revision_no": int(current["revision_no"]) if current else None,
            "action": "noop" if current and dict(current["values_json"]) == VALUES else "create_revision",
        }
        if not args.apply:
            print(json.dumps(preview, ensure_ascii=False, sort_keys=True))
            connection.rollback()
            return 0
        saved = save_revision(
            connection, source_scope="program", organization_id=args.organization_id,
            assessment_configuration_id=args.configuration_id, values=VALUES,
            created_by=args.actor_id, publish=True,
        )
        connection.commit()
        read_back = connection.execute(
            """SELECT revision_no,status,values_json,values_checksum,created_by,published_at
               FROM m7_parameter_revisions WHERE id=%s""", (saved["id"],)
        ).fetchone()
        print(json.dumps({**preview, "read_back": dict(read_back)}, ensure_ascii=False,
                         sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

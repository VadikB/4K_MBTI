from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Iterable

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


@dataclass(frozen=True)
class TableRef:
    oid: int
    schema: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class ForeignKey:
    parent_oid: int
    child_oid: int
    parent_columns: tuple[str, ...]
    child_columns: tuple[str, ...]
    name: str = ""


def _get(row, name: str, index: int):
    return row[name] if isinstance(row, dict) else row[index]


def database_name(database_url: str) -> str:
    return str(conninfo_to_dict(database_url).get("dbname") or "").strip().lower()


def require_test_database(database_url: str) -> str:
    name = database_name(database_url)
    if "test" not in name and "pytest" not in name:
        raise ValueError("Refusing organization purge: database name must contain test or pytest.")
    return name


def _tables(connection: psycopg.Connection) -> dict[int, TableRef]:
    rows = connection.execute(
        """
        SELECT c.oid::bigint AS oid, n.nspname AS schema_name, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'p') AND n.nspname = current_schema()
        """
    ).fetchall()
    return {
        int(_get(row, "oid", 0)): TableRef(
            int(_get(row, "oid", 0)),
            str(_get(row, "schema_name", 1)),
            str(_get(row, "table_name", 2)),
        )
        for row in rows
    }


def _foreign_keys(connection: psycopg.Connection) -> list[ForeignKey]:
    rows = connection.execute(
        """
        SELECT constraint_row.conrelid::bigint AS child_oid,
               constraint_row.confrelid::bigint AS parent_oid,
               constraint_row.conname AS constraint_name,
               ARRAY(
                   SELECT child_attribute.attname
                   FROM unnest(constraint_row.conkey) WITH ORDINALITY AS key(attnum, position)
                   JOIN pg_attribute child_attribute
                     ON child_attribute.attrelid = constraint_row.conrelid
                    AND child_attribute.attnum = key.attnum
                   ORDER BY key.position
               ) AS child_columns,
               ARRAY(
                   SELECT parent_attribute.attname
                   FROM unnest(constraint_row.confkey) WITH ORDINALITY AS key(attnum, position)
                   JOIN pg_attribute parent_attribute
                     ON parent_attribute.attrelid = constraint_row.confrelid
                    AND parent_attribute.attnum = key.attnum
                   ORDER BY key.position
               ) AS parent_columns
        FROM pg_constraint constraint_row
        JOIN pg_class child_table ON child_table.oid = constraint_row.conrelid
        JOIN pg_namespace child_namespace ON child_namespace.oid = child_table.relnamespace
        JOIN pg_class parent_table ON parent_table.oid = constraint_row.confrelid
        JOIN pg_namespace parent_namespace ON parent_namespace.oid = parent_table.relnamespace
        WHERE constraint_row.contype = 'f'
          AND child_namespace.nspname = current_schema()
          AND parent_namespace.nspname = current_schema()
        """
    ).fetchall()
    return [
        ForeignKey(
            parent_oid=int(_get(row, "parent_oid", 1)),
            child_oid=int(_get(row, "child_oid", 0)),
            parent_columns=tuple(_get(row, "parent_columns", 4)),
            child_columns=tuple(_get(row, "child_columns", 3)),
            name=str(_get(row, "constraint_name", 2)),
        )
        for row in rows
    ]


def _column_tables(connection: psycopg.Connection, column_name: str) -> list[int]:
    rows = connection.execute(
        """
        SELECT DISTINCT c.oid::bigint AS oid
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relkind IN ('r', 'p')
          AND n.nspname = current_schema()
          AND a.attname = %s AND NOT a.attisdropped
        """,
        (column_name,),
    ).fetchall()
    return [int(_get(row, "oid", 0)) for row in rows]


def _seed_by_organization_id(
    connection: psycopg.Connection,
    tables: dict[int, TableRef],
    organization_id: int,
) -> None:
    for oid in _column_tables(connection, "organization_id"):
        table = tables[oid]
        connection.execute(
            sql.SQL(
                "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
                "SELECT %s, target.ctid FROM {}.{} target WHERE target.organization_id = %s "
                "ON CONFLICT DO NOTHING"
            ).format(sql.Identifier(table.schema), sql.Identifier(table.name)),
            (oid, organization_id),
        )


def _seed_legacy_assessment_rows(
    connection: psycopg.Connection,
    tables: dict[int, TableRef],
) -> None:
    by_name = {table.name: table for table in tables.values()}
    if by_name.get("organization_memberships") is None or by_name.get("users") is None:
        return
    for table_name in ("user_sessions", "assessment_preparation_jobs"):
        target = by_name.get(table_name)
        if target is None or target.oid not in _column_tables(connection, "user_id"):
            continue
        connection.execute(
            sql.SQL(
                "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
                "SELECT %s, target.ctid FROM {}.{} target "
                "WHERE EXISTS (SELECT 1 FROM organization_purge_orphan_users candidate "
                "WHERE candidate.user_id = target.user_id) "
                "ON CONFLICT DO NOTHING"
            ).format(
                sql.Identifier(target.schema),
                sql.Identifier(target.name),
            ),
            (target.oid,),
        )


def _seed_orphan_users(
    connection: psycopg.Connection,
    tables: dict[int, TableRef],
    organization_id: int,
) -> None:
    by_name = {table.name: table for table in tables.values()}
    users = by_name.get("users")
    memberships = by_name.get("organization_memberships")
    if users is None or memberships is None:
        return
    connection.execute(
        """
        CREATE TEMP TABLE organization_purge_orphan_users (
            user_id BIGINT PRIMARY KEY
        ) ON COMMIT DROP
        """
    )
    connection.execute(
        sql.SQL(
            "INSERT INTO organization_purge_orphan_users(user_id) "
            "SELECT DISTINCT membership.user_id FROM {}.{} membership "
            "WHERE membership.organization_id = %s "
            "AND NOT EXISTS (SELECT 1 FROM {}.{} other_membership "
            "WHERE other_membership.user_id = membership.user_id "
            "AND other_membership.organization_id <> %s)"
        ).format(
            sql.Identifier(memberships.schema),
            sql.Identifier(memberships.name),
            sql.Identifier(memberships.schema),
            sql.Identifier(memberships.name),
        ),
        (organization_id, organization_id),
    )
    connection.execute(
        sql.SQL(
            "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
            "SELECT %s, target.ctid FROM {}.{} target "
            "JOIN organization_purge_orphan_users candidate ON candidate.user_id = target.id "
            "ON CONFLICT DO NOTHING"
        ).format(sql.Identifier(users.schema), sql.Identifier(users.name)),
        (users.oid,),
    )


def _expand_foreign_keys(
    connection: psycopg.Connection,
    tables: dict[int, TableRef],
    foreign_keys: Iterable[ForeignKey],
) -> None:
    foreign_keys = list(foreign_keys)
    while True:
        inserted = 0
        for foreign_key in foreign_keys:
            parent = tables[foreign_key.parent_oid]
            child = tables[foreign_key.child_oid]
            predicates = [
                sql.SQL("child.{} = parent.{}").format(
                    sql.Identifier(child_column), sql.Identifier(parent_column)
                )
                for child_column, parent_column in zip(
                    foreign_key.child_columns, foreign_key.parent_columns, strict=True
                )
            ]
            cursor = connection.execute(
                sql.SQL(
                    "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
                    "SELECT %s, child.ctid FROM {}.{} child "
                    "JOIN {}.{} parent ON {} "
                    "JOIN organization_purge_rows selected "
                    "ON selected.table_oid = %s AND selected.row_ctid = parent.ctid "
                    "ON CONFLICT DO NOTHING"
                ).format(
                    sql.Identifier(child.schema),
                    sql.Identifier(child.name),
                    sql.Identifier(parent.schema),
                    sql.Identifier(parent.name),
                    sql.SQL(" AND ").join(predicates),
                ),
                (child.oid, parent.oid),
            )
            inserted += int(cursor.rowcount or 0)
        if inserted == 0:
            return


def _delete_order(selected_oids: set[int], foreign_keys: Iterable[ForeignKey]) -> list[int]:
    edges = {
        (foreign_key.parent_oid, foreign_key.child_oid)
        for foreign_key in foreign_keys
        if foreign_key.parent_oid in selected_oids
        and foreign_key.child_oid in selected_oids
        and foreign_key.parent_oid != foreign_key.child_oid
        # The selected users have this nullable back-reference cleared before
        # deletion. Ignoring it breaks the users <-> profiles catalog cycle.
        and foreign_key.name != "users_active_profile_fk"
    }
    depths = {oid: 0 for oid in selected_oids}
    for iteration in range(len(selected_oids)):
        changed = False
        for parent_oid, child_oid in edges:
            candidate = depths[parent_oid] + 1
            if candidate > depths[child_oid]:
                depths[child_oid] = candidate
                changed = True
        if not changed:
            return sorted(selected_oids, key=lambda oid: (depths[oid], oid), reverse=True)
        if iteration == len(selected_oids) - 1:
            raise RuntimeError("Cyclic foreign-key dependency prevents safe automatic purge.")
    return []


def build_purge_plan(connection: psycopg.Connection, organization_id: int) -> tuple[dict[str, int], dict[int, TableRef], list[ForeignKey]]:
    organization = connection.execute(
        "SELECT id, code, name FROM organizations WHERE id = %s FOR UPDATE",
        (organization_id,),
    ).fetchone()
    if organization is None:
        raise LookupError(f"Organization id={organization_id} not found.")

    connection.execute(
        """
        CREATE TEMP TABLE organization_purge_rows (
            table_oid OID NOT NULL,
            row_ctid TID NOT NULL,
            PRIMARY KEY (table_oid, row_ctid)
        ) ON COMMIT DROP
        """
    )
    tables = _tables(connection)
    foreign_keys = _foreign_keys(connection)
    organizations = next(table for table in tables.values() if table.name == "organizations")
    connection.execute(
        sql.SQL(
            "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
            "SELECT %s, target.ctid FROM {}.{} target WHERE target.id = %s"
        ).format(sql.Identifier(organizations.schema), sql.Identifier(organizations.name)),
        (organizations.oid, organization_id),
    )
    _seed_by_organization_id(connection, tables, organization_id)
    _seed_orphan_users(connection, tables, organization_id)
    _seed_legacy_assessment_rows(connection, tables)
    _expand_foreign_keys(connection, tables, foreign_keys)

    rows = connection.execute(
        "SELECT table_oid::bigint AS table_oid, COUNT(*)::bigint AS row_count "
        "FROM organization_purge_rows GROUP BY table_oid"
    ).fetchall()
    counts = {
        tables[int(_get(row, "table_oid", 0))].label: int(_get(row, "row_count", 1))
        for row in rows
    }
    return counts, tables, foreign_keys


def purge_organization(
    connection: psycopg.Connection,
    *,
    organization_id: int,
    confirm_code: str,
) -> dict[str, int]:
    organization = connection.execute(
        "SELECT code FROM organizations WHERE id = %s FOR UPDATE", (organization_id,)
    ).fetchone()
    if organization is None:
        raise LookupError(f"Organization id={organization_id} not found.")
    actual_code = str(_get(organization, "code", 0))
    if confirm_code != actual_code:
        raise ValueError("Confirmation code does not match the selected organization.")

    connection.execute("SELECT pg_advisory_xact_lock(%s)", (8_044_001,))
    counts, tables, foreign_keys = build_purge_plan(connection, organization_id)
    label_to_oid = {table.label: oid for oid, table in tables.items()}
    selected_oids = {label_to_oid[label] for label in counts}
    order = _delete_order(selected_oids, foreign_keys)

    # A nested transaction is a savepoint when the caller already has an active
    # transaction. Any failure restores both deleted rows and trigger state.
    with connection.transaction():
        users = next((table for table in tables.values() if table.name == "users"), None)
        if users is not None:
            connection.execute(
                sql.SQL(
                    "UPDATE {}.{} SET active_profile_id = NULL "
                    "WHERE id IN (SELECT user_id FROM organization_purge_orphan_users)"
                ).format(sql.Identifier(users.schema), sql.Identifier(users.name))
            )
            # UPDATE creates a new row version and therefore a new ctid. Refresh
            # the physical-row selector before executing the deletion plan.
            connection.execute(
                "DELETE FROM organization_purge_rows WHERE table_oid = %s",
                (users.oid,),
            )
            connection.execute(
                sql.SQL(
                    "INSERT INTO organization_purge_rows(table_oid, row_ctid) "
                    "SELECT %s, target.ctid FROM {}.{} target "
                    "JOIN organization_purge_orphan_users candidate ON candidate.user_id = target.id"
                ).format(sql.Identifier(users.schema), sql.Identifier(users.name)),
                (users.oid,),
            )
        disabled: list[TableRef] = []
        for oid in order:
            table = tables[oid]
            connection.execute(
                sql.SQL("ALTER TABLE {}.{} DISABLE TRIGGER USER").format(
                    sql.Identifier(table.schema), sql.Identifier(table.name)
                )
            )
            disabled.append(table)
        for oid in order:
            table = tables[oid]
            connection.execute(
                sql.SQL(
                    "DELETE FROM {}.{} target USING organization_purge_rows selected "
                    "WHERE selected.table_oid = %s AND selected.row_ctid = target.ctid"
                ).format(sql.Identifier(table.schema), sql.Identifier(table.name)),
                (oid,),
            )
        for table in reversed(disabled):
            connection.execute(
                sql.SQL("ALTER TABLE {}.{} ENABLE TRIGGER USER").format(
                    sql.Identifier(table.schema), sql.Identifier(table.name)
                )
            )

        if connection.execute("SELECT 1 FROM organizations WHERE id = %s", (organization_id,)).fetchone():
            raise RuntimeError("Purge verification failed: organization still exists.")
        for oid in _column_tables(connection, "organization_id"):
            table = tables[oid]
            row = connection.execute(
                sql.SQL("SELECT COUNT(*) FROM {}.{} WHERE organization_id = %s").format(
                    sql.Identifier(table.schema), sql.Identifier(table.name)
                ),
                (organization_id,),
            ).fetchone()
            if int(_get(row, "count", 0) or 0):
                raise RuntimeError(f"Purge verification failed: rows remain in {table.label}.")
        if users is not None:
            remaining_users = connection.execute(
                sql.SQL(
                    "SELECT COUNT(*) FROM {}.{} target "
                    "JOIN organization_purge_orphan_users candidate ON candidate.user_id = target.id"
                ).format(sql.Identifier(users.schema), sql.Identifier(users.name))
            ).fetchone()
            if int(_get(remaining_users, "count", 0) or 0):
                raise RuntimeError("Purge verification failed: orphan users remain.")
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or physically purge one organization from a test database."
    )
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--execute", action="store_true", help="Commit destructive purge.")
    parser.add_argument("--confirm-code", help="Exact organization code; required with --execute.")
    parser.add_argument("--backup-reference", help="Backup/snapshot identifier; required with --execute.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = str(os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("Set TEST_DATABASE_URL or DATABASE_URL.")
    try:
        db_name = require_test_database(database_url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.execute and (not args.confirm_code or not str(args.backup_reference or "").strip()):
        raise SystemExit("--execute requires --confirm-code and --backup-reference.")

    with psycopg.connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        if args.execute:
            counts = purge_organization(
                connection,
                organization_id=args.organization_id,
                confirm_code=args.confirm_code,
            )
            connection.commit()
            mode = "PURGED"
        else:
            counts, _, _ = build_purge_plan(connection, args.organization_id)
            connection.rollback()
            mode = "DRY_RUN"

    print(f"mode={mode} database={db_name} organization_id={args.organization_id}")
    for table_name in sorted(counts):
        print(f"{table_name}: {counts[table_name]}")
    print(f"total_rows={sum(counts.values())}")
    if not args.execute:
        print("No data changed. Review the plan, create a backup, then rerun with --execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

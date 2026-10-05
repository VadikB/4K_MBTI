"""Versioned empty-database bootstrap. Existing untracked databases fail closed."""
from hashlib import sha256
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'database/bootstrap/v1/base.sql'


def fingerprint(connection):
    rows = connection.execute("""SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,
        pg_get_expr(d.adbin,d.adrelid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname,a.attnum""").fetchall()
    constraints = connection.execute("""SELECT c.relname,x.conname,pg_get_constraintdef(x.oid)
        FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' ORDER BY c.relname,x.conname""").fetchall()
    indexes=connection.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname").fetchall()
    triggers=connection.execute("""SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid)
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""").fetchall()
    return sha256(repr((rows,constraints,indexes,triggers)).encode()).hexdigest()


def bootstrap_base(connection):
    digest = sha256(BASE.read_bytes()).hexdigest()
    exists=connection.execute("SELECT to_regclass('public.app_bootstrap') AS name").fetchone()['name']
    if exists:
        row=connection.execute('SELECT version,source_hash FROM app_bootstrap').fetchone()
        if not row or row['version']!=1 or row['source_hash']!=digest:
            raise ValueError('BOOTSTRAP_VERSION_MISMATCH')
        return
    tables=connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    if tables:
        raise ValueError('BOOTSTRAP_UNKNOWN_SCHEMA: an empty owned database is required')
    connection.execute(BASE.read_text())
    connection.execute('CREATE TABLE app_bootstrap(version INTEGER PRIMARY KEY,source_hash TEXT NOT NULL,schema_hash TEXT)')
    connection.execute('INSERT INTO app_bootstrap VALUES(1,%s,NULL)',(digest,))


def check_schema(connection):
    import os
    if os.getenv('AGENT4K_ISOLATED_STAND') == '1':
        marker=connection.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()").fetchone()['marker']
        if not marker or marker!=os.getenv('AGENT4K_STAND_MARKER'):
            raise ValueError('STAND_NOT_OWNED')
    row=connection.execute('SELECT source_hash,schema_hash FROM app_bootstrap WHERE version=1').fetchone()
    if not row or row['source_hash']!=sha256(BASE.read_bytes()).hexdigest():
        raise ValueError('BOOTSTRAP_VERSION_MISMATCH')
    if not row['schema_hash'] or row['schema_hash']!=fingerprint(connection):
        raise ValueError('BOOTSTRAP_SCHEMA_MISMATCH')

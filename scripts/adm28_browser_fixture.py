"""Synthetic org-admin inputs for an owned local test stand; no provider calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(state):
    from Api.database import get_connection
    from Api.auth_service import _hash_password
    with get_connection() as connection:
        organization_id = connection.execute("""INSERT INTO organizations(code,name)
            VALUES('adm28_synthetic','Синтетическая организация ADM28') RETURNING id""").fetchone()['id']
        for email, role in [('admin@example.test', 'admin'), ('colleague@example.test', 'member')]:
            user_id = connection.execute('INSERT INTO users(full_name,email,job_description) VALUES(%s,%s,%s) RETURNING id',
                                         ('Синтетический ' + role, email, 'Синтетический специалист')).fetchone()['id']
            connection.execute("""INSERT INTO organization_memberships(
                organization_id,user_id,role,admission_source,admitted_at)
                VALUES(%s,%s,%s,'admin_add',NOW())""", (organization_id, user_id, role))
            salt, digest = _hash_password(state['password'])
            connection.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                               (user_id, email, digest, salt))
            connection.execute("""INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at)
                VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())""", (user_id, email))
        connection.commit()
    print('Synthetic organization/admin/colleague ready; no assessments started')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--isolated-child', action='store_true')
    args = parser.parse_args()
    from scripts.test_stand import environment, owned
    state = json.loads(args.state.read_text())
    with owned(state): pass
    if args.isolated_child:
        if os.getenv('AGENT4K_ISOLATED_STAND') != '1': raise ValueError('ISOLATED_STAND_REQUIRED')
        seed(state)
    else:
        subprocess.run([sys.executable, __file__, '--state', str(args.state), '--isolated-child'],
                       env=environment(state), cwd=ROOT, check=True)

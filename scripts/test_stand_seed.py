"""Synthetic inputs only. No turns, Evidence, IA, Cycle, Results or Report."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from Api.database import get_connection
from Api.auth_service import _hash_password
from Api.assessment_methodology_publication import publish_m2_qa_configuration
from Api.assessment_role_profiles import publish_base_roles,select_role_profile_for_user
from Api.assessment_contexts import (create_organization_context_draft,publish_organization_context,
    create_user_context_draft,confirm_user_context,create_personalized_profile)
from Api.m5_storage import import_package
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import publish_catalog
from Api.assessment_authoring_service import assessment_authoring_service
from Api.organization_invitation_service import hash_invitation_token

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT/path).read_text())


def seed(state):
    qa_mode=state.get('qa_orchestration') is True
    with get_connection() as c:
        if c.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone():
            print('synthetic seed already present; no data changed');return
        org=c.execute("""INSERT INTO organizations(code,name,invitation_intro)
            VALUES('e102_synthetic','Синтетическая организация E10.2','Техническое приглашение из изолированного стенда')
            RETURNING id""").fetchone()['id']
        if state.get('browser_scenario') == 'acceptance-v1':
            invitation_token='browser-invitation-'+state['run_id']
            c.execute("""INSERT INTO organization_invitations(organization_id,token_hash,expires_at)
                VALUES(%s,%s,%s)""",(org,hash_invitation_token(invitation_token),datetime.now()+timedelta(days=30)))
            other_org=c.execute("INSERT INTO organizations(code,name) VALUES('e102_other','Другая синтетическая организация') RETURNING id").fetchone()['id']
            other_user=c.execute("INSERT INTO users(full_name,email) VALUES('Участник другой организации','member-b@example.test') RETURNING id").fetchone()['id']
            c.execute("""INSERT INTO organization_memberships(
                organization_id,user_id,role,admission_source,admitted_at
            ) VALUES(%s,%s,'member','admin_add',NOW())""",(other_org,other_user))
        from Api.assessment_configuration import load_default_methodology_roles,ensure_methodology_role_projection
        legacy_roles=load_default_methodology_roles(c)
        ensure_methodology_role_projection(c,{'roles':legacy_roles})
        legacy_role=c.execute('SELECT id FROM roles WHERE code=%s',(legacy_roles[0]['code'],)).fetchone()['id']
        users=[]
        for i,email in enumerate(['participant@example.test','other@example.test']):
            uid=c.execute('INSERT INTO users(full_name,email) VALUES(%s,%s) RETURNING id',('Синтетический участник '+str(i+1),email)).fetchone()['id']
            users.append(uid)
            profile=c.execute("""INSERT INTO user_role_profiles(user_id,role_id,raw_position,raw_duties,normalized_duties)
                VALUES(%s,%s,'Синтетический специалист','Проверять технические примеры','Проверять технические примеры') RETURNING id""",(uid,legacy_role)).fetchone()['id']
            c.execute("""UPDATE users SET role_id=%s,active_profile_id=%s,job_description='Синтетический специалист',
                company_industry='Техническая проверка',personal_data_consent_accepted_at=NOW(),
                personal_data_consent_version=1,personal_data_consent_text='Synthetic fixture; not a real consent',
                telegram='@synthetic_e102' WHERE id=%s""",(legacy_role,profile,uid))
            c.execute("""INSERT INTO organization_memberships(
                organization_id,user_id,role,admission_source,admitted_at
            ) VALUES(%s,%s,'member','csv_import',NOW())""",(org,uid))
            salt,digest=_hash_password(state['password'])
            c.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',(uid,email,digest,salt))
            c.execute("INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at) VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())",(uid,email))
        admin_email = 'superadmin@example.test'
        admin_id = c.execute(
            "INSERT INTO users(full_name,email) VALUES('Синтетический суперадминистратор',%s) RETURNING id",
            (admin_email,),
        ).fetchone()['id']
        salt,digest=_hash_password(state['password'])
        c.execute('INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt) VALUES(%s,%s,%s,%s)',
                  (admin_id,admin_email,digest,salt))
        c.execute("INSERT INTO user_identities(user_id,provider,email,is_primary,is_verified,verified_at) VALUES(%s,'email_magic_link',%s,TRUE,TRUE,NOW())",
                  (admin_id,admin_email))
        basis='E10.2 synthetic disposable fixture; technical admission only, not normative approval/GC'
        publication=publish_m2_qa_configuration(c,published_by_user_id=users[0],decision_basis=basis)
        roles=publish_base_roles(c,package=read('assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json'),
            manifest=read('assessment_definitions/role_profiles/competencies_4k/1.1/manifest.json'),published_by_user_id=users[0],decision_basis=basis)
        cases=read('assessment_definitions/cases/competencies_4k/1.1/case-package.json')
        role_code=cases['cases'][3 if state.get('browser_case')=='character' else 0]['base_role']
        role=c.execute('SELECT v.id FROM assessment_role_profile_versions v JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code=%s',(role_code,)).fetchone()['id']
        definition={'name':'Синтетическая организация','organization_type':'компания','industry':'образование',
            'activity_description':'Техническая проверка','case_reality_level':'обобщённый','organization_name_usage_rules':'не использовать название'}
        org_version=create_organization_context_draft(c,organization_id=org,definition=definition,source_manifest={'fixture':'E10.2'})
        publish_organization_context(c,version_id=org_version,confirmed_by_user_id=users[0])
        # Same isolated fixture lifecycle as test_m10_product_path_db; repository package stays WORKING.
        admitted=([read('tests/browser/fixtures/sources/character-case-v1.json')] if state.get('browser_case')=='character' else [cases['cases'][0],cases['cases'][2]])
        if state.get('browser_catalog') == 'unavailable':
            admitted = []  # Preserve WORKING status and absent admission; no runtime outputs are seeded.
        for case in admitted:case['status']='FROZEN'
        manifest=read('assessment_definitions/cases/competencies_4k/1.1/manifest.json')
        import_package(c,package=cases,manifest=manifest,execution_rules=read('assessment_definitions/cases/competencies_4k/1.1/execution-rules.json'))
        if state.get('browser_case')=='character':
            import_package(c,package={**cases,'cases':admitted},manifest=read('tests/browser/fixtures/character-manifest.json'),
                           execution_rules=read('assessment_definitions/cases/competencies_4k/1.1/execution-rules.json'))
        for case in admitted:
            case_row=c.execute('SELECT * FROM m5_case_versions WHERE case_id=%s',(case['case_id'],)).fetchone();cid=case_row['id']
            for scope in ('case_format','case_dialogue','assessment_situation'):
                evidence={'schema_version':1,'eligibility':'user_admission','scope':scope,'result':'PASS',
                    'case_ref':{'id':case_row['case_id'],'version':case_row['case_version'],'checksum':case_row['content_checksum']},
                    'base_role':case_row['base_role'],'usage_scopes':['qa'] if qa_mode else ['assessment'],
                    'origin':{'type':'fixture' if qa_mode else 'human_review','actor_ref':'controlled-test:E10.2'}}
                c.execute("INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum) VALUES(%s,%s,'PASS',%s::jsonb,%s)",(cid,scope,json.dumps(evidence),checksum(evidence)))
        package_row=c.execute("SELECT id FROM m5_packages ORDER BY id DESC LIMIT 1").fetchone()
        catalog=publish_catalog(c,catalog_id='e102-controlled',catalog_version='1.0',package_db_id=package_row['id'],
            case_version_ids=[row['id'] for row in c.execute("SELECT id FROM m5_case_versions WHERE status='FROZEN' ORDER BY id").fetchall()],
            usage_scope='qa' if qa_mode else 'assessment',organization_id=org,published_by=users[0],decision_basis=basis,
            idempotency_key='e102-controlled-catalog')
        base_config=c.execute('SELECT * FROM assessment_configurations WHERE id=%s',(publication['configuration_id'],)).fetchone()
        runtime_config=assessment_authoring_service.create_configuration(c,code='e102_controlled_catalog',name='E10.2 controlled catalog',
            methodology_version_id=base_config['methodology_version_id'],scenario_version_id=base_config['scenario_version_id'],
            catalog_version_id=catalog['catalog_db_id'],actor_user_id=users[0],comment=basis)
        runtime_config=assessment_authoring_service.publish_configuration(c,configuration_id=runtime_config['id'],make_default=False,
            actor_user_id=users[0],comment=basis)
        for uid in users:
            if state.get('browser_profile') == 'unprepared' and uid == users[0]:
                continue
            select_role_profile_for_user(c,user_id=uid,version_id=role)
            version=create_user_context_draft(c,user_id=uid,identity={'full_name':'Синтетический участник'},professional={'position_or_status':'Технический участник'})
            confirm_user_context(c,version_id=version,user_id=uid)
            create_personalized_profile(c,user_id=uid,assessment_configuration_id=runtime_config['id'],
                organization_context_version_id=org_version,role_profile_version_id=role,user_context_version_id=version)
        c.commit()
    print('Synthetic input seed ready; no assessment results created')

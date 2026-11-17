"""Owner-scoped history semantics: Cycle count, Results revisions, presentation revisions."""
from uuid import uuid4
import psycopg
import pytest
from psycopg.rows import dict_row
from Api.m8_results import list_owned_reports

pytestmark = pytest.mark.integration


def test_history_groups_cycles_and_preserves_all_saved_versions(test_database_url):
    with psycopg.connect(test_database_url,row_factory=dict_row) as c:
        schema='review_history_pytest_'+uuid4().hex
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        c.execute(psycopg.sql.SQL('SET LOCAL search_path TO {}').format(psycopg.sql.Identifier(schema)))
        c.execute('CREATE TABLE m5_cycles(id BIGINT PRIMARY KEY,cycle_id UUID,owner_user_id BIGINT,usage_scope TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
        c.execute("ALTER TABLE m5_cycles ADD COLUMN organization_id BIGINT DEFAULT 1, ADD COLUMN status TEXT DEFAULT 'calculated', ADD COLUMN started_at TIMESTAMPTZ, ADD COLUMN collection_closed_at TIMESTAMPTZ DEFAULT NOW()")
        c.execute('ALTER TABLE m5_cycles ADD COLUMN personalized_profile_id BIGINT')
        c.execute('ALTER TABLE m5_cycles ADD COLUMN display_snapshot_json JSONB')
        c.execute('CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY,assessment_configuration_id BIGINT)')
        c.execute('CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,name TEXT)')
        c.execute("INSERT INTO assessment_configurations VALUES(1,'Синтетическая программа')")
        c.execute('INSERT INTO assessment_personalized_profiles VALUES(1,1)')
        c.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN)')
        c.execute('CREATE TABLE organization_memberships(user_id BIGINT,organization_id BIGINT)')
        c.execute('INSERT INTO organizations VALUES(1,TRUE)')
        c.execute('INSERT INTO organization_memberships VALUES(91,1),(92,1)')
        c.execute('CREATE TABLE m10_pipeline_runs(cycle_db_id BIGINT,status TEXT,stage TEXT)')
        c.execute('CREATE TABLE m8_results(id UUID PRIMARY KEY,cycle_db_id BIGINT)')
        c.execute('CREATE TABLE m8_result_revisions(id UUID PRIMARY KEY,results_id UUID,revision_no INTEGER)')
        c.execute("CREATE TABLE m8_reports(id UUID PRIMARY KEY,result_revision_id UUID,revision_no INTEGER,audience TEXT,c67_json JSONB DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ DEFAULT NOW())")
        c.execute('CREATE TABLE m8_published_reports(cycle_db_id BIGINT PRIMARY KEY,report_id UUID)')
        expected={}
        for cycle_db_id,owner,scope in [(1,91,'assessment'),(2,91,'assessment'),(3,92,'assessment'),(4,91,'qa')]:
            cycle,results,rr=uuid4(),uuid4(),uuid4()
            c.execute('INSERT INTO m5_cycles(id,cycle_id,owner_user_id,usage_scope) VALUES(%s,%s,%s,%s)',(cycle_db_id,cycle,owner,scope))
            c.execute("UPDATE m5_cycles SET personalized_profile_id=1, display_snapshot_json=jsonb_build_object('program_name',%s::text) WHERE id=%s",
                      (f'Программа {cycle_db_id}',cycle_db_id))
            c.execute('INSERT INTO m8_results VALUES(%s,%s)',(results,cycle_db_id))
            c.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,1)',(rr,results))
            reports=[]
            for revision in (1,2):
                report=uuid4();reports.append(str(report))
                c.execute("INSERT INTO m8_reports(id,result_revision_id,revision_no,audience) VALUES(%s,%s,%s,'assessee')",(report,rr,revision))
            c.execute("INSERT INTO m8_reports(id,result_revision_id,revision_no,audience) VALUES(%s,%s,3,'organization')",(uuid4(),rr))
            if cycle_db_id==1:
                new_rr,new_report=uuid4(),uuid4()
                c.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,2)',(new_rr,results))
                c.execute("INSERT INTO m8_reports(id,result_revision_id,revision_no,audience) VALUES(%s,%s,1,'assessee')",(new_report,new_rr))
                reports.append(str(new_report))
            expected[str(cycle)]=list(reversed(reports))
        history=list_owned_reports(c,91)
        assert len(history)==2
        for item in history:
            assert [v['report_id'] for v in item['versions']]==expected[item['cycle_id']]
            assert item['report_id']==item['versions'][0]['report_id']
            assert item['program_name'] in {'Программа 1','Программа 2'}
        assert len(list_owned_reports(c,92))==1
        assert list_owned_reports(c,999)==[]
        c.rollback()

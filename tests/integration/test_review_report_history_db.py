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
        c.execute('CREATE TABLE m8_results(id UUID PRIMARY KEY,cycle_db_id BIGINT)')
        c.execute('CREATE TABLE m8_result_revisions(id UUID PRIMARY KEY,results_id UUID,revision_no INTEGER)')
        c.execute('CREATE TABLE m8_reports(id UUID PRIMARY KEY,result_revision_id UUID,revision_no INTEGER,audience TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
        expected={}
        for cycle_db_id,owner,scope in [(1,91,'assessment'),(2,91,'assessment'),(3,92,'assessment'),(4,91,'qa')]:
            cycle,results,rr=uuid4(),uuid4(),uuid4()
            c.execute('INSERT INTO m5_cycles(id,cycle_id,owner_user_id,usage_scope) VALUES(%s,%s,%s,%s)',(cycle_db_id,cycle,owner,scope))
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
        assert len(list_owned_reports(c,92))==1
        assert list_owned_reports(c,999)==[]
        c.rollback()

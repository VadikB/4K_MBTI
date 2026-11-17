from datetime import datetime, timedelta, timezone
import pytest
from Api.preparation_observation import project, reference

NOW = datetime(2026,11,16,12,tzinfo=timezone.utc)

@pytest.mark.parametrize('kind', ['assessment','next','report'])
@pytest.mark.parametrize('status,heartbeat,delayed', [('queued',None,True), ('running',NOW,True),
    ('running',NOW-timedelta(minutes=10),True), ('failed',NOW,False), ('completed',NOW,False)])
def test_saved_times_freshness_terminal_priority_and_safe_projection(kind,status,heartbeat,delayed):
    op = {'operation_id':'safe-operation','status':status,'created_at':NOW-timedelta(minutes=30),
          'error_message':'private sql model prompt', 'user_id':99}
    observed = {'kind':kind,'stage':'checking','stage_started_at':NOW-timedelta(minutes=27),
                'heartbeat_at':heartbeat, 'attempt_token':'secret-internal'}
    result = project(op, observed, now=NOW)
    assert result['delayed'] is delayed
    assert result['started_at'] == op['created_at'].isoformat()
    assert result['stage_started_at'] == observed['stage_started_at'].isoformat() or status == 'queued'
    assert result['reference'] == reference('cycle','safe-operation')
    assert all(x not in str(result) for x in ['private sql','secret-internal','user_id','attempt_token'])
    if status == 'running':
        assert result['freshness'] == ('confirmed' if heartbeat == NOW else 'unconfirmed')


def test_legacy_unknown_is_honest_and_read_does_not_change_progress(monkeypatch):
    op={'operation_id':'legacy','status':'running','created_at':NOW-timedelta(minutes=30)}
    first=project(op,now=NOW)
    second=project(op,now=NOW+timedelta(minutes=1))
    assert first['last_progress_at'] is None
    assert 'недоступны' in first['explanation']
    assert first['started_at']==second['started_at']
    assert first['reference']==second['reference']
    assert first['read_at']!=second['read_at']
    monkeypatch.setattr('Api.preparation_observation.settings.preparation_delay_notice_seconds',999)
    assert project(op,now=NOW)['delay_notice_seconds']==300

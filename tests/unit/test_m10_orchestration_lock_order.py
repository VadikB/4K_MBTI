from Api import m10_orchestration
from uuid import uuid4


class _NoCandidateResult:
    def fetchone(self):
        return None


class _RecordingConnection:
    def __init__(self):
        self.queries = []

    def execute(self, query, _params=None):
        self.queries.append(" ".join(str(query).split()))
        return _NoCandidateResult()


def test_product_queue_claims_cycle_before_assessment_situation():
    connection = _RecordingConnection()

    assert m10_orchestration._queue_outbox(connection) is False
    assert m10_orchestration._queue_assessment(connection) is False
    assert m10_orchestration._clarify_interim(connection, gateway=object()) is False

    assert [query.rsplit(" ORDER BY ", 1)[1] for query in connection.queries] == [
        "o.created_at FOR UPDATE OF c SKIP LOCKED LIMIT 1",
        "a.created_at FOR UPDATE OF c SKIP LOCKED LIMIT 1",
        "c.created_at FOR UPDATE OF cy SKIP LOCKED LIMIT 1",
    ]


def test_concurrent_clarification_fence_is_retried_without_publishing_late_output(monkeypatch):
    row = {'id': uuid4(), 'as_db_id': 3, 'cycle_db_id': 4, 'created_by': 5}

    class Result:
        def fetchone(self):
            return row

    class Connection:
        def execute(self, *_args, **_kwargs):
            return Result()
        def commit(self):
            return None

    def fenced(**_kwargs):
        raise ValueError('M7_CLARIFICATION_STATE_CHANGED')

    monkeypatch.setattr(m10_orchestration.m7_clarification, 'decide_detached', fenced)
    assert m10_orchestration._clarify_interim(Connection(), gateway=object(),
                                               connection_factory=object()) is True

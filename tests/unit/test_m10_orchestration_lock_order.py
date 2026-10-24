from Api import m10_orchestration


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

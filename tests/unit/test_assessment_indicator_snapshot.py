import pytest

from Api.assessment_service import freeze_session_case_indicators


class SnapshotConnection:
    def __init__(self, count: int):
        self.count = count
        self.calls = []

    def execute(self, statement, params):
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))

        class Result:
            def __init__(self, count):
                self.count = count

            def fetchone(self):
                return {"count": self.count}

        return Result(self.count)


@pytest.mark.unit
def test_freeze_session_case_indicators_uses_versioned_frozen_scope() -> None:
    connection = SnapshotConnection(count=2)

    count = freeze_session_case_indicators(
        connection,
        session_case_id=31,
        case_registry_id=41,
        methodology_version_id=2,
        indicator_codes=["K1.I02", "K1.I01", "K1.I01", ""],
    )

    assert count == 2
    assert "FROM case_registry_indicators" in connection.calls[0][0]
    assert connection.calls[0][1] == (31, 41, 2, ["K1.I01", "K1.I02"])
    assert connection.calls[1][1] == (31, 2)


@pytest.mark.unit
def test_freeze_session_case_indicators_rejects_missing_case_mapping() -> None:
    with pytest.raises(ValueError, match="has no Indicator mappings"):
        freeze_session_case_indicators(
            SnapshotConnection(count=0),
            session_case_id=31,
            case_registry_id=41,
            methodology_version_id=2,
            indicator_codes=["K1.I01"],
        )


@pytest.mark.unit
def test_freeze_session_case_indicators_rejects_empty_scope_before_sql() -> None:
    connection = SnapshotConnection(count=0)
    with pytest.raises(ValueError, match="non-empty frozen indicator scope"):
        freeze_session_case_indicators(
            connection,
            session_case_id=31,
            case_registry_id=41,
            methodology_version_id=2,
            indicator_codes=[],
        )
    assert connection.calls == []

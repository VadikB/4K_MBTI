from Api.integration_identity_service import resolve_or_provision_participant


class Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class Connection:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, query, parameters):
        self.calls.append((query, parameters))
        return Result(next(self.results))


def test_existing_email_is_resolved_without_profile_mutation() -> None:
    connection = Connection([{"id": 17}])

    result = resolve_or_provision_participant(
        connection,
        email=" Student@Example.EDU ",
        display_name="Новое имя не должно заменить существующее",
    )

    assert result.agent4k_user_id == 17
    assert result.created is False
    assert len(connection.calls) == 1
    assert connection.calls[0][1] == ("student@example.edu",)


def test_missing_email_provisions_user_without_role_or_profile() -> None:
    connection = Connection([None, {"id": 23}])

    result = resolve_or_provision_participant(
        connection,
        email="student@example.edu",
        display_name=" Студент ",
    )

    assert result.agent4k_user_id == 23
    assert result.created is True
    assert "INSERT INTO users" in connection.calls[1][0]
    assert connection.calls[1][1] == ("Студент", "student@example.edu")

from __future__ import annotations

import pytest

from Api import database


class FakeConnection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.commits = 0
        self.rollbacks = 0
        self.executed: list[tuple] = []

    def execute(self, *args, **kwargs):
        self.executed.append(args)
        return {"connection": self.name, "args": args}

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeLease:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.exits: list[tuple] = []

    def __enter__(self) -> FakeConnection:
        return self.connection

    def __exit__(self, *args) -> bool:
        self.exits.append(args)
        return False


class FakePool:
    def __init__(self) -> None:
        self.connections: list[FakeConnection] = []
        self.leases: list[FakeLease] = []

    def connection(self, **_kwargs) -> FakeLease:
        connection = FakeConnection(f"connection-{len(self.connections) + 1}")
        lease = FakeLease(connection)
        self.connections.append(connection)
        self.leases.append(lease)
        return lease


@pytest.mark.unit
def test_pause_returns_lease_and_next_sql_reacquires(monkeypatch) -> None:
    pool = FakePool()
    monkeypatch.setattr(database, "_connection_pool", pool)

    with database.get_connection() as connection:
        first_result = connection.execute("SELECT 1")
        connection.pause()
        second_result = connection.execute("SELECT 2")

    assert first_result["connection"] == "connection-1"
    assert second_result["connection"] == "connection-2"
    assert pool.connections[0].commits == 1
    assert len(pool.leases[0].exits) == 1
    assert len(pool.leases[1].exits) == 1


@pytest.mark.unit
def test_external_io_pauses_every_active_connection(monkeypatch) -> None:
    pool = FakePool()
    monkeypatch.setattr(database, "_connection_pool", pool)

    with database.get_connection():
        with database.get_connection():
            assert database.pause_thread_connections_for_external_io() == 2
            assert all(connection.commits == 1 for connection in pool.connections)
            assert database.pause_thread_connections_for_external_io() == 0

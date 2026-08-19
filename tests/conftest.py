from __future__ import annotations

import os

import pytest

# Importing Api.database creates the pool object. Unit tests keep it fully lazy
# and must never connect to the developer or production database.
os.environ["DB_POOL_MIN_SIZE"] = "0"


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that require TEST_DATABASE_URL",
    )


def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="use --run-integration with an isolated TEST_DATABASE_URL")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def test_database_url() -> str:
    url = str(os.getenv("TEST_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(url)
    database_name = str(params.get("dbname") or "").lower()
    if "test" not in database_name and "pytest" not in database_name:
        pytest.fail(
            "Integration tests refuse to use this database: "
            "TEST_DATABASE_URL dbname must contain 'test' or 'pytest'."
        )
    production_name = str(os.getenv("DB_NAME") or "").strip().lower()
    if production_name and database_name == production_name:
        pytest.fail("TEST_DATABASE_URL must not point to DB_NAME.")
    return url

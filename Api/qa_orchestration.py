"""Server-owned switch for synthetic QA orchestration on a disposable stand."""
from __future__ import annotations

import os


def enabled() -> bool:
    database = os.getenv("DB_NAME", "")
    return (
        os.getenv("AGENT4K_ISOLATED_STAND") == "1"
        and os.getenv("AGENT4K_BROWSER_TEST_GATEWAY") == "1"
        and os.getenv("AGENT4K_QA_ORCHESTRATION") == "1"
        and os.getenv("AGENT4K_BROWSER_SCENARIO") == "acceptance-v1"
        and os.getenv("AGENT4K_STAND_MARKER", "").startswith("stand-10.2:")
        and (database.startswith("product4k_pytest_") or database.startswith("agent4k_pytest_"))
    )


def usage_scope() -> str:
    return "qa" if enabled() else "assessment"


def permits(scope: str) -> bool:
    return scope == "assessment" or (scope == "qa" and enabled())


def sql_scope(alias: str) -> str:
    return f"{alias}.usage_scope='qa'" if enabled() else f"{alias}.usage_scope='assessment'"

from Api import qa_orchestration


VARIABLES = {
    "AGENT4K_ISOLATED_STAND": "1",
    "AGENT4K_BROWSER_TEST_GATEWAY": "1",
    "AGENT4K_QA_ORCHESTRATION": "1",
    "AGENT4K_BROWSER_SCENARIO": "acceptance-v1",
    "AGENT4K_STAND_MARKER": "stand-10.2:owned",
    "DB_NAME": "product4k_pytest_owned",
}


def test_qa_scope_requires_all_server_owned_disposable_stand_guards(monkeypatch):
    for name, value in VARIABLES.items():
        monkeypatch.setenv(name, value)
    assert qa_orchestration.enabled()
    assert qa_orchestration.usage_scope() == "qa"
    assert qa_orchestration.permits("qa")
    for name in VARIABLES:
        with monkeypatch.context() as isolated:
            for key, value in VARIABLES.items():
                isolated.setenv(key, value)
            isolated.delenv(name)
            assert not qa_orchestration.enabled(), name
            assert qa_orchestration.usage_scope() == "assessment"
            assert not qa_orchestration.permits("qa")


def test_production_database_cannot_enable_qa_scope(monkeypatch):
    for name, value in VARIABLES.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DB_NAME", "product4k")
    assert not qa_orchestration.enabled()
    assert qa_orchestration.permits("assessment")
    assert not qa_orchestration.permits("qa")

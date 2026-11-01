from Api import m7_completion_worker


def test_completion_sweep_interval_stays_production_safe(monkeypatch):
    monkeypatch.delenv("AGENT4K_ISOLATED_STAND", raising=False)
    monkeypatch.setenv("M7_COMPLETION_SWEEP_SECONDS", "1")
    assert m7_completion_worker._sweep_interval_seconds() == 30.0


def test_completion_sweep_interval_can_shorten_owned_stand(monkeypatch):
    monkeypatch.setenv("AGENT4K_ISOLATED_STAND", "1")
    monkeypatch.setenv("M7_COMPLETION_SWEEP_SECONDS", "2")
    assert m7_completion_worker._sweep_interval_seconds() == 2.0


def test_completion_sweep_interval_rejects_unsafe_values(monkeypatch):
    monkeypatch.setenv("AGENT4K_ISOLATED_STAND", "1")
    for value in ("invalid", "0", "31"):
        monkeypatch.setenv("M7_COMPLETION_SWEEP_SECONDS", value)
        assert m7_completion_worker._sweep_interval_seconds() == 30.0

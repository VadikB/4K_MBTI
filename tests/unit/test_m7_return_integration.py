from datetime import datetime,timedelta,timezone

from Api import m7_return_integration
from Api.m7_return_integration import load_policy, policy_snapshot_for_plan


class _StaleLeaseConnection:
    def __init__(self, started_at):
        self.started_at=started_at
        self.statements=[]

    def execute(self, statement, parameters=None):
        self.statements.append((statement,parameters))
        if "SELECT started_at FROM m5_cycle_time_intervals" in statement:
            return _OneRow({"started_at":self.started_at})
        raise AssertionError("stale lease must not mutate the current collecting interval")


class _OneRow:
    def __init__(self, row):self.row=row
    def fetchone(self):return self.row


def test_p03_policy_is_qa_only_and_keeps_exact_threshold():
    policy = load_policy()
    assert policy["status"] == "draft"
    assert policy["usage_scope"] == "qa"
    assert policy["replacement_threshold_seconds"] == 180
    assert policy["presence_lease_seconds"] == 120
    assert policy["heartbeat_interval_seconds"] == 10
    assert policy["max_successful_replacements_per_position"] == 3
    assert policy["production_activation"] == "blocked_by_methodology_and_provider_admission"


def test_sales_r1_policy_is_published_and_keeps_same_as_after_any_break():
    policy = load_policy(usage_scope="assessment")
    assert policy["status"] == "published"
    assert policy["usage_scope"] == "assessment"
    assert policy["algorithm"] == "m7-return-r1"
    assert policy["resume_mode"] == "same_assessment_situation"
    assert policy["replacement_policy"] == "not_applicable"
    assert policy["presence_lease_seconds"] == 120
    assert policy["heartbeat_interval_seconds"] == 10
    snapshot = policy_snapshot_for_plan(usage_scope="assessment")
    assert snapshot["content"] == policy
    assert snapshot["checksum"]


def test_stale_presence_lease_cannot_close_newer_collecting_interval(monkeypatch):
    started_at=datetime.now(timezone.utc)
    connection=_StaleLeaseConnection(started_at)
    monkeypatch.setattr(m7_return_integration,"_saved_policy",lambda *_:{"id":"p","version":"1"})
    result=m7_return_integration._recognize_presence_absence(connection,
        cycle={"id":7},session={"id":8},position={"id":9},situation={"id":10},
        recognized_at=started_at-timedelta(seconds=120),source_ref="stale-lease")
    assert result=={}
    assert len(connection.statements)==1

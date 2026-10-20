from Api.m7_return_integration import load_policy, policy_snapshot_for_plan


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

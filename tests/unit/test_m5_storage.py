from Api.m5_storage import _frozen_cycle_base_role, resolve_legacy_base_role


def test_resolve_legacy_base_role_uses_profile_code_first() -> None:
    assert resolve_legacy_base_role("leader", "manager") == "direction_system_leader"


def test_resolve_legacy_base_role_falls_back_to_platform_role() -> None:
    assert resolve_legacy_base_role(None, "leader", "Лидер") == "direction_system_leader"


def test_resolve_legacy_base_role_supports_legacy_linear_codes_and_names() -> None:
    assert resolve_legacy_base_role("linear_employee") == "specialist_expert"
    assert resolve_legacy_base_role(None, None, "Линейный   сотрудник") == "specialist_expert"


def test_resolve_legacy_base_role_preserves_m3_base_role_code() -> None:
    assert resolve_legacy_base_role("project_product_process_manager") == "project_product_process_manager"


def test_resolve_legacy_base_role_rejects_unknown_value() -> None:
    assert resolve_legacy_base_role("unknown") == ""


def test_frozen_cycle_base_role_wins_over_changed_organization_profile() -> None:
    selected = {"id": "41", "version": "1.0", "checksum": "a" * 64,
                "code": "project_product_process_manager"}
    changed_profile = {"role_profile": {"code": "organization-director-v2"}}
    assert _frozen_cycle_base_role(selected, changed_profile) == "project_product_process_manager"


def test_frozen_cycle_base_role_preserves_legacy_text_ref() -> None:
    assert _frozen_cycle_base_role(
        {"id": "team_lead", "version": "0", "checksum": "legacy"},
        {"role_profile": {"code": "changed"}},
    ) == "team_lead"


def test_frozen_cycle_numeric_ref_uses_resolved_published_base_role() -> None:
    assert _frozen_cycle_base_role(
        {"id": "41", "version": "1", "checksum": "a" * 64},
        {"role_profile": {"code": "changed-organization-role"}},
        "specialist_expert",
    ) == "specialist_expert"

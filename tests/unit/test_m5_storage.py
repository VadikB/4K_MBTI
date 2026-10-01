from Api.m5_storage import resolve_legacy_base_role


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

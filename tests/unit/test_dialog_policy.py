from Api.assessment.interview import DialogPolicy


def test_dialog_mode_is_explicitly_detected() -> None:
    policy = DialogPolicy()

    assert policy.is_dialog_mode("Ролевой диалог") is True
    assert policy.is_dialog_mode("structured interview") is False
    assert policy.is_dialog_mode(None) is False


def test_unknown_role_uses_generic_contract() -> None:
    policy = DialogPolicy()

    assert policy.role_contract("unknown") == policy.role_contract("generic")
    assert "не как интервью-бот" in policy.role_contract("unknown")


def test_meta_response_detection_preserves_runtime_guards() -> None:
    policy = DialogPolicy()

    assert policy.looks_like_meta_response("") is True
    assert policy.looks_like_meta_response("Пользователь ответил достаточно подробно") is True
    assert policy.looks_like_meta_response("Когда вы сможете прислать статус?") is False


def test_domain_drift_matches_comma_separated_terms_case_insensitively() -> None:
    policy = DialogPolicy()

    assert policy.looks_like_domain_drift("Обсудим Service Desk", "кандидаты, service desk") is True
    assert policy.looks_like_domain_drift("Обсудим срок договора", "кандидаты, service desk") is False
    assert policy.looks_like_domain_drift("", "service desk") is False

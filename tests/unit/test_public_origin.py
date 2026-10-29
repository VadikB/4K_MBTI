from __future__ import annotations

import pytest

from Api.public_origin import build_public_link, validate_public_origin
from Api.public_origin import read_deployment_origin
from scripts.configure_public_origin import configure


def test_public_origin_is_explicit_and_tokens_are_encoded_without_host_input():
    assert build_public_link("https://example.com/", {"auth_action": "password_reset", "token": "a/+?& b"},
                             mode="public") == "https://example.com/?auth_action=password_reset&token=a%2F%2B%3F%26%20b"


@pytest.mark.parametrize("value", [
    "http://example.com", "https://178.236.26.203:8002", "http://127.0.0.1:8002",
    "https://localhost", "https://sub.localhost", "https://[::1]", "https://2130706433",
    "https://name:password@example.com", "https://example.com/app", "https://example.com?token=x",
    "https://example.com/#fragment", "//example.com", "https://example.com\n", "", None, 1,
    "https://" + "a" * 64 + ".example.com",
])
def test_public_mode_rejects_nonpublic_or_nonorigin_configuration(value):
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        validate_public_origin(value, mode="public")


def test_explicit_local_mode_preserves_local_development():
    assert validate_public_origin("http://127.0.0.1:18000/", mode="local") == "http://127.0.0.1:18000"
    with pytest.raises(ValueError, match="APP_ORIGIN_MODE"):
        validate_public_origin("https://example.com", mode="unknown")


def test_each_delivery_uses_current_configuration_not_a_cached_link():
    query = {"invite": "synthetic-token"}
    assert build_public_link("https://old.example.com", query, mode="public").startswith("https://old.example.com/")
    assert build_public_link("https://new.example.com", query, mode="public").startswith("https://new.example.com/")


def test_deployment_configuration_never_rewrites_or_reads_secret_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("APP_BASE_URL=http://127.0.0.1:8002\nSYNTHETIC_SECRET=not-a-real-key\n")
    before = dotenv.read_bytes()
    assert read_deployment_origin(tmp_path) is None
    configure(tmp_path, "https://test.example.com/")
    assert read_deployment_origin(tmp_path) == "https://test.example.com"
    assert dotenv.read_bytes() == before
    configure(tmp_path, "https://next.example.com")
    assert read_deployment_origin(tmp_path) == "https://next.example.com"
    assert dotenv.read_bytes() == before


def test_unknown_or_invalid_deployment_origin_is_not_silently_ignored(tmp_path):
    (tmp_path / ".public-origin.json").write_text('{"schema_version":1,"mode":"public","origin":"http://127.0.0.1"}')
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        read_deployment_origin(tmp_path)
    (tmp_path / ".public-origin.json").write_text('{"origin":"https://example.com","unexpected":"x"}')
    with pytest.raises(ValueError, match="schema"):
        read_deployment_origin(tmp_path)

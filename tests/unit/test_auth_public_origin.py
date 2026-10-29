"""Controlled delivery sink: real auth URL builders, no DB/provider access."""
from contextlib import contextmanager
from urllib.parse import parse_qs, urlsplit

import pytest

from Api import auth_service as auth


class Connection:
    def execute(self, query, params=None):
        self.query = query
        return self

    def fetchone(self):
        if "COUNT(*) AS request_count" in self.query:
            return {"request_count": 0}
        if "auth_password_credentials" in self.query:
            return {"id": 1}
        return None

    def commit(self):
        pass


@pytest.fixture
def delivery(monkeypatch):
    sink = []
    service = auth.AuthService()
    monkeypatch.setattr(service, "ensure_schema", lambda: None)
    monkeypatch.setattr(service, "_ensure_email_can_authenticate", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_enforce_magic_link_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth.settings, "app_base_url", "https://test.example.com")
    monkeypatch.setattr(auth.settings, "app_origin_mode", "public")
    monkeypatch.setattr(auth.settings, "auth_magic_link_dev_mode", False)
    monkeypatch.setattr(auth.settings, "email_provider", "controlled-sink")
    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda *args: "synthetic/+?& token")
    monkeypatch.setattr(auth, "send_auth_action_email", lambda **kwargs: sink.append(kwargs))
    monkeypatch.setattr(auth, "send_magic_link_email", lambda **kwargs: sink.append(kwargs))

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(auth, "get_connection", connection)
    return service, sink


@pytest.mark.parametrize("purpose", ["email_verification", "password_reset", "magic"])
def test_delivered_auth_urls_use_current_trusted_origin_and_preserve_purpose(delivery, monkeypatch, purpose):
    service, sink = delivery
    for origin in ("https://test.example.com", "https://next.example.com"):
        monkeypatch.setattr(auth.settings, "app_base_url", origin)
        if purpose == "magic":
            result = service.create_magic_link_request(email="synthetic@example.test")
            url = sink[-1]["login_url"]
        else:
            result = service.create_auth_action_request(email="synthetic@example.test", purpose=purpose)
            url = sink[-1]["action_url"]
        parsed = urlsplit(url)
        assert parsed.scheme + "://" + parsed.netloc == origin
        query = parse_qs(parsed.query)
        assert query["token"] == ["synthetic/+?& token"]
        assert query.get("auth_action") == (None if purpose == "magic" else [purpose])
        assert result.expires_at is not None
    assert len(sink) == 2


@pytest.mark.parametrize("purpose", ["email_verification", "password_reset", "magic"])
def test_invalid_origin_fails_before_any_database_mutation(delivery, monkeypatch, purpose):
    service, sink = delivery
    monkeypatch.setattr(auth.settings, "app_base_url", "http://127.0.0.1:8002")

    def forbidden():
        pytest.fail("Invalid public origin must be rejected before schema/token writes")

    monkeypatch.setattr(service, "ensure_schema", forbidden)
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        if purpose == "magic":
            service.create_magic_link_request(email="synthetic@example.test")
        else:
            service.create_auth_action_request(email="synthetic@example.test", purpose=purpose)
    assert not sink

"""FIX5: полный password HTTP/cookie/restore на чистом owned PostgreSQL stand."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

import pytest


pytestmark = pytest.mark.integration


def test_password_registration_login_cookie_restore_on_owned_schema(tmp_path, monkeypatch):
    from scripts.test_stand import environment

    env = {**os.environ, "STAND_ADMIN_URL": os.environ.get("STAND_ADMIN_URL") or os.environ.get("TEST_DATABASE_URL", "")}
    monkeypatch.setenv("STAND_ADMIN_URL", env["STAND_ADMIN_URL"])
    state_path = tmp_path / "state.json"

    def cli(action: str) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/test_stand.py", action, "--state", str(state_path), "--gateway", "1"],
            env=env, capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    cli("create")
    try:
        cli("bootstrap")
        cli("seed")
        isolated = environment(json.loads(state_path.read_text()))
        result = subprocess.run(
            [sys.executable, __file__, "--internal"], env=isolated,
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        cli("destroy")


def _internal() -> None:
    assert os.environ.get("AGENT4K_ISOLATED_STAND") == "1"
    from datetime import datetime, timedelta, timezone
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import auth_service as auth_module
    from Api import routes
    from Api.database import close_connection_pool, get_connection
    from Api.organization_invitation_service import hash_invitation_token

    state = json.loads(Path(os.environ["STAND_STATE"]).read_text())
    with get_connection() as connection:
        organization_id = connection.execute(
            "SELECT id FROM organizations WHERE code='e102_synthetic'"
        ).fetchone()["id"]
        participant_id = connection.execute(
            "SELECT id FROM users WHERE email='participant@example.test'"
        ).fetchone()["id"]
        new_user_id = connection.execute(
            "SELECT id FROM users WHERE email='other@example.test'"
        ).fetchone()["id"]
        runtime_counts_before = connection.execute(
            "SELECT (SELECT count(*) FROM m5_cycles) AS cycles, (SELECT count(*) FROM m5_cycle_sessions) AS sessions"
        ).fetchone()
        connection.execute("DELETE FROM auth_password_credentials WHERE user_id=%s", (new_user_id,))
        connection.execute("DELETE FROM user_identities WHERE user_id=%s", (new_user_id,))
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=72)
        login_token = "fix5-existing-login"
        registration_token = "fix5-new-registration"
        for token, email in ((login_token, "participant@example.test"), (registration_token, "other@example.test")):
            connection.execute(
                """INSERT INTO organization_invitations(
                    organization_id,token_hash,expires_at,recipient_email,purpose,delivery_status,sent_at
                ) VALUES(%s,%s,%s,%s,'personal_registration','accepted',NOW())""",
                (organization_id, hash_invitation_token(token), expires, email),
            )
        connection.commit()

    app = FastAPI()
    app.include_router(routes.router)

    with TestClient(app) as http:
        scanner = http.get(f"/users/organization-invitations/{login_token}")
        assert scanner.status_code == 200
        with get_connection() as connection:
            assert connection.execute(
                "SELECT used_at FROM organization_invitations WHERE token_hash=%s",
                (hash_invitation_token(login_token),),
            ).fetchone()["used_at"] is None

        login = http.post("/users/auth/email/password-login", json={
            "email": "participant@example.test", "password": state["password"],
            "organization_invitation_token": login_token,
        })
        assert login.status_code == 200, login.text
        assert routes.SESSION_COOKIE_NAME in login.cookies
        restored = http.get("/users/session/restore")
        assert restored.status_code == 200 and restored.json()["authenticated"] is True
        assert restored.json()["organization"]["organization_id"] == organization_id

    sent: list[dict] = []
    original_sender = auth_module.send_auth_action_email
    auth_module.send_auth_action_email = lambda **payload: sent.append(payload)
    try:
        with TestClient(app) as http:
            request = http.post("/users/auth/email/request-link", json={
                "email": "other@example.test", "organization_invitation_token": registration_token,
            })
            assert request.status_code == 200 and request.json()["auth_mode"] == "verification_pending"
            action_token = parse_qs(urlparse(sent[-1]["action_url"]).query)["token"][0]
            confirmed = http.post("/users/auth/email/confirm", json={"token": action_token})
            assert confirmed.status_code == 200 and confirmed.json()["auth_mode"] == "password_registration"
            registered = http.post("/users/auth/email/password-register", json={
                "email": "other@example.test", "password": "ValidPass1!", "password_confirm": "ValidPass1!",
                "verification_token": action_token, "organization_invitation_token": registration_token,
            })
            assert registered.status_code == 200, registered.text
            assert routes.SESSION_COOKIE_NAME in registered.cookies
            restored = http.get("/users/session/restore").json()
            assert restored["authenticated"] is True
            assert restored["organization"]["organization_id"] == organization_id
            repeated = http.post("/users/auth/email/password-register", json={
                "email": "other@example.test", "password": "ValidPass1!", "password_confirm": "ValidPass1!",
                "verification_token": action_token, "organization_invitation_token": registration_token,
            })
            assert repeated.status_code in {400, 403}
            forgot = http.post("/users/auth/password/forgot", json={"email": "other@example.test"})
            assert forgot.status_code == 200
            reset_token = parse_qs(urlparse(sent[-1]["action_url"]).query)["token"][0]
            validated = http.post("/users/auth/password/reset/validate", json={"token": reset_token})
            assert validated.status_code == 200 and validated.json()["auth_mode"] == "password_reset"
            reset = http.post("/users/auth/password/reset", json={
                "token": reset_token, "password": "ChangedPass2!", "password_confirm": "ChangedPass2!",
            })
            assert reset.status_code == 200, reset.text
            assert http.post("/users/auth/email/password-login", json={
                "email": "other@example.test", "password": "ValidPass1!",
            }).status_code in {400, 401, 403}
            assert http.post("/users/auth/email/password-login", json={
                "email": "other@example.test", "password": "ChangedPass2!",
            }).status_code == 200
            reused_reset = http.post("/users/auth/password/reset", json={
                "token": reset_token, "password": "ThirdPass3!", "password_confirm": "ThirdPass3!",
            })
            assert reused_reset.status_code in {400, 403}
        with get_connection() as connection:
            runtime_counts_after = connection.execute(
                "SELECT (SELECT count(*) FROM m5_cycles) AS cycles, (SELECT count(*) FROM m5_cycle_sessions) AS sessions"
            ).fetchone()
            assert runtime_counts_after == runtime_counts_before
    finally:
        auth_module.send_auth_action_email = original_sender
        close_connection_pool()


if __name__ == "__main__":
    _internal()

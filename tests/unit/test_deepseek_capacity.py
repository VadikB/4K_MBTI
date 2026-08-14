from __future__ import annotations

import json
import threading
from urllib import error

import pytest

from Api.deepseek_client import DeepSeekClient
from Api.llm import deepseek_gateway as gateway_module


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()


@pytest.mark.unit
def test_post_chat_releases_database_before_network(monkeypatch) -> None:
    client = DeepSeekClient()
    client.api_keys = ["test-key"]
    paused: list[bool] = []

    monkeypatch.setattr(
        gateway_module,
        "pause_thread_connections_for_external_io",
        lambda: paused.append(True) or 1,
    )
    monkeypatch.setattr(gateway_module.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    assert client._post_chat([{"role": "user", "content": "test"}]) == "ok"
    assert paused == [True]


@pytest.mark.unit
def test_concurrency_queue_returns_clear_overload_error(monkeypatch) -> None:
    client = DeepSeekClient()
    client.api_keys = ["test-key"]
    client._request_slots = threading.BoundedSemaphore(1)
    entered = threading.Event()
    release = threading.Event()

    class BlockingResponse(FakeResponse):
        def __enter__(self):
            entered.set()
            release.wait(timeout=2)
            return self

    monkeypatch.setattr(gateway_module, "pause_thread_connections_for_external_io", lambda: 0)
    monkeypatch.setattr(gateway_module.request, "urlopen", lambda *_args, **_kwargs: BlockingResponse())
    monkeypatch.setattr(gateway_module.settings, "deepseek_queue_timeout_seconds", 0.05)

    first_error: list[Exception] = []

    def first_request() -> None:
        try:
            client._post_chat([{"role": "user", "content": "first"}])
        except Exception as exc:  # pragma: no cover - diagnostic path
            first_error.append(exc)

    thread = threading.Thread(target=first_request)
    thread.start()
    assert entered.wait(timeout=1)
    with pytest.raises(RuntimeError, match="перегружен"):
        client._post_chat([{"role": "user", "content": "second"}])
    release.set()
    thread.join(timeout=2)
    assert not first_error


@pytest.mark.unit
def test_gateway_fails_over_to_next_routed_key(monkeypatch) -> None:
    client = DeepSeekClient()
    client.api_keys = ["first-key", "second-key"]
    attempted_authorizations: list[str] = []

    def fake_urlopen(req, **_kwargs):
        attempted_authorizations.append(req.headers["Authorization"])
        if len(attempted_authorizations) == 1:
            raise error.URLError("temporary")
        return FakeResponse()

    monkeypatch.setattr(gateway_module, "pause_thread_connections_for_external_io", lambda: 0)
    monkeypatch.setattr(gateway_module.request, "urlopen", fake_urlopen)

    assert client._post_chat([{"role": "user", "content": "test"}], routing_key="stable") == "ok"
    assert len(attempted_authorizations) == 2
    assert attempted_authorizations[0] != attempted_authorizations[1]


@pytest.mark.unit
def test_routing_key_produces_stable_key_order() -> None:
    client = DeepSeekClient()
    client.api_keys = ["key-a", "key-b", "key-c"]
    messages = [{"role": "user", "content": "same input"}]
    assert client._get_deepseek_key_chain("same-route", messages) == client._get_deepseek_key_chain(
        "same-route",
        messages,
    )

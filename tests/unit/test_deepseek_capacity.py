from __future__ import annotations

import json
import threading

import pytest

from Api import deepseek_client as deepseek_module
from Api.deepseek_client import DeepSeekClient


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
        deepseek_module,
        "pause_thread_connections_for_external_io",
        lambda: paused.append(True) or 1,
    )
    monkeypatch.setattr(deepseek_module.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

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

    monkeypatch.setattr(deepseek_module, "pause_thread_connections_for_external_io", lambda: 0)
    monkeypatch.setattr(deepseek_module.request, "urlopen", lambda *_args, **_kwargs: BlockingResponse())
    monkeypatch.setattr(deepseek_module.settings, "deepseek_queue_timeout_seconds", 0.05)

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

"""EXEC-FIX-02: saturation is retryable before transport.

No real credentials, database, network, provider or threads. The held semaphore
reproduces an unavailable provider slot, including through the legacy client.
"""
from __future__ import annotations

import json
import threading

import pytest

from Api.deepseek_client import DeepSeekClient
from Api.llm import deepseek_gateway as gateway_module
from Api.llm.contracts import LlmCapacityError, LlmGatewayError
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.product_cycle_preparation_queue import public_operation


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "synthetic ready"}}]}).encode()


@pytest.mark.unit
@pytest.mark.parametrize("through_client", [False, True], ids=["gateway", "legacy_client"])
def test_capacity_failure_precedes_transport_and_is_safe_retry(monkeypatch, through_client):
    gateway = DeepSeekGateway(api_keys=["synthetic-private-key"])
    slots = gateway.request_slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    calls = []
    monkeypatch.setattr(gateway_module, "pause_thread_connections_for_external_io", lambda: 0)
    monkeypatch.setattr(gateway_module.settings, "deepseek_queue_timeout_seconds", 0.001)
    monkeypatch.setattr(gateway_module.request, "urlopen", lambda *a, **k: calls.append((a, k)))
    if through_client:
        client = DeepSeekClient()
        client.gateway = gateway
        invoke = lambda: client._post_chat([{"role": "user", "content": "synthetic input"}])
    else:
        invoke = lambda: gateway.chat_with_trace([{"role": "user", "content": "synthetic input"}])

    with pytest.raises(LlmCapacityError) as captured:
        invoke()

    assert isinstance(captured.value, LlmGatewayError)
    assert not calls  # L2: no outbound request was sent, not merely no success.
    assert slots.acquire(blocking=False) is False  # Failed acquisition must not release another caller's slot.
    projected = public_operation({"operation_id": "synthetic-capacity", "status": "failed",
        "error_code": type(captured.value).__name__, "error_message": str(captured.value)})
    assert projected["retry_allowed"] is True
    assert projected["error"]["code"] == "ASSESSMENT_CYCLE_PREPARATION_TECHNICAL_FAILURE"
    assert "synthetic-private-key" not in str(projected)
    assert "synthetic input" not in str(projected)
    assert "Обратитесь" not in projected["error"]["message"]

    slots.release()
    monkeypatch.setattr(gateway_module.request, "urlopen", lambda *a, **k: calls.append((a, k)) or _Response())
    result = invoke()
    assert (result if through_client else result.content) == "synthetic ready"
    assert len(calls) == 1
    assert slots.acquire(blocking=False) is True
    assert slots.acquire(blocking=False) is False
    slots.release()


@pytest.mark.unit
@pytest.mark.parametrize("error_code,message", [
    ("RuntimeError", "DeepSeek API key is not configured"),
    ("ValueError", "DEEPSEEK_THINKING_MODE_UNSUPPORTED"),
    ("ValueError", "DEEPSEEK_RESPONSE_FORMAT_UNSUPPORTED"),
    ("RuntimeError", "unclassified runtime error"),
    ("LlmCapacityError", "M5_FUNCTIONAL_AS_NOT_ADMITTED:FAIL"),
    ("LlmCapacityError", "M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE"),
    ("LlmGatewayError", "M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE"),
])
def test_capacity_classification_does_not_enable_credential_configuration_or_admission_retry(error_code, message):
    projected = public_operation({"operation_id": "synthetic-terminal", "status": "failed",
        "error_code": error_code, "error_message": message})
    assert projected["retry_allowed"] is False


@pytest.mark.unit
@pytest.mark.parametrize("error_code", ["TimeoutError", "ConnectionError", "LlmGatewayError", "LlmCapacityError"])
def test_existing_transient_classes_remain_retryable(error_code):
    projected = public_operation({"operation_id": "synthetic-transient", "status": "failed",
        "error_code": error_code, "error_message": "private transport detail"})
    assert projected["retry_allowed"] is True
    assert "private transport detail" not in str(projected)

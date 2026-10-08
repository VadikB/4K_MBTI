import json

import pytest

from Api.llm.contracts import LlmGatewayError
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.llm.provider_contract import load_provider_contract

pytestmark = pytest.mark.unit


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def read(self): return json.dumps(self.value).encode()


def test_product_gateway_captures_declared_json_payload_without_secret(monkeypatch):
    captured = {}
    def urlopen(req, timeout):
        captured.update(json.loads(req.data))
        assert req.headers["Authorization"] == "Bearer test-secret"
        return Response({"id":"r1","model":"DeepSeek-V4.1-Flash","system_fingerprint":"rev",
                         "choices":[{"message":{"content":"{\"ok\":true}"},"finish_reason":"stop"}],
                         "usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}})
    monkeypatch.setattr("Api.llm.deepseek_gateway.request.urlopen", urlopen)
    gateway = DeepSeekGateway(api_keys=["test-secret"], base_url="https://api.deepseek.com", model="deepseek-flash")
    result = gateway.chat_with_trace([{"role":"system","content":"Return JSON."}], temperature=0,
        max_tokens=100, timeout_seconds=30, thinking={"type":"disabled"},
        response_format={"type":"json_object"})
    assert captured["thinking"] == {"type":"disabled"}
    assert captured["response_format"] == {"type":"json_object"}
    assert result.sent["model"] == "deepseek-flash"
    assert "test-secret" not in json.dumps(result.sent)
    assert result.provider["usage"]["total_tokens"] == 5
    assert result.provider["transport_attempts"] == [{"attempt":1,"outcome":"completed"}]


@pytest.mark.parametrize("content,finish_reason,message", [
    ("", "stop", "empty"), ("{\"partial\":", "length", "truncated")])
def test_empty_and_truncated_responses_are_technical_failures(monkeypatch, content, finish_reason, message):
    monkeypatch.setattr("Api.llm.deepseek_gateway.request.urlopen", lambda *_a, **_k: Response({
        "choices":[{"message":{"content":content},"finish_reason":finish_reason}], "usage":{"total_tokens":9}}))
    gateway = DeepSeekGateway(api_keys=["secret"], model="deepseek-flash")
    with pytest.raises(LlmGatewayError, match=message):
        gateway.chat_with_trace([{"role":"user","content":"Return JSON."}], response_format={"type":"json_object"})


def test_preflight_discloses_presence_not_secret_and_contract_is_versioned():
    contract = load_provider_contract()
    preflight = DeepSeekGateway(api_keys=["secret"], model="deepseek-flash").preflight(response_format="json_object")
    assert preflight["ready"] is True and preflight["secret_configured"] is True
    assert preflight["contract_version"] == contract["version"]
    assert ': "secret"' not in json.dumps(preflight)

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "assessment_definitions/providers/deepseek/v1/manifest.json"
)
GATEWAY_VERSION = "deepseek-product-gateway/1"


def load_provider_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    expected = (1, "deepseek_product_gateway", "1.0.0", "draft", "deepseek", "deepseek-flash")
    actual = tuple(value.get(k) for k in ("schema_version", "id", "version", "status", "provider", "model"))
    if actual != expected:
        raise ValueError("DEEPSEEK_PROVIDER_CONTRACT_INVALID")
    if value.get("thinking") != {"type": "disabled"}:
        raise ValueError("DEEPSEEK_PROVIDER_CONTRACT_INVALID")
    if value.get("supported_response_formats") != ["text", "json_object"]:
        raise ValueError("DEEPSEEK_PROVIDER_CONTRACT_INVALID")
    value["checksum"] = hashlib.sha256(raw).hexdigest()
    return value


def operation_parameters(operation: dict[str, Any]) -> dict[str, Any]:
    contract = load_provider_contract()
    if operation.get("provider") != contract["provider"] or operation.get("model") != contract["model"]:
        raise ValueError("DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED")
    if operation.get("endpoint") != contract["endpoint"]:
        raise ValueError("DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED")
    parameters = dict(operation["parameters"])
    response_format = operation.get("response_format", "text")
    if response_format not in contract["supported_response_formats"]:
        raise ValueError("DEEPSEEK_RESPONSE_FORMAT_UNSUPPORTED")
    parameters["thinking"] = dict(operation.get("thinking") or {"type": "disabled"})
    parameters["response_format"] = {"type": response_format}
    return parameters

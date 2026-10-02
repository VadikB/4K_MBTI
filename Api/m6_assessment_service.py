from __future__ import annotations

import json

from Api.assessment_configuration import definition_checksum
from Api.m5_rule_engine import _call_with_trace, _gateway_for
from Api.m6_assessment_contracts import validate_assessment
from Api.m6_assessment_package import verify_mechanism


def evaluate(value: dict, mechanism: dict, mechanism_hash: str, *, gateway=None):
    verify_mechanism(mechanism, mechanism_hash)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > mechanism["max_input_bytes"]:
        raise ValueError("M6_CONTEXT_LIMIT_EXCEEDED")
    resolved = _gateway_for(mechanism["operation"], gateway)
    if not resolved.enabled:
        raise ValueError("M6_GATEWAY_UNAVAILABLE")
    messages = [
        {"role": "system", "content": mechanism["prompt"] + "\nJSON Schema:\n" + json.dumps(mechanism["schema"], ensure_ascii=False)},
        {"role": "user", "content": encoded},
    ]
    raw, trace = _call_with_trace(resolved, messages, operation=mechanism["operation"],
                                  routing_key="m6-assessment:" + definition_checksum(value))
    try:
        if trace["identity_status"] != "sent_matches_snapshot":
            raise ValueError("M6_AI_IDENTITY_MISMATCH")
        output = validate_assessment(json.loads(raw), value)
    except Exception as exc:
        exc.ai_trace = trace
        raise
    return output, trace

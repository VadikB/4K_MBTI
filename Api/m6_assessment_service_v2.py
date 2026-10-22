from __future__ import annotations

import json

from Api.assessment_configuration import definition_checksum
from Api.m5_rule_engine import _gateway_for
from Api.m6_assessment_contracts import validate_assessment
from Api.m6_assessment_package import verify_mechanism
from Api.m6_validation_retry import call_and_validate


def evaluate(value, mechanism, mechanism_hash, *, gateway=None):
    verify_mechanism(mechanism, mechanism_hash)
    if mechanism.get("ref") != "m6_indicator_assessment/1.0.1":
        raise ValueError("M6_ASSESSMENT_MECHANISM_UNSUPPORTED")
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
    return call_and_validate(
        gateway=resolved, messages=messages, operation=mechanism["operation"],
        routing_key="m6-assessment-v2:" + definition_checksum(value),
        validate=lambda output: validate_assessment(output, value),
        max_attempts=int(mechanism["validation_attempts"]),
    )

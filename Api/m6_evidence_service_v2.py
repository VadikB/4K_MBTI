from __future__ import annotations

import json

from Api.assessment_configuration import definition_checksum
from Api.m5_rule_engine import _gateway_for
from Api.m6_contracts import EvidenceCandidate, assemble_analysis, validate_analysis
from Api.m6_package import verify_mechanism
from Api.m6_package_v2 import PREVIOUS_REF, QUOTE_HANDLER, QUOTE_INPUT_CONTRACT, QUOTE_OUTPUT_CONTRACT, QUOTE_REF
from Api.m6_quote_retry import PriorFragment, rejected_basis, validate_repaired_basis
from Api.m6_validation_retry import call_and_validate


def validate_current_analysis(value: dict, material: dict) -> dict:
    return validate_analysis(value, material, enforce_simple_basis=True)


def evaluate(material, mechanism, mechanism_hash, *, gateway=None):
    ref = mechanism.get("ref")
    if ref == QUOTE_REF:
        verify_mechanism(mechanism, mechanism_hash, handler=QUOTE_HANDLER, output_model=EvidenceCandidate)
        provider_input = {**material, "schema_version": 2}
        response_contract = {"input": QUOTE_INPUT_CONTRACT, "output": QUOTE_OUTPUT_CONTRACT}
    elif ref == PREVIOUS_REF:
        verify_mechanism(mechanism, mechanism_hash)
        provider_input = material
        response_contract = None
    else:
        raise ValueError("M6_MECHANISM_UNSUPPORTED")
    encoded = json.dumps(provider_input, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > mechanism["max_input_bytes"]:
        raise ValueError("M6_CONTEXT_LIMIT_EXCEEDED")
    resolved = _gateway_for(mechanism["operation"], gateway)
    if not resolved.enabled:
        raise ValueError("M6_GATEWAY_UNAVAILABLE")
    messages = [
        {"role": "system", "content": mechanism["prompt"] + "\nJSON Schema:\n" + json.dumps(mechanism["schema"], ensure_ascii=False)},
        {"role": "user", "content": encoded},
    ]
    prior: dict[str, PriorFragment] | None = None

    def validate(value):
        nonlocal prior
        if ref != QUOTE_REF:
            return validate_current_analysis(value, material)
        try:
            assembled = assemble_analysis(value, material)
            if prior:
                validate_repaired_basis(assembled, prior)
            return validate_current_analysis(assembled, material)
        except ValueError as error:
            if prior is None:
                prior = rejected_basis(value, material, error)
            raise

    output, trace = call_and_validate(
        gateway=resolved, messages=messages, operation=mechanism["operation"],
        routing_key="m6-v2:" + definition_checksum(material),
        validate=validate, response_contract=response_contract,
        max_attempts=int(mechanism["validation_attempts"]),
    )
    if ref == QUOTE_REF:
        trace["assembled_analysis"] = {"contract": "M6.EvidenceAnalysis/1", "checksum": definition_checksum(output)}
    return output, trace

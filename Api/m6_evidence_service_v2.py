from __future__ import annotations

import json

from Api.assessment_configuration import definition_checksum
from Api.m5_rule_engine import _gateway_for
from Api.m6_candidate_v3 import EvidenceCandidateV3, assemble_reviewed_analysis
from Api.m6_contracts import EvidenceCandidate, assemble_analysis, validate_analysis
from Api.m6_link_repair import address_validation_failures, collect_repair_basis, validate_link_repair
from Api.m6_package import verify_mechanism
from Api.m6_package_v2 import (
    PREVIOUS_REF, QUOTE_HANDLER, QUOTE_INPUT_CONTRACT, QUOTE_OUTPUT_CONTRACT, QUOTE_REF,
    REPAIR_HANDLER, REPAIR_INPUT_CONTRACT, REPAIR_OUTPUT_CONTRACT, REPAIR_REF,
)
from Api.m6_quote_retry import (
    rejected_basis, validate_repaired_basis, validate_verified_basis, validate_verified_bundles, verified_basis,
)
from Api.m6_validation_retry import call_and_validate, validation_failure


def validate_current_analysis(value: dict, material: dict) -> dict:
    return validate_analysis(value, material, enforce_simple_basis=True)


def evaluate(material, mechanism, mechanism_hash, *, gateway=None):
    ref = mechanism.get("ref")
    if ref == REPAIR_REF:
        verify_mechanism(mechanism, mechanism_hash, handler=REPAIR_HANDLER, output_model=EvidenceCandidateV3)
        provider_input = {**material, "schema_version": 3}
        response_contract = {"input": REPAIR_INPUT_CONTRACT, "output": REPAIR_OUTPUT_CONTRACT}
    elif ref == QUOTE_REF:
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
    prior = None
    verified = None
    repair = None
    accepted_reviews = []

    def validate_addressed(value):
        nonlocal repair, accepted_reviews
        try:
            analysis, reviews = assemble_reviewed_analysis(value, material)
            analysis = validate_current_analysis(analysis, material)
            validate_link_repair(analysis, reviews, repair, material)
            accepted_reviews = reviews
            return analysis
        except ValueError as error:
            if repair is None:
                repair = collect_repair_basis(value, material, error)
                error.repair_feedback = repair.feedback
            else:
                _, issues = validation_failure(error)
                error.addressed_validation_issues = address_validation_failures(issues, value, repair)
            raise

    def validate(value):
        nonlocal prior, verified
        try:
            analysis = (assemble_analysis(value, material) if ref == QUOTE_REF
                        else validate_current_analysis(value, material))
            if verified is not None:
                validate_verified_basis(analysis, verified.evidence)
            if prior:
                validate_repaired_basis(analysis, prior)
            if ref == QUOTE_REF:
                analysis = validate_current_analysis(analysis, material)
            if verified is not None:
                validate_verified_bundles(analysis, verified, material)
            return analysis
        except ValueError as error:
            if prior is None:
                prior = rejected_basis(value, material, error) if ref == QUOTE_REF else {}
                verified = verified_basis(value, material, quote_contract=ref == QUOTE_REF)
            raise

    output, trace = call_and_validate(
        gateway=resolved, messages=messages, operation=mechanism["operation"],
        routing_key="m6-v2:" + definition_checksum(material),
        validate=validate_addressed if ref == REPAIR_REF else validate, response_contract=response_contract,
        max_attempts=int(mechanism["validation_attempts"]),
        evidence_material=material,
        addressed_repair=ref == REPAIR_REF,
    )
    if response_contract is not None:
        trace["assembled_analysis"] = {"contract": mechanism["manifest"]["analysis_contract"],
                                       "checksum": definition_checksum(output)}
    if ref == REPAIR_REF:
        trace["repair_notes"] = accepted_reviews
    return output, trace

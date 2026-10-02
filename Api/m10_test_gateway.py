"""Deterministic AI gateway for isolated browser acceptance only."""
from __future__ import annotations

import json


class BrowserAcceptanceGateway:
    enabled = True

    def chat(self, messages, **_kwargs):
        value = json.loads(messages[1]["content"])
        if "evidence_analysis" in value:
            turn = value["material"]["turns"][-1]
            return json.dumps({
                "schema_version": 1, "mode": value["mode"],
                "targets": [{
                    "indicator_id": target["indicator_id"], "m2_version": target["m2_version"],
                    "status": "ASSESSED", "outcome": "L0",
                    "descriptor_basis": "Isolated browser acceptance fixture",
                    "rationale": "A persisted assessee turn is present in the closed material",
                    "refs": [{"kind": "turn", "id": turn["turn_id"], "meaning": "persisted assessee action"}],
                    "opportunity": "PRESENT", "opportunity_basis": "The case requested an answer",
                    "uncertainty": None, "contradictions": [], "clarification_history": [], "stop_reason": None,
                    "confidence": {"confirmed_features": ["persisted closed turn"], "alternatives_considered": [],
                                   "limitations": ["test gateway; not normative GC"], "reliability_protocol_ref": None},
                } for target in value["material"]["indicator_targets"]],
            }, ensure_ascii=False)
        return json.dumps({
            "schema_version": 1, "fragments": [], "signals": [], "evidence": [], "attribution_notes": [],
            "bundles": [{
                "indicator_id": target["indicator_id"], "evidence_ids": [],
                "opportunity_basis": "Persisted closed browser acceptance dialogue",
                "context_refs": [], "limitations": ["test gateway"], "contradictions": [],
            } for target in value["indicator_targets"]],
        }, ensure_ascii=False)


def enabled() -> bool:
    import os
    return os.getenv("AGENT4K_BROWSER_TEST_GATEWAY") == "1"

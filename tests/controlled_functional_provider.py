"""Owned-browser transport fixture for PM-03 generation, never a GC oracle.

The product still validates each candidate and persists its real tester/admission
trace. This adapter only replaces a paid provider response in a disposable stand.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from Api.m5_functional_generation_service import checksum


class ControlledFunctionalProvider:
    enabled = True

    def __init__(self, **kwargs):
        # Legacy non-PM-03 clients inspect this attribute to decide whether
        # their optional provider path is configured. Keep those paths off.
        self.api_keys = []
        self.endpoint = "test://controlled-functional-provider"
        self.requested_model = str(kwargs.get("model") or "deepseek-flash")
        self.model = "controlled-functional-v1"

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        routing_key = str(kwargs["routing_key"])
        if ":generation:" in routing_key or ":generation_repair:" in routing_key:
            candidate = json.loads(json.dumps(payload["author_as_example"], ensure_ascii=False))
            material_ids = [item["MaterialID"] for item in candidate["Материалы"]]
            event_ids = [item["EventID"] for item in candidate["События"]]
            character_ids = [item["CharacterID"] for item in candidate["Активные персонажи"]]
            for index, target in enumerate(candidate["IndicatorObservability"]):
                target.update({
                    "material_refs": material_ids[:1], "event_refs": event_ids[:1],
                    "character_refs": character_ids[:1], "authority_refs": ["participant"],
                    "author_mapping": {
                        "source_pointer": f"/IndicatorObservability/{index}",
                        "source_checksum": checksum(payload["author_as_example"]["IndicatorObservability"][index]),
                    },
                })
            content = json.dumps(candidate, ensure_ascii=False)
        else:
            required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            content = json.dumps({
                "candidate_checksum": payload.get("candidate_checksum"),
                "checks": [{
                    "check_id": item["check_id"], "status": "PASS",
                    "reason": "isolated scripted provider response, not human quality approval",
                    "evidence_paths": [], "findings": [],
                    "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"},
                } for item in required],
            }, ensure_ascii=False)
        return SimpleNamespace(content=content,
            sent={"provider": "controlled_fixture", "endpoint": self.endpoint,
                  "model": self.requested_model,
                  "contract": {"version": "synthetic-transport/1"}},
            provider={"model": self.model, "finish_reason": "stop",
                      "transport_attempts": [], "usage": {}})

"""Applicability for the v1.2 passport, resolved before any provider call."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from Api.m5_battery_contract import source_case_version
from Api.m5_functional_tester import checksum
from Api.m5_passport_v12 import INVARIANT_LINKS, REFERENCE_ID


def _source_field(label: str) -> str:
    return re.sub(r"^(\d+(?:\.\d+)?)\s+", r"\1/", label.strip())


def build_plan(snapshot: dict, protocol: dict, contract_path: Path, m2: dict) -> dict:
    case, design = snapshot["case_version"], snapshot["battery_scenario"]
    if review_content := design.get("review_content"):
        contract = review_content["contract"]
        contract_checksum = review_content["checksum"]
        expected_scope = "battery_v0.6"
        expected_versions = {"1.10.0": {"2.1.0"}, "1.10.1": {"2.1.1"},
                             "1.10.2": {"2.1.2"}, "1.10.3": {"2.1.3"}}.get(design["ref"]["version"], ())
        if protocol.get("version") != "3.3.0":
            raise ValueError("M5_BATTERY_REVIEW_PROTOCOL_MISMATCH")
    else:
        raw = contract_path.read_bytes()
        contract, contract_checksum = json.loads(raw), checksum(raw)
        expected_scope = protocol.get("scope")
        expected_versions = {"battery_v0.3_qa": {"2.0.0", "2.0.1"}, "battery_v0.4_qa": {"2.0.2"}}.get(
            expected_scope, set()
        )
    passport, pointers = case["passport"], case["passport_sources"]
    case_id, version = case["case_id"], case["version"]
    source = case["passport_source"]
    overlay = contract.get("cases", {}).get(case_id, {})
    if contract.get("version") not in expected_versions or (
        contract.get("id"), contract.get("schema_version"), contract.get("scope"),
            overlay.get("case_version"), overlay.get("passport_sha256")) != (
        "m5-functional-passport-content", 2, expected_scope,
        source_case_version(version, pilot=snapshot.get("battery_pilot", False)), source["sha256"],
    ):
        raise ValueError("M5_BATTERY_REVIEW_CASE_VERSION_MISMATCH")
    contract_ref = {key: contract[key] for key in ("id", "version", "sources")}
    contract_ref["checksum"] = contract_checksum
    case_ref = {
        "case_id": case_id, "case_version": version,
        "checksum": snapshot["refs"]["case"]["case_version_checksum"],
        "passport": source, "passport_version": case["passport_version"],
    }

    def reference(label):
        return pointers[_source_field(label)]

    def value(label):
        node = {"Паспорт": passport}
        for segment in reference(label)["pointer"].split("/")[1:]:
            key = segment.replace("~1", "/").replace("~0", "~")
            node = node[int(key)] if isinstance(node, list) else node[key]
        return node

    def definition(base, labels, sections, requirement, **extra):
        return {
            **base,
            "mandatory": True,
            "requirement": requirement,
            "finding_evidence_sections": list(dict.fromkeys(sections)),
            "source_ref": {**case_ref, "locations": [reference(label) for label in dict.fromkeys(labels)], **extra},
        }

    checks = []
    for item in protocol["common_checks"]:
        check = deepcopy(item)
        labels = check.pop("source_fields")
        sections = check.pop("finding_evidence_sections")
        checks.append(definition(check, labels, sections, item["requirement"]))

    all_content = protocol["common_checks"][0]["finding_evidence_sections"]
    for row in passport["16 Инвариантное ядро"]:
        label = row["InvariantID"]
        linked = []
        for key in INVARIANT_LINKS:
            links = row.get(key, [])
            for link in links if isinstance(links, list) else [links]:
                if _source_field(link) in pointers:
                    linked.append(link)
                else:
                    linked.extend(REFERENCE_ID.findall(link))
        checks.append(definition(
            {"check_id": "invariant:" + label, "category": "invariant", "protected": True},
            [label, *linked], all_content, row,
        ))

    indicator_refs = {}
    event_ids = {event["id"] for event in design["events"]}
    for target in case["indicator_targets"]:
        indicator = target["indicator_id"]
        indicator_refs[indicator] = m2[indicator]["descriptor"]
        field = f"22/{indicator}"
        row = value(field)
        locations = target["scenario_locations"]
        sections = [f"candidate_as/IndicatorObservability/{indicator}"]
        for location in locations:
            location_id = _source_field(location).rsplit("/", 1)[-1]
            if location_id in design["material_ids"]:
                sections.append(f"candidate_as/Материалы/{location_id}")
            elif location_id in design["fact_ids"]:
                sections.append(f"candidate_as/Закрытые фиксированные факты/{location_id}")
            elif location_id in design["roles"]:
                sections.append(f"candidate_as/Активные персонажи/{location_id}")
            elif location_id in event_ids:
                sections.extend((f"candidate_as/События/{location_id}", f"candidate_as/RuntimeBindings/{location_id}"))
        checks.append(definition(
            {"check_id": "indicator:" + indicator, "category": "indicator_observability", "protected": True},
            [field, *locations], sections,
            {"functional_conditions": row.get("Функциональные условия", []),
             "designed_condition": row.get("Проектное условие", []),
             "materials": row.get("Материалы и факты по функции", []),
             "opportunity": row["Условие возникновения"], "locations": row["Место в сценарии"],
             "observable_form": row["Доступная форма проявления"], "validity_risk": row["Риск потери"]},
            m2=target["normative_source"], indicator_id=indicator, skill_id=target["skill_id"],
        ))

    by_id = {item["check_id"]: item for item in checks}
    if len(by_id) != len(checks):
        raise ValueError("M5_FUNCTIONAL_TESTER_CHECK_ID_CONFLICT")
    for check_id, extra in overlay["requirements"].items():
        item = by_id[check_id]
        item["requirement"] = {"passport_or_protocol": item["requirement"], "case_content": extra["requirement"]}
        item["source_ref"]["case_content"] = contract_ref
        item["source_ref"]["supplemental_locations"] = [reference(label) for label in extra["source_fields"]]
        item["finding_evidence_sections"] = list(dict.fromkeys(
            [*item["finding_evidence_sections"], *extra["finding_evidence_sections"]]
        ))

    return {
        "protocol": {key: protocol[key] for key in ("id", "version", "checksum", "scope")},
        "content_contract": contract_ref, "case_ref": case_ref,
        "required_checks": checks, "not_applicable_checks": [],
        "indicator_descriptors": indicator_refs,
        "risk_context": {"source_ref": reference("21"), "risks": value("21")},
    }

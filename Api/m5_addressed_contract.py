"""Validate the scenario contract sealed by the SPEC.03 runtime rule binding."""
from __future__ import annotations


CASE_ID = "CASE.SPEC.03"


def validate_scenario_contract(case: dict, design: object) -> None:
    """Fail at the CaseVersion boundary before any provider work."""
    prefix = f"M5_SCENARIO_CONTRACT_INVALID:{case['case_id']}:{case['version']}"

    def require(condition, path):
        if not condition:
            raise ValueError(f"{prefix}:/{path}")

    require(isinstance(design, dict) and design.get("schema_version") == 1, "scenario_contract")
    passport = case["passport"]
    scenario = passport["17 Сценарий Dialogue"]
    starts = scenario["На старте"]
    functions = scenario["Функции материалов"]
    require(design.get("start_material_ids") == starts and "P00" in starts,
            "start_material_ids")
    require(design.get("material_functions") == functions, "material_functions")
    require(design.get("invariants") == passport["16 Инвариантное ядро"], "invariants")
    roles = design.get("roles")
    normative_roles = [{"function": row["Функция"], "contribution": row["Позиция и вклад"]}
                       for row in passport["11 Участники и позиции"]]
    expected_roles = {f"COLLEAGUE_{i}": role for i, role in enumerate(normative_roles, start=1)}
    require(roles == expected_roles, "roles")
    parts = design.get("parts")
    require(parts == {
        "first_input": {"owner": "COLLEAGUE_1", "requires": []},
        "second_input": {"owner": "COLLEAGUE_3", "requires": []},
        "combined_output": {"owner": "COLLEAGUE_2", "requires": ["first_input", "second_input"]},
    }, "parts")
    require(design.get("opening_speaker_id") == parts["combined_output"]["owner"], "opening_speaker_id")

    events = design.get("events")
    passport_events = {item["step_id"]: item["content"]["Условие запуска"] for item in case["scenario"]}
    require(isinstance(events, dict) and events.keys() == passport_events.keys()
            and all(isinstance(event, dict) for event in events.values()), "events")
    for event_id, condition in passport_events.items():
        require(bool(condition) and events[event_id].get("condition") == condition, f"events/{event_id}/condition")
    require(set(events) == {"E01_UPDATE", "E02_TRANSFER", "E03_REPLY"}, "events")
    update, transfer, reply = (events[key] for key in ("E01_UPDATE", "E02_TRANSFER", "E03_REPLY"))
    require(update.get("function") == "material_update" and update.get("material_ids") == ["M04"]
            and set(functions) - set(starts) == {"M04"}, "events/E01_UPDATE/material_ids")
    require(update.get("speaker_ids") == [parts["first_input"]["owner"]]
            and update.get("recipient_ids") == ["assessee"]
            and update.get("repeat") == "once" and bool(update.get("acknowledgement")), "events/E01_UPDATE")
    require(transfer.get("function") == "information_transfer" and transfer.get("material_ids") == ["M04"]
            and set(transfer.get("classification", {})) == {"DIRECT", "DELEGATE"}, "events/E02_TRANSFER")
    require(reply.get("function") == "character_reaction" and reply.get("speaker_ids") == list(expected_roles)
            and reply.get("material_ids") == [] and bool(reply.get("classification")), "events/E03_REPLY")
    targets = passport["22 IndicatorIDs"]
    require("K2.I08" in targets["Точный перечень"] and design.get("required_observability") == {
        "K2.I08": {"material_refs": ["M04"], "event_refs": ["E01_UPDATE", "E02_TRANSFER"]},
    }, "required_observability/K2.I08")

    control = design.get("control")
    require(isinstance(control, dict) and bool(control.get("condition"))
            and set(control.get("codes", {})) == {"CONTINUE", "FINAL", "STOP", "PAUSE", "UNKNOWN"}, "control")
    candidate = design.get("candidate_contract")
    require(isinstance(candidate, dict) and bool(candidate.get("instruction"))
            and candidate.get("sealed_fields") == ["Стартовые MaterialIDs", "События", "RuntimeBindings"]
            and set(candidate.get("field_overrides", {})) == {"Материалы", "Активные персонажи", "IndicatorObservability"},
            "candidate_contract")

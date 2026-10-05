from __future__ import annotations

from fractions import Fraction

LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def _score(value: Fraction) -> dict:
    return {"value": float(value), "numerator": value.numerator, "denominator": value.denominator}


def _coverage(required: set[str], present: set[str], reasons: dict[str, str], version: str) -> dict:
    included = sorted(required & present)
    missing = sorted(required - present)
    return {"numerator": len(included), "denominator": len(required), "ratio": (len(included) / len(required) if required else None),
            "included_ids": included, "missing_ids": missing, "missing_reasons": {x: reasons.get(x, "NOT_AVAILABLE") for x in missing},
            "composition_version": version}


def calculate(*, hierarchy: list[dict], observations: list[dict], decisions: list[dict],
              planned_indicator_ids: list[str], composition_version: str) -> dict:
    """Детерминированное ядро M6.7: IA -> Indicator -> Component -> Skill."""
    by_indicator: dict[str, list[dict]] = {}
    for item in observations:
        by_indicator.setdefault(item["indicator_id"], []).append(item)
    decision_map = {x["indicator_id"]: x for x in decisions}
    if len(decision_map) != len(decisions):
        raise ValueError("M6_ADMISSION_DUPLICATE_DECISION")
    identities = [(x["indicator_id"], x["assessment_situation_id"]) for x in observations]
    if len(identities) != len(set(identities)):
        raise ValueError("M6_ADMISSION_AMBIGUOUS_REVISION")
    all_indicators = {i for skill in hierarchy for component in skill["components"] for i in component["indicator_ids"]}
    if len(all_indicators) != sum(len(c["indicator_ids"]) for s in hierarchy for c in s["components"]):
        raise ValueError("M6_HIERARCHY_DUPLICATE_INDICATOR")
    unknown = (set(by_indicator) | set(decision_map) | set(planned_indicator_ids)) - all_indicators
    if unknown:
        raise ValueError("M6_AGGREGATION_TARGET_SET_MISMATCH")

    contributions, admissions = {}, []
    interpreted: set[str] = set()
    opportunities = {i for i, rows in by_indicator.items() if any(x.get("opportunity") == "PRESENT" for x in rows)}
    reasons: dict[str, str] = {}
    for indicator in sorted(all_indicators):
        rows = by_indicator.get(indicator, [])
        assessed = [x for x in rows if x.get("outcome") in LEVELS]
        decision = decision_map.get(indicator)
        if assessed and decision is None:
            raise ValueError("M6_ADMISSION_DECISION_REQUIRED")
        if decision:
            selected = set(decision.get("included_revision_ids", []))
            actual = {x["revision_id"] for x in assessed}
            if selected - actual:
                raise ValueError("M6_ADMISSION_REFERENCE_INVALID")
            numeric = bool(decision.get("numeric_admissible"))
            if decision.get("schema_version") == 2:
                interpreted_ids = set(decision["interpretable_revision_ids"])
                individual = decision["individual"]
                considered = {x["revision_id"] for x in rows}
                if (set(decision["considered_revision_ids"]) != considered
                        or len(individual) != len(considered)
                        or {x["revision_id"] for x in individual} != considered
                        or interpreted_ids != {x["revision_id"] for x in individual if x["status"] == "ADMITTED"}
                        or interpreted_ids - actual
                        or bool(interpreted_ids) != decision["interpretation_admissible"]):
                    raise ValueError("M6_ADMISSION_REFERENCE_INVALID")
                if numeric and (not selected or selected != interpreted_ids
                        or decision["joint"]["status"] != "COMPARABLE"
                        or decision["sufficiency"]["met"] is not True):
                    raise ValueError("M6_CONVENIENT_SUBSET_FORBIDDEN")
                if not numeric and selected:
                    raise ValueError("M6_ADMISSION_REFERENCE_INVALID")
            else:
                # Compatibility for explicit historical/manual v1 decisions.
                interpreted_ids = actual if decision.get("interpretation_admissible") else set()
                if numeric and (not selected or selected != actual):
                    raise ValueError("M6_CONVENIENT_SUBSET_FORBIDDEN")
            admission = {**decision, "interpretable_revision_ids": sorted(interpreted_ids)}
            admissions.append(admission)
            if interpreted_ids:
                interpreted.add(indicator)
            if numeric:
                values = [LEVELS[x["outcome"]] for x in assessed if x["revision_id"] in selected]
                value = Fraction(sum(values), len(values))
                contributions[indicator] = {"indicator_id": indicator, "score": _score(value),
                    "included_revision_ids": sorted(selected), "as_count": len({x["assessment_situation_id"] for x in assessed if x["revision_id"] in selected}),
                    "minimum": min(values), "maximum": max(values), "spread": max(values)-min(values)}
            else:
                reasons[indicator] = decision.get("reason_code", "NOT_ADMISSIBLE")
        elif not assessed:
            reasons[indicator] = "NO_JUSTIFIED_FINAL_IA"

    skill_results, components_with_score, complete_components = [], set(), set()
    for skill in hierarchy:
        component_results = []
        for component in skill["components"]:
            required = list(component["indicator_ids"])
            values = [Fraction(contributions[x]["score"]["numerator"], contributions[x]["score"]["denominator"])
                      for x in required if x in contributions]
            result = {"component_id": component["component_id"], "required_indicator_ids": required,
                      "included_indicator_ids": [x for x in required if x in contributions],
                      "missing_indicator_ids": [x for x in required if x not in contributions]}
            if values:
                result["score"] = _score(sum(values, Fraction()) / len(values))
                result["completeness"] = "full" if len(values) == len(required) else "partial"
                components_with_score.add(component["component_id"])
                if result["completeness"] == "full": complete_components.add(component["component_id"])
            component_results.append(result)
        scored = [x for x in component_results if "score" in x]
        has_result = any(i in interpreted for c in skill["components"] for i in c["indicator_ids"])
        value = {"skill_id": skill["skill_id"], "components": component_results}
        if scored:
            scores = [Fraction(x["score"]["numerator"], x["score"]["denominator"]) for x in scored]
            value["score"] = _score(sum(scores, Fraction()) / len(scores))
            full = len(scored) == len(component_results) and all(x["completeness"] == "full" for x in scored)
            value["outcome"] = "full_score" if full else "partial_score"
        else:
            value["outcome"] = "result_without_score" if has_result else "no_result"
        value["skill_result_exists"] = value["outcome"] != "no_result"
        skill_results.append(value)

    def coverages(indicators: set[str], label: str) -> dict:
        component_ids = {c["component_id"] for s in hierarchy for c in s["components"] if set(c["indicator_ids"]) & indicators}
        return {"scope": label,
            "opportunities": _coverage(indicators, opportunities, reasons, composition_version),
            "indicator_assessments": _coverage(indicators, interpreted, reasons, composition_version),
            "admissible_contributions": _coverage(indicators, set(contributions), reasons, composition_version),
            "components_with_score": _coverage(component_ids, components_with_score, {}, composition_version),
            "complete_components": _coverage(component_ids, complete_components, {}, composition_version)}
    full = coverages(all_indicators, "full_m2")
    planned = coverages(set(planned_indicator_ids), "cycle_plan")
    return {"indicator_contributions": [contributions[x] for x in sorted(contributions)], "admission_decisions": admissions,
            "skill_outcomes": skill_results, "coverage": {"full_m2": full, "cycle_plan": planned}}

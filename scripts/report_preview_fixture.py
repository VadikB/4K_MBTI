"""Shared synthetic saved Reports for FIX-02 unit, HTTP, browser and preview.

No database/provider imports; the JSON freezes a real catalog's IDs and names.
It is test material, never a runtime configuration or an assessment producer.
"""
from copy import deepcopy
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/m8_report_preview.json").read_text())


def identifier(key):
    return str(uuid5(NAMESPACE_URL, "4k-synthetic-report-preview/" + key))


def saved_reports():
    reports = {}
    names = {value for item in FIXTURE["examples"].values() for value in item.values()}
    for name in sorted(names):
        previous = name.endswith("previous")
        closed = "2026-10-01T10:00:00Z" if previous else "2026-11-17T10:00:00Z"
        skills = []
        for index, source in enumerate(FIXTURE["skills"]):
            skill = deepcopy(source)
            required = skill.pop("required_indicator_ids")
            score = [0, 2.25, 3][index] if index < 3 else 2.25
            outcome = "full_score"
            included = required[:]
            if name.startswith(("normal-", "mixed-", "partial-")) or name == "role-previous":
                score = ([1.75, 0, 2][index] if index < 3 else 2) if previous else ([2.25, 0, 1.75][index] if index < 3 else 2.25)
            if name.startswith("partial-") and index == 0:
                score, outcome, included = (1.5 if previous else 1.75), "partial_score", required[:-1]
            if name == "outcomes":
                # Three numeric axes surrounded by gaps, plus two distinct no-number outcomes.
                if index == 1:
                    score, outcome, included = 1.5, "partial_score", required[:-1]
                elif index == 2 or index > 6:
                    score, outcome, included = None, "result_without_score", []
                elif index == 3:
                    score, outcome, included = None, "no_result", []
            if name.startswith("mixed-"):
                if index == 1:
                    score, outcome = 1.5, "partial_score"
                    included = required[:-1] if previous else required[1:]
                elif index == 2 and not previous:
                    score, outcome, included = 1.75, "partial_score", required[:-1]
                elif index in (3, 4):
                    score, outcome, included = None, ("result_without_score" if index == 3 else "no_result"), []
            if name in ("error-a", "error-b") and index == 0:
                score = 0 if name == "error-a" else 2.25
            reasons = []
            if outcome == "partial_score":
                reasons = [{"code": "observation_missing", "message": "Оценена часть обязательных проявлений: в этом примере не наблюдались остальные."}]
            elif outcome == "result_without_score":
                reasons = [{"code": "observation_missing", "message": "Синтетические наблюдения сохранены; оснований объединить их в число недостаточно."}]
            elif outcome == "no_result":
                reasons = [{"code": "observation_missing", "message": "В вымышленной ситуации недостаточно материала для результата."}]
            skill.update(outcome=outcome, completeness={"full_score": "full", "partial_score": "partial"}.get(outcome),
                score=None if score is None else {"value": score, "numerator": int(score * 4), "denominator": 4},
                limitations=[], presentation={"required_indicator_ids": required, "included_indicator_ids": included,
                    "reasons": reasons, "remaining_plan_relevant": False})
            skills.append(skill)
        role = {"id": identifier(name + "-role"), "checksum": "synthetic-role-specialist", "name": "Специалист"}
        if name == "role-previous":
            role.update(checksum="synthetic-role-manager", name="Руководитель")
        report = {"id": identifier(name), "cycle_id": identifier(name + "-cycle"), "revision_no": 1,
            "results_revision_id": identifier(name + "-results"), "owner_user_id": 18, "status": "ready",
            "created_at": closed, "program_name": "Программа 4К · " + ("октябрь" if previous else "ноябрь"),
            "collection_closed_at": closed,
            "c67": {"template_version": "m8-basic-report/1.5.0", "display": {}, "role_ref": role,
                "profile_ref": {"id": identifier(name + "-profile"), "checksum": "synthetic-profile"},
                "target_profile": None, "skills": skills,
                "competencies": [{"competency_id": key, "competency_name": next(s["competency_name"] for s in skills if s["competency_id"] == key),
                    "skill_ids": [s["skill_id"] for s in skills if s["competency_id"] == key]}
                    for key in dict.fromkeys(s["competency_id"] for s in skills)],
                "time": {"started_at": closed}, "collection": {"closed_at": closed}, "coverage": {},
                "reliability": {"status": "not_verified"},
                "limitations": ["Числовой показатель не определяет общий уровень владения навыком"],
                "test_result": {"synthetic": True, "usage_scope": "local_preview"},
                "partial_result": {"plan_completed": True, "is_incomplete": False,
                    "progress": {"completed": 3, "planned": 3}, "limitation_reasons": []},
                "descriptive": {"status": "ready", "summary": ["Вымышленные результаты локального примера. Числа и наблюдения заданы для проверки интерфейса."],
                    "claims": [{"kind": kind, "skill_ids": [s["skill_id"]], "limitations": [],
                        "text": (("Пример A: уточнил срок" if name == "error-a" else "Пример B: согласовал условие")
                            if name.startswith("error-") else f"Синтетический пример {'предыдущей' if previous else 'текущей'} оценки: {s['skill_name']}." )}
                        for s in skills for kind in ("observation", "quote")]},
                "provenance": {"sources": {"M2": FIXTURE["source_sha256"], "M6": "synthetic-saved-m6-v1.8"},
                    "algorithm": {"version": "synthetic-saved", "rules_hash": "synthetic-same-rules"},
                    "comparison_evidence": {"contract_version": "m8-comparison-evidence/1.0.0",
                        "semantic_composition": {"full_target_set_checksum": FIXTURE["source_sha256"]},
                        "assessment_conditions": {"time_budget_seconds": 7200, "calendar_window_seconds": 259200,
                            "return_policy_checksum": "synthetic-return-policy"}}}}}
        report["c67"]["display"]["program_name"] = report["program_name"]
        reports[name] = report
    return reports


def preview_payload():
    from Api.m8_report_access import public_projection
    reports = saved_reports()
    return {"fixture": FIXTURE, "reports": {name: public_projection(value) for name, value in reports.items()}}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    from Api.m8_report_comparison import compare_reports, render_comparison_pdf
    from Api.m8_results import render_pdf
    command = json.load(sys.stdin)
    reports = saved_reports()
    if command["operation"] == "payload":
        print(json.dumps(preview_payload(), ensure_ascii=False))
    elif command["operation"] == "compare":
        print(json.dumps(compare_reports(reports[command["current"]], reports[command["previous"]]), ensure_ascii=False))
    elif command["operation"] == "comparison_pdf":
        sys.stdout.buffer.write(render_comparison_pdf(compare_reports(reports[command["current"]], reports[command["previous"]])))
    elif command["operation"] == "pdf":
        sys.stdout.buffer.write(render_pdf(reports[command["current"]]))

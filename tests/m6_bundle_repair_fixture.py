import json


TARGETS = (
    "K1.I06", "K1.I09", "K4.I03", "K4.I05", "K4.I12", "K4.I13", "K4.I14", "K4.I16", "K4.I17",
)
LEGACY_HASH = "1b75e29673da38ed2fbb1a3167b9fc49f54ddee514fc38f7744a2efe02239620"
ANSWER = "Сверю сроки. Уточню цену."
BASES = {
    "K1.I06": "Участник включил сверку сроков в содержание ответа о дальнейших действиях.",
    "K1.I09": "Участник однозначно называет предмет уточнения — цену. Значение цены не названо.",
    "K4.I03": "Можно было оценить достоверность данных. В ходе заявлена только будущая сверка.",
    "K4.I05": "Можно было сопоставить сведения о сроках. В ходе нет сопоставления конкретных сведений.",
    "K4.I12": "Участник мог указать допущения о сроках или цене. В ходе допущения не сформулированы.",
    "K4.I13": "Можно было связать предлагаемые действия с условиями. В ходе названы два намерения без связующего рассуждения.",
    "K4.I14": "Можно было обосновать вывод о дальнейших действиях. Вывод и основания в ходе отсутствуют.",
    "K4.I16": "Можно было сравнить варианты по срокам и цене. В ходе ни одного сравнения вариантов нет.",
    "K4.I17": "Можно было оценить последствия вариантов. В ходе риски и их связь с вариантами не названы.",
}


class RecordedEvidenceGateway:
    enabled = True

    def __init__(self, *replies):
        self.replies = replies
        self.calls = []
        self.responses = []

    def chat(self, messages, **kwargs):
        index = len(self.calls)
        self.calls.append(messages)
        material = json.loads(messages[1]["content"])
        response = self.replies[index](material)
        self.responses.append(response)
        return response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)


def complete_reply(material):
    turn, = [item for item in material["turns"] if item["speaker_type"] == "assessee"]
    assert turn["content"] == ANSWER
    turn_id = turn["turn_id"]
    criteria = {item["id"]: item for item in material["criteria"]}
    version = material.get("schema_version", 1)
    result = {"schema_version": version, "fragments": [], "signals": [], "evidence": [],
              "bundles": [], "attribution_notes": []}
    for indicator, key, quote in (("K1.I06", "schedule", "Сверю сроки"), ("K1.I09", "price", "Уточню цену")):
        criterion = criteria[indicator]
        fragment = {"id": f"quote-{key}", "turn_id": turn_id, "quote": quote}
        if version == 1:
            start = ANSWER.index(quote)
            fragment.update(start=start, end=start + len(quote))
        signal = {"id": f"signal-{key}", "fragment_id": fragment["id"], "observation": BASES[indicator],
                  "form_description": "Письменное намерение", "context_refs": []}
        evidence = {
            "id": f"evidence-{key}", "indicator_id": indicator, "m2_version": criterion["m2_version"],
            "type": "Simple", "interpretation": BASES[indicator], "bs_ids": [signal["id"]],
            "fragment_ids": [fragment["id"]], "ordered_turn_ids": [turn_id],
            "attribution": {**{field: criterion[field] for field in ("function", "product", "evidence_pattern")},
                            "boundaries": criterion["boundary"]},
            "context_refs": [], "limitations": ["Наблюдается намерение. Выполненное действие ещё не показано."],
            "composite_basis": None,
        }
        result["fragments"].append(fragment)
        result["signals"].append(signal)
        result["evidence"].append(evidence)
    evidence_ids = {item["indicator_id"]: [item["id"]] for item in result["evidence"]}
    for target in material["indicator_targets"]:
        indicator = target["indicator_id"]
        result["bundles"].append({
            "indicator_id": indicator, "evidence_ids": evidence_ids.get(indicator, []),
            "opportunity_basis": BASES[indicator], "limitations": [], "contradictions": [],
            "context_refs": [{"kind": "turn", "id": turn_id, "meaning": "Исходный письменный ход"}],
        })
    return result


def double_defect_reply(material):
    result = complete_reply(material)
    first, empty = result["fragments"]
    empty["quote"] = ""
    if result["schema_version"] == 1:
        first.update(start=1, end=12)
        empty.update(start=0, end=0)
    else:
        first["quote"] = "Сверю дедлайн"
    result.update(signals=[], evidence=[], bundles=[])
    return result


def partial_reply(material):
    result = complete_reply(material)
    damaged = result["fragments"][1]
    if result["schema_version"] == 1:
        damaged["end"] += 1
    else:
        damaged["quote"] = "Уточню стоимость"
    result["bundles"] = [bundle for bundle in result["bundles"] if bundle["indicator_id"] == "K1.I06"]
    return result


def retry_reply(material, defect):
    result = complete_reply(material)
    if defect == "empty":
        result.update(fragments=result["fragments"][:1], signals=[], evidence=[], bundles=[])
    elif defect == "missing":
        result["bundles"].pop()
    elif defect == "foreign":
        result["bundles"][-1]["indicator_id"] = "K9.I99"
    elif defect == "duplicate":
        result["bundles"].append(dict(result["bundles"][-1]))
    elif defect == "invented":
        result["fragments"][0]["quote"] = "Срок уже согласован"
    return result

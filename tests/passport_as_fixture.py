"""Small synthetic AS values for transport and persistence tests."""

def synthetic_as(payload: dict) -> dict:
    case = payload["case"]
    passport = case["Паспорт"]
    scenario = passport["17 Сценарий Dialogue"]
    targets = passport["22 IndicatorIDs"]
    starts = scenario["На старте"]
    events = scenario["События"]
    materials = sorted(scenario["Функции материалов"])
    characters = [f"SYNTHETIC-{n + 1}" for n in range(passport["19 Параметры сложности"]["Фиксировано"]["Активные персонажи"])]
    bindings = {}
    for index, event in enumerate(events):
        updates = [material_id for material_id in materials if material_id not in starts and index == 0]
        speakers = characters if not updates else []
        function = "material_update" if updates else "character_reaction" if speakers else "facilitator_action"
        bindings[event["EventID"]] = {"function": function, "speaker_ids": speakers, "material_ids": updates}
    return {
        "AssessmentSituationID": "AS-SYNTHETIC:" + case["CaseID"], "Version": "1",
        "CaseID": case["CaseID"], "CaseVersion": case["Version"],
        "CaseTypeIDs": passport["3 CaseTypeIDs"], "BaseRole": payload["requirements"]["base_role"],
        "IndicatorIDs": targets["Точный перечень"], "Версии M2": targets["Версии M2"],
        "Название": "Синтетическая ситуация",
        "Применённые замены": [], "Закрытые фиксированные факты": [],
        "Стартовые MaterialIDs": starts,
        "Материалы": [{"MaterialID": key, "Название": f"Тест {key}", "Текст": f"Синтетический текст {key}."}
                      for key in materials],
        "Активные персонажи": [
            {"CharacterID": key, "Имя": key, "Роль": "Тестовая роль", "Текст": "Синтетическая позиция.",
             "Начальные знания": []} for key in characters
        ],
        "События": [{"EventID": item["EventID"], **{key: "Условие теста." for key in item if key != "EventID"}}
                    for item in events],
        "RuntimeBindings": bindings,
        "IndicatorObservability": [{
            "IndicatorID": indicator_id, "Конкретное условие": "Синтетическое условие.",
            "Форма проявления": "Тестовое действие.", "Дефект потери": "Условие утрачено.",
            "material_refs": materials[:1], "event_refs": [events[0]["EventID"]],
            "character_refs": characters[:1], "authority_refs": ["participant"],
        } for indicator_id in targets["Точный перечень"]],
    }

from __future__ import annotations


DEFICIT_PRIORITY = (
    ("structure", lambda metrics: float(metrics.get("avg_block_coverage", 0) or 0) < 50),
    ("artifact", lambda metrics: float(metrics.get("avg_artifact_compliance", 0) or 0) < 50),
    ("evidence", lambda metrics: float(metrics.get("evidence_hit_rate", 0) or 0) < 0.5),
    ("redflags", lambda metrics: float(metrics.get("avg_red_flag_count", 0) or 0) > 2),
)


COMPETENCY_GROWTH_RECOMMENDATIONS = {
    "Коммуникация": {
        "structure": "По коммуникации стоит усилить структуру ответа: фиксировать контекст, уточняющие вопросы, договоренности и следующий шаг.",
        "artifact": "По коммуникации важно точнее попадать в ожидаемый формат артефакта: сообщение стейкхолдеру должно содержать статус, срок и понятный следующий шаг.",
        "evidence": "По коммуникации полезно делать ответы более наблюдаемыми: явно формулировать позицию, вопросы и договоренности, чтобы навык проявлялся в тексте.",
        "redflags": "По коммуникации стоит снизить число типовых ошибок: не игнорировать ограничения, не пропускать резюме и не оставлять ответ без следующего шага.",
        "generic": "Усилить коммуникацию: чаще фиксировать позицию, вопросы и договоренности в явном виде.",
    },
    "Командная работа": {
        "structure": "По командной работе стоит делать ответ более структурным: явно показывать роли, точки синхронизации и контроль исполнения.",
        "artifact": "По командной работе важно точнее попадать в артефакт плана действий: кто делает, в какой последовательности, по каким контрольным точкам.",
        "evidence": "По командной работе полезно явнее проявлять координацию: показывать распределение ролей, поддержку участников и согласование действий.",
        "redflags": "По командной работе стоит уменьшить число red flags: не пропускать роли, контрольные точки и критерии взаимодействия.",
        "generic": "Усилить командную работу: показывать распределение ролей, синхронизацию и поддержку участников.",
    },
    "Креативность": {
        "structure": "По креативности стоит лучше структурировать ответ: выделять альтернативы, критерии отбора и следующий шаг по проверке идеи.",
        "artifact": "По креативности важно точнее попадать в формат артефакта: идеи, пилоты и варианты должны быть оформлены как проверяемый план, а не как общее рассуждение.",
        "evidence": "По креативности полезно явнее проявлять генерацию вариантов: предлагать альтернативы, пилоты и нестандартные решения в явном виде.",
        "redflags": "По креативности стоит снизить число red flags: не оставлять ответ без альтернатив, критериев выбора и ограничений для проверки идеи.",
        "generic": "Усилить креативность: предлагать альтернативы, пилоты и нестандартные варианты решений.",
    },
    "Критическое мышление": {
        "structure": "По критическому мышлению стоит лучше структурировать ответ: выделять критерии, риски, гипотезы и проверку решения.",
        "artifact": "По критическому мышлению важно точнее попадать в формат артефакта: решение должно быть оформлено через критерии, риски и обоснованный выбор.",
        "evidence": "По критическому мышлению полезно делать анализ наблюдаемым: явно показывать логику выбора, допущения и проверку гипотез.",
        "redflags": "По критическому мышлению стоит снизить число red flags: не пропускать критерии, ограничения, риски и контроль решения.",
        "generic": "Усилить критическое мышление: добавлять критерии, риски, гипотезы и проверку решений.",
    },
}


WEAK_SIGNAL_RECOMMENDATIONS = [
    "По последней сессии подтвержденных сигналов пока недостаточно для корректной интерпретации зон роста.",
    "Сначала стоит усилить структурность ответов и попадание в ожидаемый формат артефакта кейса.",
    "Рекомендуется пройти ассессмент повторно и дать более развернутые ответы по кейсам.",
]


ZERO_SIGNAL_RECOMMENDATIONS = [
    "По последней сессии навыки не были проявлены на уровне, достаточном для корректной интерпретации зон роста.",
    "Рекомендуется пройти ассессмент повторно и дать более развернутые ответы по кейсам.",
]


def build_interpretation_basis_items(metrics: dict | None) -> list[str]:
    metrics = metrics or {}
    evidence_hit_rate = round(float(metrics.get("evidence_hit_rate", 0) or 0) * 100)
    avg_block_coverage = round(float(metrics.get("avg_block_coverage", 0) or 0))
    avg_artifact_compliance = round(float(metrics.get("avg_artifact_compliance", 0) or 0))
    avg_red_flag_count = round(float(metrics.get("avg_red_flag_count", 0) or 0), 1)
    return [
        f"Доля навыков с подтвержденными признаками проявления в ответах: {evidence_hit_rate}%",
        f"Покрытие обязательных блоков: {avg_block_coverage}%",
        f"Соответствие артефакту: {avg_artifact_compliance}%",
        f"Среднее число red flags на навык: {avg_red_flag_count}",
    ]


def build_response_pattern_text(metrics: dict | None, *, has_interpretation_signal: bool) -> str:
    metrics = metrics or {}
    avg_block_coverage = float(metrics.get("avg_block_coverage", 0) or 0)
    avg_artifact_compliance = float(metrics.get("avg_artifact_compliance", 0) or 0)
    evidence_hit_rate = float(metrics.get("evidence_hit_rate", 0) or 0)
    avg_red_flag_count = float(metrics.get("avg_red_flag_count", 0) or 0)

    if not has_interpretation_signal:
        if avg_block_coverage < 25:
            return "Наблюдаемый паттерн: ответы пока чаще остаются краткими и недостаточно структурированными, без явной фиксации критериев, договоренностей и следующего шага."
        if avg_artifact_compliance < 25:
            return "Наблюдаемый паттерн: в ответах есть попытка решить кейс по содержанию, но формат ожидаемого артефакта пока соблюдается непоследовательно."
        if evidence_hit_rate < 0.2:
            return "Наблюдаемый паттерн: решения и действия пока выражены слишком неявно, поэтому система видит мало подтвержденных сигналов проявления навыков."
        if avg_red_flag_count > 4:
            return "Наблюдаемый паттерн: в ответах часто пропускаются ограничения, контрольные точки и обязательные элементы структуры, что снижает надежность интерпретации."
        return "Наблюдаемый паттерн: по текущей сессии ответов пока недостаточно для уверенного описания устойчивой модели поведения."

    if avg_block_coverage < 50:
        return "Наблюдаемый паттерн: пользователь чаще предлагает содержательные идеи, чем оформляет их в полную структуру ответа с критериями, ролями и следующим шагом."
    if avg_artifact_compliance < 50:
        return "Наблюдаемый паттерн: пользователь ориентируется на решение задачи, но не всегда оформляет ответ в ожидаемый формат артефакта кейса."
    if evidence_hit_rate < 0.5:
        return "Наблюдаемый паттерн: ответы содержат общую логику решения, но наблюдаемые действия и формулировки навыков проявляются недостаточно явно."
    if avg_red_flag_count > 2:
        return "Наблюдаемый паттерн: пользователь в целом движется к решению, но регулярно упускает ограничения, контрольные точки или важные элементы проверки."
    return "Наблюдаемый паттерн: ответы в целом структурированы, содержательны и ближе к рабочему формату принятия решения, чем к общим рассуждениям."


def build_ai_insight_copy(
    strongest_name: str | None,
    strongest_value: int | float | None,
    *,
    has_manifested_results: bool,
    has_interpretation_signal: bool,
    has_confident_strongest: bool,
    response_pattern: str,
) -> tuple[str, str]:
    if (
        strongest_name
        and strongest_value is not None
        and has_manifested_results
        and has_interpretation_signal
        and has_confident_strongest
        and float(strongest_value) > 0
    ):
        return (
            f"Сильная сторона — {strongest_name}",
            "Наиболее выраженный показатель зафиксирован по направлению "
            f"«{strongest_name}». Средний интегральный результат по связанным навыкам составил "
            f"{round(float(strongest_value))}%, а качество сигнала подтверждено структурой ответа и найденными evidence.\n\n"
            f"{response_pattern}",
        )

    return (
        "AI insights пока недоступны",
        "По последней сессии пока не удалось выделить достаточно уверенную доминирующую компетенцию. "
        "После повторного прохождения с более содержательными и структурированными ответами здесь появится аналитический вывод.\n\n"
        f"{response_pattern}",
    )


def get_competency_dominant_deficit(metrics: dict | None) -> str:
    metrics = metrics or {}
    for deficit_code, predicate in DEFICIT_PRIORITY:
        if predicate(metrics):
            return deficit_code
    return "generic"


def build_competency_growth_recommendation(competency_name: str, metrics: dict | None) -> str:
    deficit = get_competency_dominant_deficit(metrics)
    competency_map = COMPETENCY_GROWTH_RECOMMENDATIONS.get(
        competency_name,
        COMPETENCY_GROWTH_RECOMMENDATIONS["Критическое мышление"],
    )
    return competency_map.get(deficit) or competency_map["generic"]

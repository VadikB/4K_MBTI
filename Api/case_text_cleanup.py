from __future__ import annotations

import re
from typing import Iterable


COMMON_TEXT_REPLACEMENTS = {
    " ланир": " планир",
    " Ланир": " Планир",
    "измеен": "изменен",
    "поддряд": "подряд",
    " согласоваан": " согласован",
    " несогласс": " несоглас",
    " повтр": " повтор",
    " комппани": " компании",
    " кеайс": " кейс",
    " кейсво": " кейсов",
    " обученеи": " обучение",
    " обученя": " обучения",
    " сотруднки": " сотрудники",
    " руковдитель": " руководитель",
    " прогрм": " программ",
    " следуюший": " следующий",
    " следущий": " следующий",
    " огранчи": " огранич",
    " метрикке": " метрике",
    " возращ": " возвращ",
    " согласво": " согласов",
    "Это может": "Это может",
    "Пока неясно": "Пока неясно",
}


def cleanup_case_text(text: str | None) -> str:
    value = str(text or "").strip()
    if not value:
        return ""

    for source, target in COMMON_TEXT_REPLACEMENTS.items():
        value = value.replace(source, target)

    value = value.replace(" ,", ",")
    value = value.replace(" .", ".")
    value = value.replace(" ;", ";")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"[ \t]*\n[ \t]*", "\n", value)
    value = re.sub(r"([,.;:!?])\1+", r"\1", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"([,.;:!?])([^\s\n])", r"\1 \2", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"\b(и)\s+\1\b", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(что)\s+\1\b", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(по)\s+\1\b", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"\bв роли\s+Линейный сотрудник\b", "в роли линейного сотрудника", value)
    value = re.sub(r"\bв роли\s+Менеджер\b", "в роли менеджера", value)
    value = re.sub(r"\bв роли\s+Лидер\b", "в роли лидера", value)
    value = re.sub(r"\bк карточка\b", "к карточке", value)
    value = re.sub(r"\bпо вопросу сбой\b", "по вопросу сбоя", value)
    value = re.sub(r"\bпо вопросу отсутствие\b", "по вопросу отсутствия", value)
    value = re.sub(r"\bчасть работы действительно велась\b", "часть работы действительно была выполнена", value)
    value = re.sub(r"\bследущий\b", "следующий", value, flags=re.IGNORECASE)
    value = re.sub(r"\bследуюший\b", "следующий", value, flags=re.IGNORECASE)
    value = re.sub(r"\bклиентской поддержки и 1 смежный координатор на эскалациях\b", "2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях", value, flags=re.IGNORECASE)
    value = re.sub(r"\bклиентская поддержка и сопровождение обращений к клиент ждет\b", "в процессе клиентской поддержки клиент ждет", value, flags=re.IGNORECASE)
    value = re.sub(r"\bвокруг обновление клиента\b", "вокруг обновления клиента", value, flags=re.IGNORECASE)
    value = re.sub(r"\bдля клиент\b", "для клиента", value, flags=re.IGNORECASE)
    value = re.sub(r"\bЭто касается \*\*дневная\b", "Это касается **дневной", value, flags=re.IGNORECASE)
    value = re.sub(r"\bбудут заметны для клиент\b", "будут заметны для клиента", value, flags=re.IGNORECASE)
    value = re.sub(r"\bважно прояснить подтвердить владельца обращения и дать клиенту реалистичное обновление\b", "важно прояснить, кто отвечает за обращение, и дать клиенту реалистичное обновление", value, flags=re.IGNORECASE)
    value = re.sub(r"\bиз-за этого у клиента тормозится подтвердить владельца обращения и дать клиенту реалистичное обновление\b", "из-за этого клиент не получает понятного следующего шага и подтвержденного обновления", value, flags=re.IGNORECASE)
    value = re.sub(r"\bпо обращениям клиентов часть статусов уже обновлена, но подтвержденный результат и следующий шаг фиксируются не полностью сейчас\b", "по обращениям клиентов часть статусов уже обновлена, но подтвержденный результат и следующий шаг фиксируются не полностью. Сейчас", value, flags=re.IGNORECASE)
    value = re.sub(r"\bчто уже угрожает результату и доверию\b", "что уже мешает договориться и удерживать рабочий контакт", value, flags=re.IGNORECASE)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


def cleanup_case_list(values: Iterable[str] | str | None, *, limit: int | None = None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = re.split(r"[,;\n]+", values)
    else:
        raw_values = list(values)

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = cleanup_case_text(str(raw or "").strip(" -—\t\"'«»"))
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if limit is not None and len(cleaned) >= limit:
            break
    return cleaned


def join_case_list(values: Iterable[str] | str | None, *, limit: int | None = None) -> str:
    items = cleanup_case_list(values, limit=limit)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} и {items[1]}"
    return f"{', '.join(items[:-1])} и {items[-1]}"

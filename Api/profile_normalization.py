from __future__ import annotations

import re
from dataclasses import dataclass


NO_CHANGES_VALUES = {
    "изменений нет",
    "нет изменений",
    "нет измеенний",
    "не изменилось",
    "не изменений",
    "без изменений",
}

LEADING_DUTY_PATTERNS = (
    r"^(?:я\s+)?(?:выполняю|занимаюсь|отвечаю\s+за|в\s+мои\s+обязанности\s+входит(?:\s*[:\-])?|мои\s+обязанности(?:\s*[-:])?)\s+",
    r"^(?:непосредственно\s+)?(?:обязан|обязана)\s+",
)

NOMINALIZATION_PATTERNS = (
    (r"^организую\b", "Организация"),
    (r"^контролирую\b", "Контроль"),
    (r"^анализирую\b", "Анализ"),
    (r"^готовлю\b", "Подготовка"),
    (r"^формулирую\b", "Формулирование"),
    (r"^декомпозирую\b", "Декомпозиция"),
    (r"^распределяю\b", "Распределение"),
    (r"^приоритизирую\b", "Приоритизация"),
    (r"^управляю\b", "Управление"),
    (r"^синхронизирую\b", "Синхронизация"),
    (r"^координирую\b", "Координация"),
    (r"^обеспечиваю\b", "Обеспечение"),
    (r"^согласовываю\b", "Согласование"),
    (r"^сопровождаю\b", "Сопровождение"),
    (r"^мониторю\b", "Мониторинг"),
    (r"^проверяю\b", "Проверка"),
    (r"^веду\b", "Ведение"),
    (r"^оцениваю\b", "Оценка"),
    (r"^разрабатываю\b", "Разработка"),
    (r"^участвую\s+в\b", "Участие в"),
    (r"^отвечаю\s+за\b", "Ответственность за"),
)

NOMINALIZATION_PHRASE_FIXES = (
    (r"\bОрганизация работу\b", "Организация работы"),
    (r"\bКонтроль сроки\b", "Контроль сроков"),
    (r"\bАнализ причины\b", "Анализ причин"),
    (r"\bПодготовка отчеты\b", "Подготовка отчетов"),
    (r"\bОрганизация работы([^,]*),\s*распределяю\b", r"Организация работы\1 и распределение"),
    (r"\bраспределение обращения\b", "распределение обращений"),
    (r"\bФормулирование цели\b", "Формулирование целей"),
    (r"\bДекомпозиция работ\b", "Декомпозиция работ"),
    (r"\bПодготовка отчетов([^,]*?)\s+и\s+участвую\s+в\b", r"Подготовка отчетов\1 и участие в"),
)


@dataclass(slots=True)
class ProfileNormalizationResult:
    cleaned_position: str | None
    normalized_company_industry_fallback: str | None
    normalized_duties_items: list[str]
    normalized_duties_text: str | None
    source_text: str


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9\s-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def clean_position(position: str | None) -> str | None:
    if not position:
        return None
    cleaned = " ".join(position.split())
    return cleaned or None


def normalize_company_industry_fallback(company_industry: str | None) -> str | None:
    cleaned = normalize_text(company_industry)
    if not cleaned:
        return None

    mapping = [
        (("банк", "финанс", "страх", "инвест"), "финансовых услуг"),
        (("it", "айти", "разработк", "продукт", "цифров", "saas", "software"), "информационных технологий"),
        (("ритейл", "рознич", "магазин", "ecommerce", "маркетплейс"), "розничной торговли"),
        (("логист", "склад", "достав", "транспорт"), "логистики и транспорта"),
        (("телеком", "связ", "оператор"), "телекоммуникаций"),
        (("медиц", "здрав", "фарма", "клиник"), "здравоохранения и фармацевтики"),
        (("образован", "обучен", "университет", "школ"), "образования"),
        (("производ", "завод", "фабрик", "промышл"), "производства"),
        (("строит", "девелоп", "недвиж"), "строительства и недвижимости"),
        (("госс", "государ", "муницип", "бюджет"), "государственного сектора"),
        (("энерг", "нефт", "газ", "электр"), "энергетики"),
        (("агро", "сельск", "ферм"), "агропромышленного комплекса"),
        (("hr", "персонал", "рекрут"), "кадровых и HR-услуг"),
        (("маркет", "реклам", "бренд", "pr"), "маркетинга и рекламы"),
    ]
    for hints, label in mapping:
        if any(hint in cleaned for hint in hints):
            return label

    return company_industry.strip() if company_industry and company_industry.strip() else None


def cleanup_duty_item(item: str) -> str | None:
    cleaned = item.strip(" \t\n\r-•—,;:.")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    for pattern in LEADING_DUTY_PATTERNS:
        lowered = re.sub(pattern, "", lowered, flags=re.IGNORECASE)
    lowered = lowered.strip(" \t\n\r-•—,;:.")
    if len(lowered) < 3:
        return None
    nominalized = lowered
    for pattern, replacement in NOMINALIZATION_PATTERNS:
        nominalized = re.sub(pattern, replacement, nominalized, count=1, flags=re.IGNORECASE)
        if nominalized != lowered:
            break
    for pattern, replacement in NOMINALIZATION_PHRASE_FIXES:
        nominalized = re.sub(pattern, replacement, nominalized, flags=re.IGNORECASE)
    return nominalized[0].upper() + nominalized[1:]


def dedupe_text_items(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = cleanup_duty_item(item)
        if not cleaned:
            continue
        key = normalize_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def fallback_normalize_duties_items(duties: str | None) -> list[str]:
    if not duties:
        return []
    text = duties.replace("\r", "\n")
    text = re.sub(r"[•●▪]", "\n", text)
    text = re.sub(r"\s*;\s*", "\n", text)
    text = re.sub(r"\.\s+", "\n", text)
    text = re.sub(
        r"\s*,\s*(?=(?:контрол|коорди|вед|готов|соглас|анализ|управ|обеспеч|разраб|формир|планир|провод|отвеч|организ|сопровож|монитор|провер))",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    raw_items = [segment for segment in text.split("\n") if segment.strip()]
    return dedupe_text_items(raw_items)


def format_duties_items(items: list[str]) -> str | None:
    normalized = dedupe_text_items(items)
    if not normalized:
        return None
    return "\n".join(f"- {item}" for item in normalized)


def parse_bullets(value: str | None) -> list[str]:
    if not value:
        return []
    chunks = re.split(r"[\n\r]+|•\t?|•|-\s+", value)
    items: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        cleaned = chunk.strip(" \t-•—")
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            continue
        key = normalize_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
    return items


def normalize_profile_text(value: str | None, *, fallback: str) -> str:
    cleaned = (value or "").strip()
    lowered = cleaned.lower()
    if not cleaned or lowered in NO_CHANGES_VALUES:
        return fallback
    return cleaned


def build_profile_normalization_result(
    *,
    position: str | None,
    duties: str | None,
    normalized_duties: str | None,
    company_industry: str | None,
) -> ProfileNormalizationResult:
    cleaned_position = clean_position(position)
    duties_items = fallback_normalize_duties_items(duties)
    duties_text = normalized_duties or format_duties_items(duties_items)
    source_text = normalize_text(" ".join(filter(None, [cleaned_position or "", duties or "", duties_text or ""])))
    return ProfileNormalizationResult(
        cleaned_position=cleaned_position,
        normalized_company_industry_fallback=normalize_company_industry_fallback(company_industry),
        normalized_duties_items=duties_items,
        normalized_duties_text=duties_text,
        source_text=source_text,
    )

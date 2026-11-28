"""Validate explicit numeric division and source units before semantic review."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
import re


_GROUP_SPACE = " \u00a0\u202f"
_VALUE = rf"[-−]?(?:[0-9]{{1,3}}(?:[{_GROUP_SPACE}][0-9]{{3}}){{1,5}}|[0-9]{{1,18}})(?:[,.][0-9]{{1,8}})?"
_LEFT = r"(?<![\w.,/−–-])"
_RIGHT = r"(?![\w/−–-]|[.,][0-9])"
_DIVISION = re.compile(rf"{_LEFT}(?P<numerator>{_VALUE})\s*[/÷]\s*(?P<denominator>{_VALUE})\s*=\s*(?P<result>{_VALUE}){_RIGHT}")
_NUMBER = re.compile(rf"{_LEFT}{_VALUE}{_RIGHT}")
CLOCK = r"(?:[01]?[0-9]|2[0-3]):[0-5][0-9]"
_WINDOW_DURATION = re.compile(
    rf"\bокно\s*(?:[:—–-]\s*)?(?:[а-яё]+[ \t]+){{0,3}}"
    rf"(?P<start>{CLOCK})\s*[—–-]\s*(?P<end>{CLOCK}),\s*длительность\s*(?:[:—–-]\s*)?"
    rf"(?P<duration>{_VALUE})\s+(?P<unit>час(?:а|ов)?|минут(?:а|ы)?)\b", re.IGNORECASE,
)
_SMALL_NUMBERS = {
    word: Decimal(number)
    for number, words in enumerate(("ноль нуля", "один одна одно одной одного одну", "два две двух",
        "три трех трёх", "четыре четырех четырёх", "пять пяти", "шесть шести", "семь семи", "восемь восьми",
        "девять девяти", "десять десяти", "одиннадцать одиннадцати", "двенадцать двенадцати"))
    for word in words.split()
}


def _decimal(value: str) -> Decimal:
    return Decimal(value.translate(str.maketrans(",−", ".-", _GROUP_SPACE)))


def _rounded_quotient(numerator: Decimal, denominator: Decimal, result: Decimal) -> Decimal | None:
    with localcontext() as context:
        context.prec = 60
        precision = Decimal(1).scaleb(result.as_tuple().exponent)
        return (numerator / denominator).quantize(precision, rounding=ROUND_HALF_UP) if denominator else None


def division_findings(document: str) -> list[dict]:
    """Require separate facts for bare operands and recompute the printed quotient."""
    equations = list(_DIVISION.finditer(document))
    if not equations:
        return []
    # A result acquires an independent basis only after its own expression passes.
    independent = _DIVISION.sub(" ", document)
    available = {_decimal(match.group()) for match in _NUMBER.finditer(independent)}
    available.update(_SMALL_NUMBERS[word] for word in re.findall(r"[^\W\d_]+", independent.casefold())
                     if word in _SMALL_NUMBERS)
    findings = []
    for expression in equations:
        numerator = _decimal(expression["numerator"])
        denominator = _decimal(expression["denominator"])
        result = _decimal(expression["result"])
        missing = [expression[key] for key, value in (("numerator", numerator), ("denominator", denominator))
                   if value not in available]
        if missing:
            findings.append({"code": "battery_division_basis", "expression": expression.group(), "missing": missing})
        expected = _rounded_quotient(numerator, denominator, result)
        if expected != result:
            findings.append({"code": "battery_division_result", "expression": expression.group(),
                             "expected_result": str(expected) if expected is not None else None})
        elif not missing:
            available.add(result)
    return findings


_QUANTITY_UNITS = {
    "applications": r"заяв(?:ка|ки|ок|ку|ке|кой|кам|ками|ках)",
    "person_days": r"человеко[-‐‑–]д(?:ень|ня|ней|ню|нём|нем|ням|нями|нях)",
    "work_days": r"рабоч(?:ий|их|ие|ими|им|его|ему|ем)\s+д(?:ень|ня|ней|ню|нём|нем|ням|нями|нях)",
    "calendar_days": r"календарн(?:ый|ых|ые|ыми|ым|ого|ому|ом)\s+д(?:ень|ня|ней|ню|нём|нем|ням|нями|нях)",
    "days": r"д(?:ень|ня|ней|ню|нём|нем|ням|нями|нях)",
    "people": r"сотрудник(?:а|ов|ам|ами|ах|у|ом|е|и)?|специалист(?:а|ов|ам|ами|ах|у|ом|е|ы)?|человек(?:а|у|ом|е)?",
    "hours": r"час(?:а|ов|ам|ами|ах|у|ом|е|ы)?",
    "minutes": r"минут(?:а|ы|у|ой|ам|ами|ах|е)?",
    "shifts": r"смен(?:а|ы|у|ой|ам|ами|ах|е)?",
}
_QUANTITY_UNIT = "(?:" + "|".join(_QUANTITY_UNITS.values()) + ")"
_UNIT_BY_TEXT = [(kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in _QUANTITY_UNITS.items()]
_BASIS_NUMBERS = {
    **_SMALL_NUMBERS,
    **{word: Decimal(value)
       for value, words in {
           13: "тринадцать тринадцати", 14: "четырнадцать четырнадцати",
           15: "пятнадцать пятнадцати", 16: "шестнадцать шестнадцати",
           17: "семнадцать семнадцати", 18: "восемнадцать восемнадцати",
           19: "девятнадцать девятнадцати", 20: "двадцать двадцати", 30: "тридцать тридцати",
           40: "сорок сорока", 50: "пятьдесят пятидесяти", 60: "шестьдесят шестидесяти",
           70: "семьдесят семидесяти", 80: "восемьдесят восьмидесяти", 90: "девяносто девяноста",
           100: "сто ста", 500: "пятьсот пятисот",
       }.items() for word in words.split()},
}
_TENS = "|".join(word for word, value in _BASIS_NUMBERS.items() if 20 <= value < 100)
_ONES = "|".join(word for word, value in _BASIS_NUMBERS.items() if 0 < value < 10)
_QUANTITY_NUMBER = rf"(?:{_VALUE}|(?:{_TENS})[ \t]+(?:{_ONES})|{'|'.join(_BASIS_NUMBERS)})"
_QUANTITY = re.compile(rf"{_LEFT}(?P<value>{_QUANTITY_NUMBER})\s+(?P<unit>{_QUANTITY_UNIT})\b", re.IGNORECASE)
_MATERIAL_ID = r"(?:[MМ][0-9]{2}|[PР]00)"
_MATERIAL_REF = re.compile(rf"\b{_MATERIAL_ID}\b", re.IGNORECASE)
_BASIS_DIVISION = re.compile(
    rf"{_LEFT}(?P<numerator>{_VALUE})(?:[ \t]+(?P<numerator_unit>{_QUANTITY_UNIT})\b)?"
    rf"(?:[ \t]*\((?:(?:из|по)\s+)?(?P<numerator_ref>{_MATERIAL_ID})\))?\s*[/÷]\s*"
    rf"(?P<denominator>{_VALUE})(?:[ \t]+(?P<denominator_unit>{_QUANTITY_UNIT})\b)?"
    rf"(?:[ \t]*\((?:(?:из|по)\s+)?(?P<denominator_ref>{_MATERIAL_ID})\))?\s*=\s*(?P<result>{_VALUE}){_RIGHT}"
    rf"(?:[ \t]+(?P<result_unit>{_QUANTITY_UNIT})\b(?:[ \t]*(?:в|на|/)[ \t]*(?P<rate_unit>{_QUANTITY_UNIT})\b)?)?",
    re.IGNORECASE,
)
_ASSERTED_RATIO = re.compile(
    rf"{_LEFT}(?P<result>{_VALUE})[ \t]+(?P<result_unit>{_QUANTITY_UNIT})\b"
    rf"[ \t]+(?:в|на)[ \t]+(?P<rate_unit>{_QUANTITY_UNIT})\b"
    rf"[ \t]+(?:получен[оа]?|вычислен[оа]?)\s+как\s+отношение\s+(?:[а-яё]+[ \t]+){{0,4}}"
    rf"(?P<numerator>{_VALUE})[ \t]+(?P<numerator_unit>{_QUANTITY_UNIT})\b"
    rf"[ \t]+к\s+(?:[а-яё]+[ \t]+){{0,4}}(?P<denominator>{_VALUE})"
    rf"[ \t]+(?P<denominator_unit>{_QUANTITY_UNIT})\b",
    re.IGNORECASE,
)
_CLAUSE_BREAK = re.compile(r"(?<=[.!?;])[ \t]+|\n+")
_REFERENCE_TAIL = rf"{_MATERIAL_ID}(?:[ \t]*(?:,|и|/)[ \t]*{_MATERIAL_ID})*"
_BASE_REFERENCE = re.compile(
    rf"\b(?:из|по|согласно|в|источник(?:и|ом)?)\s*(?:[:—–-]\s*)?"
    rf"(?:данным\s+|данных\s+|документ(?:а|е|у)?\s+|материал(?:а|е|у)?\s+|из\s+|отч[её]т(?:а|е|у)?\s+)*"
    rf"(?P<ids>{_REFERENCE_TAIL})\b|\((?:см\.\s*)?(?P<parenthetical>{_REFERENCE_TAIL})\)", re.IGNORECASE,
)
_DAY_KINDS = {"days", "work_days", "calendar_days"}


def _unit_kind(text: str | None) -> str | None:
    if text:
        return next((kind for kind, pattern in _UNIT_BY_TEXT if pattern.fullmatch(text)), None)
    return None


def _quantity_number(text: str) -> Decimal:
    if text[0].isalpha():
        return sum(_BASIS_NUMBERS[word] for word in text.casefold().split())
    return _decimal(text)


def _material_id(text: str) -> str:
    return text.upper().translate(str.maketrans("МР", "MP"))


def _quantities(document: str) -> list[tuple[Decimal, str]]:
    # Equations are claims to verify. Their operands cannot cite themselves.
    independent = _BASIS_DIVISION.sub(" ", _ASSERTED_RATIO.sub(" ", document))
    return [(_quantity_number(match["value"]), _unit_kind(match["unit"])) for match in _QUANTITY.finditer(independent)]


def _basis_relation(kind: str, required: str) -> str:
    if kind == required or required == "days" and kind in _DAY_KINDS:
        return "match"
    if kind == "days" and required in _DAY_KINDS:
        return "unknown"
    return "incompatible"


def _allowed_basis(claim: re.Match, operand: str, document_id: str, context_refs: set[str],
                   available: dict[str, list[tuple[Decimal, str]]], required: str | None) -> dict:
    ref = claim.groupdict().get(operand + "_ref")
    refs = {_material_id(ref)} if ref else {document_id, *context_refs}
    number = _decimal(claim[operand])
    sources = {key: sorted({unit for value, unit in available[key] if value == number})
               for key in sorted(refs & available.keys())}
    sources = {key: units for key, units in sources.items() if units}
    kinds = {unit for units in sources.values() for unit in units}
    stated = _unit_kind(claim[operand + "_unit"])
    if required is None or refs - available.keys():
        status = "REVIEW_REQUIRED"
    elif stated and _basis_relation(stated, required) == "incompatible":
        status = "INCOMPATIBLE"
    else:
        relations = {_basis_relation(kind, required) for kind in kinds}
        if relations == {"match"}:
            status = "SUPPORTED"
        else:
            status = "INCOMPATIBLE" if relations == {"incompatible"} else "REVIEW_REQUIRED"
    return {"value": str(number), "required_unit": required, "stated_unit": stated,
            "referenced_materials": sorted(refs), "sources": sources, "status": status}


def quantity_basis_division_checks(document_id: str, available_documents: dict[str, str]) -> list[dict]:
    """Check explicit division against stated units and only participant-accessible sources.

    Unparsed, absent and equivocal bases remain visible to semantic reviewers.
    Object, period, status and source intent always require their own review.
    """
    document = available_documents.get(document_id, "")
    claims = sorted([*_BASIS_DIVISION.finditer(document), *_ASSERTED_RATIO.finditer(document)],
                    key=lambda item: item.start())
    if not claims:
        return []
    available = {key: _quantities(text) for key, text in available_documents.items()}
    breaks = list(_CLAUSE_BREAK.finditer(document))
    checks = []
    for claim in claims:
        preceding = [item for item in breaks if item.end() <= claim.start()]
        start = preceding[-1].end() if preceding else 0
        end = next((item.start() for item in breaks if item.start() >= claim.end()), len(document))
        context = document[start:end]
        if preceding:
            prior = document[preceding[-2].end() if len(preceding) > 1 else 0:preceding[-1].start()]
            if _BASE_REFERENCE.match(prior.lstrip()):
                context = prior + "\n" + context
        refs = {_material_id(ref.group()) for anchor in _BASE_REFERENCE.finditer(context)
                for ref in _MATERIAL_REF.finditer(anchor["ids"] or anchor["parenthetical"])}
        result = _decimal(claim["result"])
        numerator = _decimal(claim["numerator"])
        denominator = _decimal(claim["denominator"])
        expected = _rounded_quotient(numerator, denominator, result)
        if expected != result:
            checks.append({"code": "battery_division_result", "status": "FAIL", "expression": claim.group(),
                           "expected_result": str(expected) if expected is not None else None})
        rate_unit = _unit_kind(claim["rate_unit"])
        basis = {
            "numerator": _allowed_basis(claim, "numerator", document_id, refs, available,
                                        _unit_kind(claim["result_unit"]) if rate_unit else None),
            "denominator": _allowed_basis(claim, "denominator", document_id, refs, available, rate_unit),
        }
        statuses = {item["status"] for item in basis.values()}
        if "INCOMPATIBLE" in statuses:
            code, status = "battery_division_basis", "FAIL"
        else:
            code = "battery_division_provenance"
            status = "PASS" if statuses == {"SUPPORTED"} else "REVIEW_REQUIRED"
        checks.append({"code": code, "status": status, "expression": claim.group(), "basis": basis})
    return checks


def clock_minutes(clock: str) -> int:
    hours, minutes = map(int, clock.split(":"))
    return 60 * hours + minutes


def window_duration_findings(document: str) -> list[dict]:
    """Check one clock interval and duration explicitly paired in the same clause."""
    findings = []
    for claim in _WINDOW_DURATION.finditer(document):
        available = clock_minutes(claim["end"]) - clock_minutes(claim["start"])
        # Same-day intervals have an ordered start and end. Calendar transitions
        # and timelines assembled from separate role statements are reviewed separately.
        if available <= 0:
            continue
        duration = _decimal(claim["duration"])
        minutes = duration * 60 if claim["unit"].lower().startswith("час") else duration
        if minutes > available:
            findings.append({"code": "battery_window_duration_exceeds", "claim": claim.group(),
                             "available_minutes": available, "duration_minutes": str(minutes)})
    return findings

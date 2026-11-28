"""Validate explicit numeric division in a source document before semantic review."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
import re


_GROUP_SPACE = " \u00a0\u202f"
_VALUE = rf"[-−]?(?:[0-9]{{1,3}}(?:[{_GROUP_SPACE}][0-9]{{3}}){{1,5}}|[0-9]{{1,18}})(?:[,.][0-9]{{1,8}})?"
_LEFT = r"(?<![\w.,/−–-])"
_RIGHT = r"(?![\w/−–-]|[.,][0-9])"
_DIVISION = re.compile(rf"{_LEFT}(?P<numerator>{_VALUE})\s*[/÷]\s*(?P<denominator>{_VALUE})\s*=\s*(?P<result>{_VALUE}){_RIGHT}")
_NUMBER = re.compile(rf"{_LEFT}{_VALUE}{_RIGHT}")
_SMALL_NUMBERS = {
    word: Decimal(number)
    for number, words in enumerate(("ноль нуля", "один одна одно одной одного одну", "два две двух",
        "три трех трёх", "четыре четырех четырёх", "пять пяти", "шесть шести", "семь семи", "восемь восьми",
        "девять девяти", "десять десяти", "одиннадцать одиннадцати", "двенадцать двенадцати"))
    for word in words.split()
}


def _decimal(value: str) -> Decimal:
    return Decimal(value.translate(str.maketrans(",−", ".-", _GROUP_SPACE)))


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
        with localcontext() as context:
            context.prec = 60
            precision = Decimal(1).scaleb(result.as_tuple().exponent)
            expected = (numerator / denominator).quantize(precision, rounding=ROUND_HALF_UP) if denominator else None
        if expected != result:
            findings.append({"code": "battery_division_result", "expression": expression.group(),
                             "expected_result": str(expected) if expected is not None else None})
        elif not missing:
            available.add(result)
    return findings

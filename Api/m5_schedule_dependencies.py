"""Check a role's explicit promise about a same-window handoff."""
from __future__ import annotations

from decimal import Decimal
import re

from Api.m5_source_calculations import CLOCK, clock_minutes


_CLOCK_RANGE = rf"(?P<start>{CLOCK})\s*[—–-]\s*(?P<end>{CLOCK})"
_WINDOW = re.compile(
    rf"\bокно для итогового действия\s*[—–:-]\s*(?:рабочий день|пятница)?\s*{_CLOCK_RANGE},\s*"
    r"длительность\s+(?P<duration>[0-9]{1,3}(?:[,.][0-9]{1,2})?)\s+"
    r"(?P<unit>час(?:а|ов)?|минут(?:а|ы)?)\b",
    re.IGNORECASE,
)
_FULL_DEPENDENCY = re.compile(
    r"\bитогов(?:ую часть|ое действие)\s+(?:могу готовить|могу начать|начинаю|начну|готовлю)\s+"
    r"(?:(?:только|лишь)\s+)?после получения обоих (?:профильных )?(?:входов|подтверждений)\b",
    re.IGNORECASE,
)
_PROMISED_HANDOFF = re.compile(
    rf"\bмне нужно получить оба (?:профильных )?(?:входа|подтверждения) (?:до|к) (?P<handoff>{CLOCK})"
    rf"(?: пятницы)?, чтобы успеть к сроку (?P<deadline>{CLOCK})(?=[.!?]|[»”\"]?\s*$)",
    re.IGNORECASE,
)


def handoff_finding(document: str, role_id: str) -> dict | None:
    """Check a single explicit assurance with a fully dependent action in the same role statement.

    The reviewers reconcile calendar days, other work windows, partial action
    and status options from the complete set of documents.
    """
    statement = re.compile(rf"^\s*{re.escape(role_id)}\s*:\s*(.+)$")
    rows = [match[1] for row in document.splitlines() if (match := statement.match(row))]
    if len(rows) != 1:
        return None
    role_text = rows[0]
    window = _WINDOW.search(role_text)
    promise = _PROMISED_HANDOFF.search(role_text)
    if not (window and promise and _FULL_DEPENDENCY.search(role_text)):
        return None
    if len(list(re.finditer(_CLOCK_RANGE, role_text))) != 1:
        return None
    start = clock_minutes(window["start"])
    end = min(clock_minutes(window["end"]), clock_minutes(promise["deadline"]))
    handoff = clock_minutes(promise["handoff"])
    if end <= start or handoff > clock_minutes(window["end"]):
        # The reviewer establishes the calendar if the printed clocks may refer to different days.
        return None
    duration = Decimal(window["duration"].replace(",", "."))
    if window["unit"].casefold().startswith("час"):
        duration *= 60
    if duration > end - start or duration <= end - max(start, handoff):
        return None
    latest_handoff = int(end - duration)
    return {
        "code": "battery_handoff_after_latest_start",
        "role": role_id,
        "claim": promise.group(),
        "window": window.group(),
        "duration_minutes": str(duration),
        "minutes_available_after_handoff": end - max(start, handoff),
        "latest_handoff": f"{latest_handoff // 60:02d}:{latest_handoff % 60:02d}",
    }

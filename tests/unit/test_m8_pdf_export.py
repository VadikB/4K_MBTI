"""Real PDF checks for the saved projection and fail-closed renderer."""
from __future__ import annotations

from io import BytesIO
import re
import subprocess

import pytest
from pypdf import PdfReader

from Api.typst_pdf_renderer import TypstRenderError, render_typst_report


def participant_payload(*, score=0, partial=False, correction=None, long=False):
    name = "Понимание собеседника" + (" и бережная работа с очень длинным описанием контекста" * 4 if long else "")
    long_text = "Наблюдение подтверждено в сохранённом материале. " * 30 if long else "Основание вывода."
    return {
        "title": "Оценка 4К", "program_name": "Программа взаимодействия", "closed_at": "2026-11-17",
        "participant_name": "Участник", "correction": correction,
        "descriptive": {"status": "ready", "summary": ["Подтверждённое резюме."],
                        "claims": [{"kind": "observation", "text": long_text, "limitations": []}]},
        "processing": {"status": "completed"},
        "partial_result": {"is_incomplete": partial, "limitation_reasons": [{"message": "Наблюдений недостаточно."}] if partial else [],
                           "messages": {"title": "Оценка завершена не полностью"},
                           "progress": {"completed": 1, "planned": 2}} if partial else None,
        "radars": [{"name": "Коммуникация", "competency_id": "K1", "axes": [{"name": name, "current": score, "partial": partial}]}],
        "skills": [{"name": name, "competency": "Коммуникация", "competency_id": "K1", "description": long_text if long else "Описание навыка.",
                    "outcome": "Результат по части навыка" if partial else "Недостаточно оснований для результата" if score is None else "Результат по полному составу навыка",
                    "score": "—" if score is None else f"{score:g}", "value": score,
                    "partial": partial, "reasons": ["Наблюдений недостаточно."] if partial else []}],
        "limitations": ["Ограничение вывода."],
    }


@pytest.mark.parametrize("score,partial,correction,long", [
    (0, False, None, False),
    (2.5, True, None, False),
    (None, False, None, False),
    (3, False, None, True),
    (1, False, {"created_at": "2026-11-17", "reason": "Уточнено объяснение"}, False),
])
def test_real_participant_pdf_contains_projection(score, partial, correction, long):
    payload = participant_payload(score=score, partial=partial, correction=correction, long=long)
    pdf = render_typst_report(payload, "m8_participant_report_v2.typ")
    reader = PdfReader(BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) == (2 if long else 1)
    assert all(page.extract_text().strip() for page in reader.pages)
    for expected in ("Программа взаимодействия", "2026-11-17", "Понимание собеседника",
                     "Наблюдение подтверждено" if long else "Основание вывода.", "Ограничение вывода."):
        assert expected in text
    assert "0%" not in text and "revision" not in text and "coverage" not in text
    assert ("Числовых результатов пока нет" in text) == (score is None)
    if score is not None:
        assert f"{score:g} из 3" in text
    if partial:
        assert "Наблюдений недостаточно." in text
    if correction:
        assert correction["reason"] in text


def test_real_comparison_pdf_never_invents_delta():
    payload = {
        "title": "Сравнение", "mode": "mixed",
        "previous": {"program_name": "Первая программа", "closed_at": "2026-10-01"},
        "current": {"program_name": "Вторая программа", "closed_at": "2026-11-01"},
        "comparable": [{"skill_name": "Первый навык", "previous": 1.5, "current": 2, "difference": .5}],
        "separate": [{"skill_name": "Второй навык", "previous": None, "current": 0,
                      "reason_text": "Сопоставимость не подтверждена."}],
        "radars": [{"name": "Сопоставимые навыки", "axes": [{"name": "Первый навык", "previous": 1.5, "current": 2}]}],
    }
    reader = PdfReader(BytesIO(render_typst_report(payload, "m8_report_comparison_v2.typ")))
    text = "\n".join(page.extract_text() for page in reader.pages)
    for expected in ("Первая программа", "Вторая программа", "Первый навык", "Второй навык",
                     "Сопоставимость не подтверждена.", "нет результата", "0 из 3"):
        assert expected in text
    assert "0%" not in text


def test_empty_report_pdf_has_explicit_state():
    payload = participant_payload(score=None)
    payload["program_name"] = None
    payload["radars"] = []
    payload["skills"] = []
    reader = PdfReader(BytesIO(render_typst_report(payload, "m8_participant_report_v2.typ")))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Результаты по навыкам пока недоступны" in text
    assert "Программа оценки не указана" in text
    assert "0%" not in text


def test_unsupported_comparison_has_no_comparable_chart():
    payload = {
        "title": "Сравнение", "mode": "separate",
        "previous": {"program_name": "Первая", "closed_at": "2026-10-01"},
        "current": {"program_name": "Вторая", "closed_at": "2026-11-01"},
        "comparable": [], "radars": [],
        "separate": [{"skill_name": "Навык", "previous": None, "current": 0,
                      "reason_text": "Сопоставимость не подтверждена."}],
    }
    reader = PdfReader(BytesIO(render_typst_report(payload, "m8_report_comparison_v2.typ")))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Сопоставимые навыки" not in text
    assert "Раздельные показатели" in text
    assert "нет результата" in text
    assert "0 из 3" in text


def test_typst_failure_never_falls_back_to_legacy():
    with pytest.raises(TypstRenderError, match="PDF_RENDER_FAILED"):
        render_typst_report({"title": "Нет C-67"}, "m8_participant_report_v2.typ")
    with pytest.raises(TypstRenderError, match="PDF_TEMPLATE_UNSUPPORTED"):
        render_typst_report({}, "m8_basic_report.typ")


def test_typst_timeout_kills_its_process_group(monkeypatch):
    from Api import typst_pdf_renderer as renderer
    killed = []

    class SlowWorker:
        pid = 12345
        def __init__(self):
            self.calls = 0
        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("typst", timeout)
            return b"", b""

    worker = SlowWorker()
    monkeypatch.setattr(renderer.subprocess, "Popen", lambda *args, **kwargs: worker)
    monkeypatch.setattr(renderer.os, "killpg", lambda pid, signal: killed.append(pid))
    with pytest.raises(TypstRenderError, match="PDF_RENDER_TIMEOUT"):
        render_typst_report({"title": "Тест"}, "m8_participant_report_v2.typ")
    assert killed == [worker.pid] and worker.calls == 2


def test_invalid_saved_radar_value_fails_closed():
    payload = participant_payload(score=1)
    payload["radars"][0]["axes"][0]["current"] = 99
    with pytest.raises(TypstRenderError, match="PDF_RADAR_INVALID"):
        render_typst_report(payload, "m8_participant_report_v2.typ")


def test_radar_runs_preserve_zero_gaps_and_close_only_complete_series(tmp_path):
    from Api.m8_pdf_radar import _runs, write_radars
    assert _runs([0, None, 2, 3]) == [([2, 3, 0], False)]
    assert _runs([0, 1, 2]) == [([0, 1, 2], True)]
    write_radars([{"axes": [{"current": value} for value in (0, 1, 2)]}], tmp_path)
    svg = (tmp_path / "radar-0.svg").read_text()
    points = re.search(r'<polyline points="([^"]+)', svg).group(1).split()
    assert len(points) == 4 and points[0] == points[-1]


@pytest.mark.parametrize("outcome,value,completeness", [
    ("full_score", 0, "full"), ("partial_score", 1.5, "partial"),
    ("result_without_score", None, None), ("no_result", None, None),
    ("full_score", 0, "partial"),
])
def test_public_labels_are_the_same_in_api_and_real_pdf(outcome, value, completeness):
    from copy import deepcopy
    from Api.m8_report_access import public_projection
    from Api.m8_results import render_pdf
    saved = {"id": "selected", "program_name": "Контрольная программа", "collection_closed_at": "2026-11-17",
             "c67": {"template_version": "m8-basic-report/1.5.0", "skills": [
                 {"skill_id": "S", "skill_name": "Контрольный навык", "outcome": outcome,
                  "score": None if value is None else {"value": value}, "completeness": completeness,
                  "presentation": {"reasons": [{"message": "Сохранённое ограничение навыка"}]}}],
                 "limitations": ["Skill Level is not derived from numeric Score", "Неизвестное ограничение"],
                 "descriptive": {"status": "ready", "summary": [], "claims": []}}}
    before = deepcopy(saved)
    view = public_projection(saved)["c67"]
    reader = PdfReader(BytesIO(render_pdf(saved)))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert view["skills"][0]["presentation"]["label"] in text
    for message in view["limitations"] + ["Сохранённое ограничение навыка", "Контрольная программа", "2026-11-17"]:
        assert message in text
    for technical in ("Skill Level", "Score", "full_score", "partial_score", "Полнота отдельно"):
        assert technical not in text
    assert text.count("Числовой показатель не определяет общий уровень владения навыком") == 1
    assert saved == before
    if value == 0:
        assert "0 из 3" in text

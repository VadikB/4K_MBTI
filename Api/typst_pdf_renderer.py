from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any


class TypstRenderError(RuntimeError):
    pass


class TypstUnavailableError(TypstRenderError):
    pass


def _render_with_reportlab(payload: dict[str, Any], template_name: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise TypstUnavailableError("ReportLab package was not found") from exc

    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    font_path = next((path for path in font_candidates if Path(path).exists()), None)
    font_name = "Helvetica"
    if font_path:
        font_name = "Agent4KUnicode"
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="AgentTitle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        spaceAfter=10,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="AgentHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=17,
        spaceBefore=8,
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="AgentBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="AgentMuted",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#667085"),
        spaceAfter=4,
    ))

    def esc(text: Any) -> str:
        return (
            str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

    story = []
    title = str(payload.get("title") or "Отчет")
    subtitle = str(payload.get("subtitle") or "").strip()
    story.append(Paragraph(esc(title), styles["AgentTitle"]))
    if subtitle:
        story.append(Paragraph(esc(subtitle), styles["AgentMuted"]))
        story.append(Spacer(1, 4))

    if template_name == "admin_reports.typ":
        summary = [
            ["Всего отчетов", str(payload.get("total_items") or "0")],
            ["Средний результат", str(payload.get("summary_score_label") or "Нет данных")],
        ]
        summary_table = Table(summary, colWidths=[55 * mm, 100 * mm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 10))
        for index, item in enumerate(payload.get("items") or [], start=1):
            story.append(Paragraph(esc(f"{index}. {item.get('full_name') or 'Без имени'}"), styles["AgentHeading"]))
            lines = [
                f"Роль: {item.get('role_name') or 'Не указана'}",
                f"Группа: {item.get('group_name') or 'Не указана'}",
                f"Статус: {item.get('status') or 'Не указан'}",
                f"Результат: {item.get('score_label') or '—'}",
                f"MBTI: {item.get('mbti_type') or 'Нет данных'}",
                f"Дата: {item.get('date_label') or 'Без даты'}",
            ]
            for line in lines:
                story.append(Paragraph(esc(line), styles["AgentBody"]))
            story.append(Spacer(1, 6))
    elif template_name == "admin_dialogue.typ":
        story.append(Paragraph(esc(f"Пользователь: {payload.get('full_name') or 'Без имени'}"), styles["AgentBody"]))
        story.append(Paragraph(esc(f"Роль: {payload.get('role_name') or 'Не указана'}"), styles["AgentBody"]))
        story.append(Paragraph(esc(f"Сессия: {payload.get('session_id') or '—'}"), styles["AgentBody"]))
        story.append(Spacer(1, 8))
        for case_item in payload.get("case_items") or []:
            story.append(Paragraph(esc(f"Кейс {case_item.get('case_number') or ''}. {case_item.get('case_title') or 'Кейс без названия'}"), styles["AgentHeading"]))
            if case_item.get("personalized_context"):
                story.append(Paragraph(esc(f"Контекст: {case_item.get('personalized_context')}"), styles["AgentBody"]))
            if case_item.get("personalized_task"):
                story.append(Paragraph(esc(f"Задача: {case_item.get('personalized_task')}"), styles["AgentBody"]))
            story.append(Spacer(1, 4))
            for message in case_item.get("dialogue") or []:
                role_label = message.get("role_label") or "Участник"
                message_text = message.get("message_text") or ""
                story.append(Paragraph(esc(f"{role_label}: {message_text}"), styles["AgentBody"]))
            story.append(Spacer(1, 8))
    else:
        user = payload.get("user") or {}
        insight = payload.get("insight") or {}
        story.append(Paragraph(esc(f"Пользователь: {user.get('full_name') or 'Без имени'}"), styles["AgentBody"]))
        story.append(Paragraph(esc(f"Должность: {user.get('job_description') or 'Не указана'}"), styles["AgentBody"]))
        story.append(Paragraph(esc(f"Телефон: {user.get('phone') or 'Не указан'}"), styles["AgentBody"]))
        story.append(Paragraph(esc(f"Общий результат: {payload.get('overall_score') or 0}%"), styles["AgentBody"]))
        story.append(Spacer(1, 8))
        if insight.get("title"):
            story.append(Paragraph(esc(insight.get("title")), styles["AgentHeading"]))
        if insight.get("text"):
            story.append(Paragraph(esc(insight.get("text")), styles["AgentBody"]))
        for section_title, key in (
            ("Основание интерпретации", "basis_items"),
            ("Сильные стороны", "strengths"),
            ("Зоны роста", "growth_areas"),
            ("Цитаты", "quotes"),
        ):
            items = payload.get(key) or []
            if not items:
                continue
            story.append(Paragraph(esc(section_title), styles["AgentHeading"]))
            for item in items:
                story.append(Paragraph(esc(f"• {item}"), styles["AgentBody"]))
        story.append(Paragraph("Компетенции", styles["AgentHeading"]))
        for competency in payload.get("competencies") or []:
            story.append(Paragraph(
                esc(f"{competency.get('name') or 'Компетенция'} — {competency.get('avg_percent') or 0}% ({competency.get('interpretation') or ''})"),
                styles["AgentBody"],
            ))
            for skill in competency.get("skills") or []:
                story.append(Paragraph(
                    esc(f"— {skill.get('name') or 'Навык'}: {skill.get('level') or 'Не определен'} ({skill.get('percent') or 0}%)"),
                    styles["AgentMuted"],
                ))
            story.append(Spacer(1, 4))

    doc.build(story)
    return buffer.getvalue()


def _typst_binary() -> str:
    configured_binary = os.getenv("AGENT4K_TYPST_BIN")
    if configured_binary:
        return configured_binary
    discovered_binary = shutil.which("typst")
    if discovered_binary:
        return discovered_binary
    raise TypstUnavailableError("Typst binary was not found")


def _font_paths() -> list[str]:
    fonts_path = Path(__file__).with_name("pdf_assets") / "fonts"
    return [str(fonts_path)] if fonts_path.exists() else []


def _render_with_python_package(source_path: Path, temp_dir: Path) -> bytes:
    try:
        import typst
    except ImportError as exc:
        raise TypstUnavailableError("Typst Python package was not found") from exc

    font_paths = _font_paths()
    try:
        return typst.compile(
            str(source_path),
            root=str(temp_dir),
            font_paths=font_paths,
            ignore_system_fonts=bool(font_paths),
        )
    except Exception as exc:
        raise TypstRenderError(str(exc)) from exc


def _render_with_cli(source_path: Path, output_path: Path, temp_dir: Path, timeout_seconds: float) -> bytes:
    typst_binary = _typst_binary()
    font_paths = _font_paths()
    command = [
        typst_binary,
        "compile",
        "--root",
        str(temp_dir),
    ]
    for font_path in font_paths:
        command.extend(["--font-path", font_path])
    if font_paths:
        command.append("--ignore-system-fonts")
    command.extend([str(source_path), str(output_path)])
    try:
        result = subprocess.run(
            command,
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TypstUnavailableError(f"Typst binary was not found: {typst_binary}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TypstRenderError(f"Typst rendering timed out after {timeout_seconds:g}s") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Typst failed without output").strip()
        raise TypstRenderError(message)
    if not output_path.exists():
        raise TypstRenderError("Typst did not produce a PDF output file")
    return output_path.read_bytes()


def render_typst_report(payload: dict[str, Any], template_name: str) -> bytes:
    engine = os.getenv("AGENT4K_PDF_ENGINE", "auto").strip().lower()
    if engine not in {"auto", "typst"}:
        raise TypstRenderError(f"Unsupported AGENT4K_PDF_ENGINE value: {engine}")

    template_path = Path(__file__).with_name("pdf_templates") / template_name
    if not template_path.exists():
        raise TypstRenderError(f"Typst template not found: {template_path}")

    timeout_seconds = float(os.getenv("AGENT4K_TYPST_TIMEOUT_SECONDS", "20"))
    with tempfile.TemporaryDirectory(prefix="agent4k-typst-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        source_path = temp_dir / template_name
        data_path = temp_dir / "report-data.json"
        output_path = temp_dir / "report.pdf"

        shutil.copyfile(template_path, source_path)
        data_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        try:
            return _render_with_python_package(source_path, temp_dir)
        except TypstUnavailableError:
            try:
                return _render_with_cli(source_path, output_path, temp_dir, timeout_seconds)
            except TypstUnavailableError:
                return _render_with_reportlab(payload, template_name)
        except TypstRenderError:
            return _render_with_reportlab(payload, template_name)


def render_typst_competency_report(payload: dict[str, Any]) -> bytes:
    return render_typst_report(payload, "competency_report.typ")


def render_typst_admin_reports(payload: dict[str, Any]) -> bytes:
    return render_typst_report(payload, "admin_reports.typ")


def render_typst_admin_dialogue(payload: dict[str, Any]) -> bytes:
    return render_typst_report(payload, "admin_dialogue.typ")

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


COMPETENCY_ORDER = [
    "Коммуникация",
    "Командная работа",
    "Креативность",
    "Критическое мышление",
]

COMPETENCY_FILE_CODES = {
    "Коммуникация": "communication",
    "Командная работа": "teamwork",
    "Креативность": "creativity",
    "Критическое мышление": "critical_thinking",
}


def _safe_filename_part(value: str | None, fallback: str = "user") -> str:
    raw_name = str(value or fallback)
    safe_name = "".join(ch if (ch.isascii() and (ch.isalnum() or ch in ("_", "-"))) else "_" for ch in raw_name)
    return safe_name.strip("_") or fallback


def _xml_text(value: str) -> str:
    return escape(value).replace("\n", "&#10;")


def _estimate_height_points(text: str, base: int = 18, max_height: int = 96) -> int:
    lines = max(1, len(text) // 95 + text.count("\n") + 1)
    return min(max_height, base + (lines - 1) * 12)


def _chunk_text_for_pdf(value: str | None, max_chars: int = 900) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return ["—"]
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(paragraph) > max_chars:
            split_at = paragraph.rfind(" ", 0, max_chars)
            if split_at <= 0:
                split_at = max_chars
            chunks.append(paragraph[:split_at].strip())
            paragraph = paragraph[split_at:].strip()
        current = paragraph
    if current:
        chunks.append(current)
    return chunks or ["—"]


def _cell(text: str = "", style: str | None = None, cell_type: str = "String") -> str:
    attrs = f' ss:StyleID="{style}"' if style else ""
    if text == "":
        return f"<Cell{attrs}/>"
    if cell_type == "Number":
        return f'<Cell{attrs}><Data ss:Type="Number">{text}</Data></Cell>'
    if cell_type == "Boolean":
        return f'<Cell{attrs}><Data ss:Type="Boolean">{text}</Data></Cell>'
    return f'<Cell{attrs}><Data ss:Type="String">{_xml_text(text)}</Data></Cell>'


def _row(cells: list[str], height: int | None = None) -> str:
    attrs = f' ss:AutoFitHeight="0" ss:Height="{height}"' if height else ""
    return f"<Row{attrs}>{''.join(cells)}</Row>"


class AdminReportExpertExportService:
    _COMPLETED_CASE_STATUSES = {"answered", "assessed", "completed"}

    def _format_system_assessment(self, skill) -> str:
        level_code = str(skill.assessed_level_code or "").strip()
        level_name = str(skill.assessed_level_name or "").strip()
        if level_name and level_code and level_name.lower() != level_code.lower():
            return f"{level_code} ({level_name})"
        if level_name:
            return level_name
        if level_code:
            return level_code
        return "—"

    def _resolve_pdf_font_name(self) -> str:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_candidates = [
            Path(__file__).resolve().parent / "pdf_assets" / "fonts" / "NotoSans.ttf",
            Path(__file__).resolve().parent / "pdf_assets" / "fonts" / "Inter.ttf",
            Path(__file__).resolve().parent / "pdf_assets" / "fonts" / "Manrope.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        font_path = next((Path(path) for path in font_candidates if Path(path).exists()), None)
        if font_path:
            font_name = "Agent4KExpertUnicode"
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                return font_name
            except Exception:
                pass
        return "Helvetica"

    def _profile_rows(self, detail) -> list[str]:
        profile = detail.profile_summary
        return [
            _row([_cell("ФИО", "Label"), _cell(detail.full_name or "—", "Text")], 22),
            _row([_cell("Телефон", "Label"), _cell(detail.phone or "—", "Text")], 22),
            _row([_cell("Telegram", "Label"), _cell(detail.telegram or "—", "Text")], 22),
            _row([_cell("Область работы компании", "Label"), _cell(detail.group_name or "—", "Text")], 22),
            _row([_cell("Должность", "Label"), _cell((profile.position if profile else None) or detail.role_name or "—", "Text")], 22),
            _row([_cell("Роль", "Label"), _cell(detail.role_name or "—", "Text")], 22),
        ]

    def _case_dialogue_rows(self, case_item, competency: str) -> list[str]:
        rows: list[str] = []
        header_text = f"{case_item.case_id_code or ''} — {case_item.case_title or 'Кейс'}".strip(" —")
        context_parts = [part for part in [header_text, case_item.personalized_context, case_item.personalized_task and f"Что нужно сделать:\n{case_item.personalized_task}"] if part]
        context_text = "\n\n".join(context_parts) or "—"
        rows.append(
            _row(
                [
                    _cell("Кейс", "Label"),
                    _cell(context_text, "WrappedText"),
                    _cell(),
                    _cell(),
                    _cell(),
                    _cell(),
                    _cell(),
                    _cell(),
                ],
                _estimate_height_points(context_text, base=42),
            )
        )

        messages = list(case_item.dialogue or [])
        if messages:
            pending_system: list[str] = []
            pending_user: list[str] = []
            for message in messages:
                role = str(message.role or "assistant")
                text = str(message.message_text or "").strip()
                if not text:
                    continue
                if role == "user":
                    pending_user.append(text)
                    system_text = "\n\n".join(pending_system).strip() or "—"
                    user_text = "\n\n".join(pending_user).strip() or "—"
                    pair_height = _estimate_height_points(system_text + "\n" + user_text, base=26)
                    rows.append(
                        _row(
                            [
                                _cell("Вопрос системы", "Label"),
                                _cell(system_text, "WrappedText"),
                                _cell("Ответ пользователя", "Label"),
                                _cell(user_text, "WrappedText"),
                                _cell(),
                                _cell(),
                                _cell(),
                                _cell(),
                            ],
                            pair_height,
                        )
                    )
                    pending_system = []
                    pending_user = []
                else:
                    pending_system.append(text)
            if pending_system:
                system_text = "\n\n".join(pending_system).strip()
                rows.append(
                    _row(
                        [
                            _cell("Вопрос системы", "Label"),
                            _cell(system_text, "WrappedText"),
                            _cell("Ответ пользователя", "Label"),
                            _cell("—", "WrappedText"),
                            _cell(),
                            _cell(),
                            _cell(),
                            _cell(),
                        ],
                        _estimate_height_points(system_text, base=24),
                    )
                )
        else:
            rows.append(
                _row(
                    [
                        _cell("Вопрос системы", "Label"),
                        _cell("—", "WrappedText"),
                        _cell("Ответ пользователя", "Label"),
                        _cell("Нет сохраненных реплик", "WrappedText"),
                        _cell(),
                        _cell(),
                        _cell(),
                        _cell(),
                    ],
                    24,
                )
            )

        competency_skills = [
            skill for skill in (case_item.skill_results or [])
            if str(skill.competency_name or "") == competency
        ]
        if competency_skills:
            first = True
            for skill in competency_skills:
                rows.append(
                    _row(
                        [
                            _cell("Навыки кейса" if first else "", "Label" if first else None),
                            _cell(str(skill.skill_name or "Навык"), "Text"),
                            _cell(self._format_system_assessment(skill), "Text"),
                            _cell("0", "BooleanCell", "Boolean"),
                            _cell("0", "BooleanCell", "Boolean"),
                            _cell("0", "BooleanCell", "Boolean"),
                            _cell("0", "BooleanCell", "Boolean"),
                            _cell("", "Text"),
                        ],
                        20,
                    )
                )
                first = False
        else:
            rows.append(
                _row(
                    [
                        _cell("Навыки кейса", "Label"),
                        _cell("По этой компетенции кейс не содержит локальной аналитики", "Text"),
                        _cell("—", "Text"),
                        _cell("0", "BooleanCell", "Boolean"),
                        _cell("0", "BooleanCell", "Boolean"),
                        _cell("0", "BooleanCell", "Boolean"),
                        _cell("1", "BooleanCell", "Boolean"),
                        _cell("", "Text"),
                    ],
                    20,
                )
            )

        rows.append(_row([_cell(), _cell(), _cell(), _cell(), _cell(), _cell(), _cell(), _cell()], 8))
        return rows

    def _completed_competency_cases(self, detail, competency: str) -> list[tuple[object, list[object]]]:
        completed_cases: list[tuple[object, list[object]]] = []
        for case_item in detail.case_items or []:
            if str(case_item.status or "") not in self._COMPLETED_CASE_STATUSES:
                continue
            case_skills = [
                skill for skill in (case_item.skill_results or [])
                if str(skill.competency_name or "") == competency
            ]
            if case_skills:
                completed_cases.append((case_item, case_skills))
        return completed_cases

    def _competency_sheet(self, detail, competency: str) -> str:
        rows = [
            _row(
                [
                    _cell("Задание / кейс", "Header"),
                    _cell("Текст", "Header"),
                    _cell("Оценка системы", "Header"),
                    _cell("L1", "Header"),
                    _cell("L2", "Header"),
                    _cell("L3", "Header"),
                    _cell("Не проявлено", "Header"),
                    _cell("Комментарий эксперта", "HeaderComment"),
                ],
                24,
            ),
            _row(
                [
                    _cell("Пользователь", "Label"),
                    _cell(detail.full_name or "—", "Text"),
                    _cell("Роль", "Label"),
                    _cell(detail.role_name or "—", "Text"),
                    _cell(),
                    _cell(),
                    _cell(),
                    _cell(),
                ],
                22,
            ),
        ]
        for case_item in detail.case_items or []:
            has_competency = any(str(skill.competency_name or "") == competency for skill in (case_item.skill_results or []))
            if has_competency:
                rows.extend(self._case_dialogue_rows(case_item, competency))
        if len(rows) == 2:
            rows.append(_row([_cell("Нет кейсов по этой компетенции", "Label"), _cell(), _cell(), _cell(), _cell(), _cell(), _cell(), _cell()], 22))
        return f'''
    <Worksheet ss:Name="{_xml_text(competency[:31])}">
      <Table ss:ExpandedColumnCount="8" ss:DefaultRowHeight="18">
        <Column ss:Width="150"/>
        <Column ss:Width="500"/>
        <Column ss:Width="110"/>
        <Column ss:Width="60"/>
        <Column ss:Width="60"/>
        <Column ss:Width="60"/>
        <Column ss:Width="90"/>
        <Column ss:Width="260"/>
        {''.join(rows)}
      </Table>
      <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
        <FreezePanes/>
        <FrozenNoSplit/>
        <SplitHorizontal>1</SplitHorizontal>
        <TopRowBottomPane>1</TopRowBottomPane>
        <ActivePane>2</ActivePane>
        <ProtectObjects>False</ProtectObjects>
        <ProtectScenarios>False</ProtectScenarios>
      </WorksheetOptions>
    </Worksheet>
        '''

    def _build_xml_workbook(self, detail) -> str:
        safe_name = _safe_filename_part(detail.full_name)
        profile_sheet = f'''
    <Worksheet ss:Name="Профиль">
      <Table ss:ExpandedColumnCount="2" ss:DefaultRowHeight="18">
        <Column ss:Width="180"/>
        <Column ss:Width="760"/>
        {''.join(self._profile_rows(detail))}
      </Table>
      <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
        <ProtectObjects>False</ProtectObjects>
        <ProtectScenarios>False</ProtectScenarios>
      </WorksheetOptions>
    </Worksheet>
        '''
        competency_sheets = "".join(self._competency_sheet(detail, competency) for competency in COMPETENCY_ORDER)
        workbook = f'''<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>OpenAI Codex</Author>
  <LastAuthor>OpenAI Codex</LastAuthor>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Bottom"/>
   <Borders/>
   <Font ss:FontName="Calibri" ss:Size="10"/>
   <Interior/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <Style ss:ID="Header">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/>
   <Interior ss:Color="#D9D9D9" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="HeaderComment">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/>
  </Style>
  <Style ss:ID="Label">
   <Alignment ss:Vertical="Top" ss:WrapText="1"/>
   <Font ss:FontName="Calibri" ss:Size="10" ss:Bold="1"/>
  </Style>
  <Style ss:ID="Text">
   <Alignment ss:Vertical="Top" ss:WrapText="1"/>
   <Font ss:FontName="Calibri" ss:Size="10"/>
  </Style>
  <Style ss:ID="WrappedText">
   <Alignment ss:Vertical="Top" ss:WrapText="1"/>
   <Font ss:FontName="Calibri" ss:Size="10"/>
  </Style>
  <Style ss:ID="NumberCell">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Font ss:FontName="Calibri" ss:Size="10"/>
  </Style>
  <Style ss:ID="BooleanCell">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Font ss:FontName="Calibri" ss:Size="10"/>
  </Style>
 </Styles>
 {profile_sheet}
 {competency_sheets}
</Workbook>
'''
        return workbook

    def build_excel(self, detail) -> tuple[str, bytes]:
        safe_name = _safe_filename_part(detail.full_name)
        filename = f"admin_expert_assessment_{detail.session_id}_{safe_name}.xls"
        return filename, self._build_xml_workbook(detail).encode("utf-8")

    def build_pdf(self, detail) -> tuple[str, bytes]:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        safe_name = _safe_filename_part(detail.full_name)
        filename = f"admin_expert_assessment_{detail.session_id}_{safe_name}.pdf"
        font_name = self._resolve_pdf_font_name()

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ExpertTitle",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=8,
        )
        h2_style = ParagraphStyle(
            "ExpertH2",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "ExpertBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#111827"),
        )
        small_style = ParagraphStyle(
            "ExpertSmall",
            parent=body_style,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#4B5563"),
        )

        def p(text: str, style=body_style) -> Paragraph:
            safe = escape(text or "—").replace("\n", "<br/>")
            return Paragraph(safe, style)

        def comment_placeholder(style=body_style) -> Paragraph:
            return Paragraph("&nbsp;<br/><br/><br/><br/>", style)

        story = [
            Paragraph("Экспертная выгрузка по ассессменту", title_style),
            Spacer(1, 6),
            Paragraph("Профиль пользователя", h2_style),
        ]

        profile = detail.profile_summary
        profile_rows = [
            ["ФИО", detail.full_name or "—"],
            ["Телефон", detail.phone or "—"],
            ["Telegram", detail.telegram or "—"],
            ["Область работы компании", detail.group_name or "—"],
            ["Должность", (profile.position if profile else None) or detail.role_name or "—"],
            ["Роль", detail.role_name or "—"],
        ]
        profile_table = Table(
            [[p(label, small_style), p(value or "—")] for label, value in profile_rows],
            colWidths=[48 * mm, 130 * mm],
            repeatRows=0,
        )
        profile_table.setStyle(
            TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.extend([profile_table, Spacer(1, 8)])

        for competency in COMPETENCY_ORDER:
            story.append(Paragraph(competency, h2_style))
            competency_cases = []
            for case_item in detail.case_items or []:
                case_skills = [skill for skill in (case_item.skill_results or []) if str(skill.competency_name or "") == competency]
                if case_skills:
                    competency_cases.append((case_item, case_skills))
            if not competency_cases:
                story.extend([p("По этой компетенции кейсы не найдены.", small_style), Spacer(1, 6)])
                continue

            for idx, (case_item, case_skills) in enumerate(competency_cases, start=1):
                header_text = f"{case_item.case_id_code or ''} — {case_item.case_title or 'Кейс'}".strip(" —")
                story.extend([
                    p(f"Кейс {idx}: {header_text}", body_style),
                    p((case_item.personalized_context or "—"), small_style),
                ])
                if case_item.personalized_task:
                    story.append(p(f"Что нужно сделать: {case_item.personalized_task}", small_style))

                messages = list(case_item.dialogue or [])
                rendered_pair = False
                pending_system: list[str] = []
                pending_user: list[str] = []
                for message in messages:
                    text = str(message.message_text or "").strip()
                    if not text:
                        continue
                    if str(message.role or "assistant") == "user":
                        pending_user.append(text)
                        system_text = "\n\n".join(pending_system).strip() or "—"
                        user_text = "\n\n".join(pending_user).strip() or "—"
                        qa_table = Table(
                            [
                                [p("Вопрос системы", small_style), p("Ответ пользователя", small_style)],
                                [p(system_text), p(user_text)],
                            ],
                            colWidths=[88 * mm, 88 * mm],
                        )
                        qa_table.setStyle(
                            TableStyle([
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ])
                        )
                        story.extend([Spacer(1, 4), qa_table, Spacer(1, 4)])
                        pending_system = []
                        pending_user = []
                        rendered_pair = True
                    else:
                        pending_system.append(text)
                if pending_system or not rendered_pair:
                    qa_table = Table(
                        [
                            [p("Вопрос системы", small_style), p("Ответ пользователя", small_style)],
                            [p("\n\n".join(pending_system).strip() or "—"), p("—")],
                        ],
                        colWidths=[88 * mm, 88 * mm],
                    )
                    qa_table.setStyle(
                        TableStyle([
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ])
                    )
                    story.extend([Spacer(1, 4), qa_table, Spacer(1, 4)])

                skills_text = "\n".join(f"• {skill.skill_name or 'Навык'}" for skill in case_skills) or "—"
                level_table = Table(
                    [
                        [
                            p("Навыки кейса", small_style),
                            p("Оценка системы", small_style),
                            p("L1", small_style),
                            p("L2", small_style),
                            p("L3", small_style),
                            p("Не проявлено", small_style),
                            p("Комментарий эксперта", small_style),
                        ],
                        [
                            p(skills_text),
                            p("\n".join(self._format_system_assessment(skill) for skill in case_skills) or "—"),
                            p("[ ]"),
                            p("[ ]"),
                            p("[ ]"),
                            p("[ ]"),
                            comment_placeholder(),
                        ],
                    ],
                    colWidths=[45 * mm, 28 * mm, 13 * mm, 13 * mm, 13 * mm, 20 * mm, 45 * mm],
                )
                level_table.setStyle(
                    TableStyle([
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ])
                )
                story.extend([level_table, Spacer(1, 8)])

        doc.build(story)
        return filename, buffer.getvalue()

    def _build_group_competency_pdf(self, details: list[object], competency: str) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        font_name = self._resolve_pdf_font_name()
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "GroupTitle",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=8,
        )
        h2_style = ParagraphStyle(
            "GroupH2",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "GroupBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#111827"),
        )
        small_style = ParagraphStyle(
            "GroupSmall",
            parent=body_style,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#4B5563"),
        )

        def p(text: str, style=body_style) -> Paragraph:
            safe = escape(text or "—").replace("\n", "<br/>")
            return Paragraph(safe, style)

        def comment_placeholder(style=body_style) -> Paragraph:
            return Paragraph("&nbsp;<br/><br/><br/><br/>", style)

        story = [
            Paragraph(f"Экспертная групповая выгрузка: {competency}", title_style),
            p(f"Количество пользователей: {len(details)}", small_style),
            Spacer(1, 6),
        ]

        first_user = True
        for detail in details:
            competency_cases = self._completed_competency_cases(detail, competency)
            if not first_user:
                story.append(PageBreak())
            first_user = False

            story.extend([
                Paragraph(detail.full_name or "Без имени", h2_style),
                Spacer(1, 4),
            ])

            profile = detail.profile_summary
            profile_rows = [
                ["ФИО", detail.full_name or "—"],
                ["Телефон", detail.phone or "—"],
                ["Telegram", detail.telegram or "—"],
                ["Область работы компании", detail.group_name or "—"],
                ["Должность", (profile.position if profile else None) or detail.role_name or "—"],
                ["Роль", detail.role_name or "—"],
            ]
            profile_table = Table(
                [[p(label, small_style), p(value or "—")] for label, value in profile_rows],
                colWidths=[44 * mm, 134 * mm],
            )
            profile_table.setStyle(
                TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ])
            )
            story.extend([profile_table, Spacer(1, 6)])

            if not competency_cases:
                story.extend([p("По этой компетенции завершенные кейсы не найдены.", small_style), Spacer(1, 8)])
                continue

            for idx, (case_item, case_skills) in enumerate(competency_cases, start=1):
                header_text = f"{case_item.case_id_code or ''} — {case_item.case_title or 'Кейс'}".strip(" —")
                story.extend([
                    p(f"Кейс {idx}: {header_text}", body_style),
                    p(case_item.personalized_context or "—", small_style),
                ])
                if case_item.personalized_task:
                    story.append(p(f"Что нужно сделать: {case_item.personalized_task}", small_style))

                messages = list(case_item.dialogue or [])
                pending_system: list[str] = []
                pending_user: list[str] = []
                rendered_pair = False
                for message in messages:
                    text = str(message.message_text or "").strip()
                    if not text:
                        continue
                    if str(message.role or "assistant") == "user":
                        pending_user.append(text)
                        system_chunks = _chunk_text_for_pdf("\n\n".join(pending_system).strip() or "—")
                        user_chunks = _chunk_text_for_pdf("\n\n".join(pending_user).strip() or "—")
                        row_count = max(len(system_chunks), len(user_chunks))
                        qa_rows = [
                            [p("Вопрос системы", small_style), p("Ответ пользователя", small_style)]
                        ]
                        for row_index in range(row_count):
                            qa_rows.append([
                                p(system_chunks[row_index] if row_index < len(system_chunks) else "—"),
                                p(user_chunks[row_index] if row_index < len(user_chunks) else "—"),
                            ])
                        qa_table = Table(
                            qa_rows,
                            colWidths=[88 * mm, 88 * mm],
                        )
                        qa_table.setStyle(
                            TableStyle([
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ])
                        )
                        story.extend([Spacer(1, 4), qa_table, Spacer(1, 4)])
                        pending_system = []
                        pending_user = []
                        rendered_pair = True
                    else:
                        pending_system.append(text)
                if pending_system or not rendered_pair:
                    system_chunks = _chunk_text_for_pdf("\n\n".join(pending_system).strip() or "—")
                    qa_rows = [
                        [p("Вопрос системы", small_style), p("Ответ пользователя", small_style)]
                    ]
                    for chunk in system_chunks:
                        qa_rows.append([p(chunk), p("—")])
                    qa_table = Table(
                        qa_rows,
                        colWidths=[88 * mm, 88 * mm],
                    )
                    qa_table.setStyle(
                        TableStyle([
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ])
                    )
                    story.extend([Spacer(1, 4), qa_table, Spacer(1, 4)])

                skills_text = "\n".join(f"• {skill.skill_name or 'Навык'}" for skill in case_skills) or "—"
                level_table = Table(
                    [
                        [
                            p("Навыки кейса", small_style),
                            p("Оценка системы", small_style),
                            p("L1", small_style),
                            p("L2", small_style),
                            p("L3", small_style),
                            p("Не проявлено", small_style),
                            p("Комментарий эксперта", small_style),
                        ],
                        [
                            p(skills_text),
                            p("\n".join(self._format_system_assessment(skill) for skill in case_skills) or "—"),
                            p("[ ]"),
                            p("[ ]"),
                            p("[ ]"),
                            p("[ ]"),
                            comment_placeholder(),
                        ],
                    ],
                    colWidths=[45 * mm, 28 * mm, 13 * mm, 13 * mm, 13 * mm, 20 * mm, 45 * mm],
                )
                level_table.setStyle(
                    TableStyle([
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ])
                )
                story.extend([level_table, Spacer(1, 8)])

        doc.build(story)
        return buffer.getvalue()

    def build_group_pdf_bundle(self, details: list[object]) -> tuple[str, bytes]:
        archive_buffer = BytesIO()
        with ZipFile(archive_buffer, "w", compression=ZIP_DEFLATED) as zf:
            for competency in COMPETENCY_ORDER:
                pdf_bytes = self._build_group_competency_pdf(details, competency)
                safe_competency = COMPETENCY_FILE_CODES.get(competency, "competency")
                zf.writestr(f"expert_group_{safe_competency}.pdf", pdf_bytes)
        return "expert_group_assessments_bundle.zip", archive_buffer.getvalue()


admin_report_expert_export_service = AdminReportExpertExportService()

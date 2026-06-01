from __future__ import annotations

from Api.typst_pdf_renderer import render_typst_admin_reports

class AdminReportsPdfService:
    def _build_typst_payload(self, reports_response) -> dict:
        items = []
        for item in reports_response.items:
            date_value = item.finished_at or item.started_at
            items.append(
                {
                    "session_id": int(item.session_id),
                    "user_id": int(item.user_id),
                    "full_name": item.full_name,
                    "group_name": item.group_name,
                    "role_name": item.role_name,
                    "status": item.status,
                    "score_label": f"{item.score_percent}%" if item.score_percent is not None else "—",
                    "mbti_type": item.mbti_type or "Нет данных",
                    "date_label": date_value.strftime("%d.%m.%Y") if date_value else "Без даты",
                }
            )
        return {
            "title": reports_response.title,
            "subtitle": reports_response.subtitle,
            "total_items": int(reports_response.total_items),
            "summary_score_label": (
                str(reports_response.summary_score_percent)
                if reports_response.summary_score_percent is not None
                else "Нет данных"
            ),
            "items": items,
        }

    def build_pdf(self, reports_response) -> tuple[str, bytes]:
        filename = "admin_detailed_reports.pdf"
        return filename, render_typst_admin_reports(self._build_typst_payload(reports_response))


admin_reports_pdf_service = AdminReportsPdfService()

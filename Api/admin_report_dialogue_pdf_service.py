from __future__ import annotations

from Api.typst_pdf_renderer import render_typst_admin_dialogue


def _safe_filename_part(value: str | None, fallback: str = "user") -> str:
    raw_name = str(value or fallback)
    safe_name = "".join(ch if (ch.isascii() and (ch.isalnum() or ch in ("_", "-"))) else "_" for ch in raw_name)
    return safe_name.strip("_") or fallback


class AdminReportDialoguePdfService:
    def _message_payload(self, message) -> dict:
        return {
            "role": message.role or "assistant",
            "role_label": "Пользователь" if message.role == "user" else "Ассистент",
            "message_text": message.message_text or "",
        }

    def _case_payload(self, case_item) -> dict:
        return {
            "session_case_id": int(case_item.session_case_id),
            "case_number": int(case_item.case_number),
            "case_title": case_item.case_title or "Кейс без названия",
            "personalized_context": case_item.personalized_context or "",
            "personalized_task": case_item.personalized_task or "",
            "dialogue": [self._message_payload(message) for message in case_item.dialogue],
        }

    def _base_payload(self, detail, *, title: str, case_items: list[dict]) -> dict:
        return {
            "title": title,
            "full_name": detail.full_name or "Без имени",
            "role_name": detail.role_name or "Не указана",
            "session_id": int(detail.session_id),
            "case_items": case_items,
        }

    def build_pdf(self, detail) -> tuple[str, bytes]:
        safe_name = _safe_filename_part(detail.full_name)
        payload = self._base_payload(
            detail,
            title="Диалог пользователя с агентом",
            case_items=[self._case_payload(item) for item in detail.case_items],
        )
        return f"admin_dialogue_{detail.session_id}_{safe_name}.pdf", render_typst_admin_dialogue(payload)

    def build_case_pdf(self, detail, case_item) -> tuple[str, bytes]:
        safe_name = _safe_filename_part(detail.full_name)
        payload = self._base_payload(
            detail,
            title="Диалог по кейсу",
            case_items=[self._case_payload(case_item)],
        )
        return (
            f"admin_case_dialogue_{detail.session_id}_{case_item.session_case_id}_{safe_name}.pdf",
            render_typst_admin_dialogue(payload),
        )


admin_report_dialogue_pdf_service = AdminReportDialoguePdfService()

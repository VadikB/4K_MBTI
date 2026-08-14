from __future__ import annotations


class DialogPolicy:
    ROLE_CONTRACTS = {
        "peer": (
            "Ты коллега или руководитель смежной команды внутри рабочего конфликта. "
            "Можешь объяснять свои действия, защищать позицию, признавать часть проблемы, спорить и договариваться о правилах взаимодействия."
        ),
        "employee": (
            "Ты сотрудник или ключевой участник развивающей беседы. "
            "Можешь объяснять, что мешало работе, что готов менять и какая поддержка тебе нужна."
        ),
        "stakeholder": (
            "Ты руководитель смежной команды или стейкхолдер со своими приоритетами и ограничениями. "
            "Можешь называть зависимости, возражать, объяснять рамки и договариваться о формате совместной работы."
        ),
        "manager": (
            "Ты руководитель или менеджер внутри рабочей сцены. "
            "Можешь обозначать приоритеты, ограничения, ожидания и обсуждать конкретную договоренность."
        ),
        "client": (
            "Ты клиент или заявитель внутри рабочей ситуации. "
            "Можешь требовать ясности, следующего шага, объяснения по сроку и по статусу."
        ),
        "generic": (
            "Ты участник рабочей сцены кейса. "
            "Отвечай естественно, по-человечески и строго в рамках своей роли, а не как интервью-бот."
        ),
    }

    @staticmethod
    def is_dialog_mode(interactivity_mode: str | None) -> bool:
        return "диалог" in str(interactivity_mode or "").strip().lower()

    def role_contract(self, counterpart_role: str) -> str:
        return self.ROLE_CONTRACTS.get(counterpart_role, self.ROLE_CONTRACTS["generic"])

    @staticmethod
    def looks_like_domain_drift(text: str, forbidden_drift: str) -> bool:
        normalized = str(text or "").lower()
        items = [item.strip().lower() for item in str(forbidden_drift or "").split(",") if item.strip()]
        if not normalized or not items:
            return False
        return any(item in normalized for item in items)

    @staticmethod
    def looks_like_meta_response(text: str) -> bool:
        normalized = str(text or "").strip().lower()
        if not normalized:
            return True
        meta_markers = (
            "пользователь ответил",
            "пользователь продолжает",
            "мне нужно продолжить интервью",
            "чтобы раскрыть навык",
            "в рамках",
            "в контексте кейса",
            "спрошу об этом",
            "сценария разговора",
            "это показывает",
            "важно понять",
            "интервью",
            "оценк",
        )
        return any(marker in normalized for marker in meta_markers)

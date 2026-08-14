from __future__ import annotations


class DialogStateMachine:
    STAGE_LABELS = {
        "root_cause": "прояснение причины и ограничений",
        "missing_info": "уточнение недостающей информации",
        "workflow_rule": "согласование рабочего минимума и правил передачи",
        "future_change": "обсуждение изменения процесса на будущее",
        "change_commitment": "личное обязательство по изменению поведения",
        "support_need": "обсуждение нужной поддержки и условий",
        "agreement": "фиксация рабочей договоренности",
        "closure": "закрытие разговора и контрольная точка",
        "criticality": "прояснение критичности и приоритетов",
        "constraints": "прояснение ограничений и зависимостей",
        "next_step": "согласование ближайшего следующего шага",
    }

    STAGE_KEYWORDS = {
        "emotion": ("задело", "без общих слов", "сорвался", "сорвал", "резко"),
        "criticality": ("самое критичное", "что для вас в этой ситуации сейчас самое критичное", "на каком шаге вы хотите договориться"),
        "root_cause": ("разберем причину", "разберём причину", "где именно сейчас", "основной перегруз", "основной сбой", "из-за которого"),
        "missing_info": ("чего именно не хватило", "какие данные", "какой информации", "какие комментарии"),
        "workflow_rule": ("обязательным минимумом", "минимумом в карточке", "что должно быть обязательным"),
        "future_change": ("что именно должно меняться", "не повторялась", "в следующ", "при следующей передаче"),
        "change_commitment": ("что именно ты готов поменять", "что именно вы готовы изменить", "уже на этой неделе", "в ближайшие дни"),
        "next_step": ("следующим шагом", "какой следующий шаг", "не оставить вопрос в подвешенном состоянии"),
        "constraints": ("какие ограничения", "что ограничивает", "какие зависимости", "что нужно подтвердить"),
        "support_need": ("какая поддержка", "какая договоренность", "какая договорённость", "с моей стороны тебе нужна", "со второй стороны нужна"),
        "agreement": ("ты с этим согласен", "готовы на таком варианте договориться", "давайте тогда это зафиксируем"),
        "closure": ("договорились", "тогда фиксируем так", "с моей стороны я тоже", "рабочее правило"),
    }

    @staticmethod
    def infer_counterpart_role(scenario_text: str) -> str:
        normalized = str(scenario_text or "").lower()
        role_markers = (
            ("peer", ("между нами как коллегами", "следующая смена", "вторая линия", "смежной команды", "по этой передаче", "ты готов поменять", "ты мог взять инцидент")),
            ("employee", ("развивающей беседе", "план развития", "зона роста", "сотрудник", "подчинен", "подчинён")),
            ("manager", ("руковод", "лидер", "менеджер")),
            ("stakeholder", ("стейкхолдер", "смежник", "смежная сторона")),
            ("client", ("клиент", "пользоват", "заказчик", "заявител")),
        )
        return next((role for role, markers in role_markers if any(marker in normalized for marker in markers)), "generic")

    def stage_label(self, stage_code: str | None) -> str:
        return self.STAGE_LABELS.get(str(stage_code or "").strip(), "рабочее продолжение разговора")

    @staticmethod
    def stage_plan(*, counterpart_role: str, is_development_dialog: bool) -> tuple[str, ...]:
        if is_development_dialog or counterpart_role == "employee":
            return ("root_cause", "change_commitment", "support_need", "agreement", "closure")
        if counterpart_role == "peer":
            return ("root_cause", "missing_info", "workflow_rule", "change_commitment", "support_need", "agreement", "closure")
        if counterpart_role in {"manager", "stakeholder"}:
            return ("criticality", "constraints", "agreement", "closure")
        if counterpart_role == "client":
            return ("next_step", "constraints", "agreement", "closure")
        return ("root_cause", "agreement", "closure")

    def infer_reply_stages(self, text: str | None) -> set[str]:
        normalized = str(text or "").lower()
        return {
            stage
            for stage, keywords in self.STAGE_KEYWORDS.items()
            if any(keyword in normalized for keyword in keywords)
        }

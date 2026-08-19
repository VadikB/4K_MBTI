from __future__ import annotations

from Api.assessment.interview.state_machine import DialogStateMachine


class DialogFallbackEngine:
    def __init__(self, *, state_machine: DialogStateMachine | None = None) -> None:
        self.state_machine = state_machine or DialogStateMachine()

    @staticmethod
    def build_direct_answer(
        *,
        normalized_user: str,
        counterpart_role: str,
        asked_stages: set[str],
    ) -> str | None:
        if "?" not in normalized_user and not any(
            token in normalized_user
            for token in ("почему", "из-за чего", "что мешает", "что именно", "какая поддержка", "что нужно")
        ):
            return None

        if counterpart_role == "peer":
            if any(token in normalized_user for token in ("почему", "из-за чего", "не закрыл", "сорвался срок", "что случилось")):
                return (
                    "Потому что меня в тот момент сорвало на срочную эскалацию, и я не зафиксировал нормально новый срок и статус. "
                    "Давай разберем, что у нас в этом месте ломается чаще всего."
                )
            if any(token in normalized_user for token in ("что мешает", "что тебе мешает", "в чем проблема", "в чём проблема")):
                return (
                    "Сильнее всего мешает резкое переключение между срочными эскалациями и обычной очередью, "
                    "из-за этого я проваливаю обновление статуса и договоренности по сроку. "
                    "Надо понять, как это лучше фиксировать заранее."
                )
            if any(token in normalized_user for token in ("какая поддержка", "что тебе нужно", "что нужно от меня")):
                return (
                    "От тебя мне нужна понятная договоренность: если я понимаю, что срок срывается, я сразу пишу это в Service Desk, "
                    "а мы отдельно сверяем новый срок и следующий шаг, а не оставляем заявку без обновления."
                )
            if any(token in normalized_user for token in ("что именно нужно", "какой минимум", "что должно быть")):
                return (
                    "Минимум для меня такой: актуальный статус, что уже проверено, почему срок сдвигается и какой следующий шаг мы фиксируем. "
                    "Тогда следующая передача не повисает в воздухе."
                )

        if counterpart_role == "employee":
            if any(token in normalized_user for token in ("почему", "из-за чего", "что случилось")):
                return (
                    "Потому что в последнее время я начал терять приоритет между срочными задачами и регулярной работой, "
                    "и это стало бить по предсказуемости результата. "
                    "Давайте разберем, где именно это проявляется сильнее всего."
                )
            if any(token in normalized_user for token in ("какая поддержка", "что нужно от нас", "что вам нужно")):
                return (
                    "Мне нужна понятная рамка ожиданий, короткая сверка по приоритетам и контрольная точка, "
                    "чтобы изменение не осталось только договоренностью на словах."
                )

        if counterpart_role == "stakeholder" and any(
            token in normalized_user for token in ("что для вас критично", "что вам нужно", "почему не получается")
        ):
            return (
                "Для нас критично не потерять темп и не зависнуть без понятного следующего шага. "
                "Со своей стороны я хочу сразу проговорить ограничения и понять, на чем мы можем зафиксироваться сейчас."
            )

        if counterpart_role == "client" and any(
            token in normalized_user for token in ("когда", "какой срок", "что происходит", "почему")
        ):
            return (
                "Сейчас я не готов обещать срок без подтверждения следующего шага, но могу сразу зафиксировать, "
                "что вопрос не закрыт и требует обновления статуса. "
                "Давайте тогда определим, что именно делаем следующим действием."
            )

        if counterpart_role in {"manager", "stakeholder"} and "criticality" not in asked_stages:
            return (
                "С моей стороны важно не потерять управляемость ситуации и не оставить ее без договоренности. "
                "Давайте тогда зафиксируем, что для вас сейчас самое критичное."
            )
        return None

    def build_reply(
        self,
        *,
        user_message: str,
        dialogue: list[dict[str, str]],
    ) -> str:
        normalized_user = str(user_message or "").strip().lower()
        scenario_text = " ".join(item["content"] for item in dialogue if item["role"] == "assistant").lower()
        assistant_messages = [
            str(item["content"] or "").strip()
            for item in dialogue
            if item["role"] == "assistant" and str(item["content"] or "").strip()
        ]
        assistant_turn_count = len(assistant_messages)
        asked_stages: set[str] = set()
        for message in assistant_messages[-4:]:
            asked_stages.update(self.state_machine.infer_reply_stages(message))
        counterpart_role = self.state_machine.infer_counterpart_role(scenario_text)

        is_peer_dialog = counterpart_role == "peer"
        is_development_dialog = any(
            marker in scenario_text
            for marker in (
                "изменил подход",
                "план изменений",
                "план развития",
                "план роста",
                "развивающ",
                "обратной связ",
                "зона роста",
                "сильная сторона",
                "подчинен",
                "подчинён",
                "развити",
            )
        )
        wants_support = any(
            token in normalized_user
            for token in (
                "поддержк",
                "с моей стороны",
                "с моей помощ",
                "договоренност",
                "договорённост",
                "нужно от тебя",
                "нужно от вас",
                "чтобы план",
                "не развал",
            )
        )
        wants_closure = any(
            token in normalized_user
            for token in (
                "подведу итог",
                "фиксируем",
                "контрольную точку",
                "контрольная точка",
                "ты с этим согласен",
                "вы с этим согласны",
                "так и работаем",
                "договорились",
            )
        )
        wants_root_cause = any(
            token in normalized_user
            for token in (
                "помочь",
                "перегруз",
                "что происходит",
                "в чем причина",
                "в чём причина",
                "сбой",
                "не успева",
                "нагруз",
                "узкое место",
                "почему ты стал так",
                "почему вы стали так",
            )
        )
        wants_change_commitment = any(
            token in normalized_user
            for token in (
                "готов изменить",
                "на этой неделе",
                "изменить уже",
                "следующие шаги",
                "буду делать",
                "план",
                "исправлю",
                "начну",
                "готов поменять",
                "что ты сам готов",
                "что вы сами готовы",
            )
        )
        wants_workflow_rule = any(
            token in normalized_user
            for token in (
                "должно",
                "нужно",
                "обязательно",
                "минимум",
                "статус",
                "комментар",
                "проверили",
                "ждем",
                "ждём",
            )
        )
        has_root_cause_answer = any(
            token in normalized_user
            for token in (
                "перегруз",
                "нагруз",
                "не успева",
                "много заяв",
                "очеред",
                "слишком много",
                "не хватает времени",
                "сбой",
                "узкое место",
                "разрываюсь",
                "три заявки",
                "висят",
            )
        )
        has_missing_info_answer = any(
            token in normalized_user
            for token in (
                "непонятно",
                "не хват",
                "не было",
                "без комментар",
                "без коммент",
                "что уже проверили",
                "что проверили",
                "что именно нужно",
                "какие данные",
                "какой статус",
            )
        )
        has_workflow_rule_answer = any(
            token in normalized_user
            for token in (
                "обязательно",
                "минимум",
                "в карточке",
                "должен быть статус",
                "должен быть",
                "оставлять комментар",
                "фиксировать",
                "шаблон передачи",
                "передач",
                "короткий шаблон",
            )
        )
        has_change_commitment_answer = any(
            token in normalized_user
            for token in (
                "буду",
                "начну",
                "изменю",
                "проверять",
                "фиксировать",
                "обновлять",
                "ставить статус",
                "оставлять комментар",
                "на этой неделе",
                "договоримся",
            )
        )
        has_support_answer = any(
            token in normalized_user
            for token in (
                "нужно от тебя",
                "нужно от вас",
                "помоги",
                "поддержк",
                "если ты",
                "если вы",
                "договоренность",
                "договорённость",
                "эскал",
                "сверка",
                "контрольная точка",
            )
        )
        has_future_change_answer = any(
            token in normalized_user
            for token in (
                "в следующий раз",
                "дальше будем",
                "не повторялось",
                "не повторялись",
                "дальше использовать",
                "с этого дня",
                "при следующей передаче",
            )
        )
        has_agreement_answer = any(
            token in normalized_user
            for token in (
                "соглас",
                "договорились",
                "подходит",
                "фиксируем",
                "так и работаем",
                "давай так",
            )
        )
        work_topic_markers = (
            "заявк",
            "срок",
            "инцидент",
            "service desk",
            "сервис деск",
            "эскалац",
            "статус",
            "комментар",
            "передач",
            "нагруз",
            "ресурс",
            "договор",
            "задач",
            "очеред",
            "повтор",
            "закрыл",
            "закры",
        )
        personal_attack_markers = (
            "пахнет",
            "воня",
            "воняет",
            "одеколон",
            "дезодоран",
            "пахнеш",
            "пахнешь",
            "вонюч",
            "воняешь",
            "вонь",
        )
        is_offtopic_personal_attack = (
            any(marker in normalized_user for marker in personal_attack_markers)
        )

        if is_offtopic_personal_attack:
            if is_peer_dialog:
                return (
                    "Давай оставим личные оценки в стороне и вернемся к рабочей ситуации. "
                    "Мне важно понять по делу: из-за чего именно у тебя в этой цепочке снова сорвался срок по заявке?"
                )
            if is_development_dialog:
                return (
                    "Давайте вернем разговор в рабочую рамку. "
                    "Что именно в процессе или нагрузке сейчас мешает вам удерживать договоренности по срокам?"
                )
            if counterpart_role == "stakeholder":
                return (
                    "Предлагаю держаться рабочей сути разговора. "
                    "Что именно сейчас мешает согласовать следующий шаг и снять напряжение по ситуации?"
                )
            if counterpart_role == "client":
                return (
                    "Давайте вернемся к сути вопроса. "
                    "Какой конкретный следующий шаг вы предлагаете сейчас по рабочей ситуации?"
                )
            return (
                "Предлагаю оставить личные комментарии в стороне и вернуться к рабочей ситуации. "
                "Что именно в процессе сейчас нужно прояснить в первую очередь?"
            )

        direct_answer = self.build_direct_answer(
            normalized_user=normalized_user,
            counterpart_role=counterpart_role,
            asked_stages=asked_stages,
        )
        if direct_answer:
            return direct_answer

        if is_development_dialog:
            if "root_cause" not in asked_stages:
                return "Хорошо. Тогда давайте сначала разберем причину: где именно сейчас возникает основной перегруз или сбой, из-за которого ситуация повторяется?"
            if "change_commitment" not in asked_stages:
                if has_root_cause_answer:
                    return "Хорошо. Тогда что именно вы готовы изменить уже на этой неделе, чтобы команда снова видела понятный статус и следующий шаг без дополнительных уточнений?"
                return "Понял. Причину зафиксировали не до конца. Скажите тогда конкретно: где именно у вас сейчас самый сильный перегруз или сбой, из-за которого статусы начинают выпадать?"
            if "support_need" not in asked_stages:
                if has_change_commitment_answer:
                    return "Понял. Тогда какая поддержка или договоренность со второй стороны нужна вам, чтобы новый порядок действительно удержался в работе?"
                return "Хорошо. Тогда что именно вы готовы изменить уже на этой неделе, чтобы новый порядок не остался просто словами?"
            if "agreement" not in asked_stages:
                if has_support_answer:
                    return "Хорошо. Тогда давайте зафиксируем это как рабочую договоренность и сверим контрольную точку. Вы готовы на таком варианте остановиться?"
                return "Понял. Тогда какая поддержка или договоренность со второй стороны нужна вам, чтобы изменение не сорвалось под нагрузкой?"
            if "closure" not in asked_stages:
                if wants_closure or has_agreement_answer:
                    return "Договорились. Тогда фиксируем новый порядок, поддержку и контрольную точку на конец недели, чтобы проверить, что изменение действительно закрепилось в работе."
                return "Хорошо. Тогда подтвердите, что на таком порядке мы останавливаемся и проверяем результат в согласованную дату."
            if wants_closure and "closure" not in asked_stages:
                return "Договорились. Тогда фиксируем новый порядок, поддержку и контрольную точку на конец недели, чтобы проверить, что изменение действительно закрепилось в работе."
            staged_prompt = self.state_machine.build_stage_prompt(
                counterpart_role=counterpart_role,
                is_development_dialog=is_development_dialog,
                asked_stages=asked_stages,
            )
            return staged_prompt or "Хорошо. Тогда так и работаем дальше: держим этот порядок и возвращаемся к нему на контрольной точке."

        if (
            wants_support
            and "support_need" not in asked_stages
        ):
            if is_peer_dialog:
                return "Понял. Тогда давай зафиксируем и вторую сторону: какая поддержка или договоренность с моей стороны тебе нужна, чтобы этот план не рассыпался через пару дней?"
            return "Понял. Тогда какая поддержка или договоренность со второй стороны нужна вам, чтобы новый порядок действительно удержался в работе?"

        if (
            wants_closure
            and "closure" not in asked_stages
        ):
            if is_peer_dialog:
                return "Договорились. Тогда фиксируем новый порядок, отдельно отмечаем риск срыва и ставим контрольную точку, чтобы проверить, что договоренность реально удержалась в работе."
            return "Договорились. Тогда фиксируем этот порядок, поддержку со второй стороны и контрольную точку, чтобы проверить, что изменения действительно закрепились."

        if (
            wants_root_cause
            and "root_cause" not in asked_stages
        ):
            if is_peer_dialog:
                return "Окей, давай тогда разберем причину спокойно: где именно сейчас у тебя самый сильный перегруз или сбой, из-за которого статус и комментарии начинают выпадать?"
            return "Хорошо. Тогда давайте сначала разберем причину: где именно сейчас возникает основной перегруз или сбой, из-за которого ситуация повторяется?"

        if (
            any(token in normalized_user for token in ("сорвал", "резко", "сорвался", "вспылил", "эмоц"))
            and "emotion" not in asked_stages
        ):
            if is_peer_dialog:
                return "Я услышал, что тебя это уже сильно задело. Давай тогда без общих слов: чего именно не хватило в передаче инцидента, чтобы ты мог нормально подхватить задачу без повторной диагностики?"
            return "Понимаю, что ситуация уже накопилась. Скажите прямо: чего именно вам не хватило в этой передаче, чтобы можно было спокойно продолжить работу без лишнего круга?"

        if (
            any(token in normalized_user for token in ("не хват", "не было", "кусками", "частями", "без комментар", "без коммент", "непонятно"))
            and "missing_info" not in asked_stages
        ):
            if is_peer_dialog:
                return "Хорошо, тогда давай конкретно: какие данные или комментарии в карточке должны были быть обязательно, чтобы ты мог взять инцидент в работу без дополнительных уточнений?"
            return "Тогда уточните конкретно: какой информации или фиксации действий вам не хватило, чтобы без задержки продолжить работу?"

        if (
            any(token in normalized_user for token in ("должно", "нужно", "обязательно", "минимум", "статус", "комментар", "проверили", "ждем", "ждём"))
            and "workflow_rule" not in asked_stages
        ):
            if is_peer_dialog:
                return "Окей, это уже конкретно. Тогда давай договоримся предметно: что именно должно быть обязательным минимумом в карточке перед передачей, чтобы следующая смена могла сразу брать задачу в работу?"
            return "Хорошо. Тогда что именно вы хотите сделать обязательным минимумом при передаче таких задач, чтобы следующий участник мог сразу продолжать работу?"

        if (
            any(token in normalized_user for token in ("срок", "задерж", "повтор", "третий", "снова", "дальше", "в следующий раз"))
            and "future_change" not in asked_stages
        ):
            if is_peer_dialog:
                return "Понял. Тогда давай зафиксируем предметно: что именно у нас должно меняться в передаче таких заявок, чтобы эта история не повторялась на следующем инциденте?"
            return "Понял. Что именно нужно изменить в вашей совместной работе, чтобы эта ситуация не повторилась при следующей передаче задачи?"

        if (
            any(token in normalized_user for token in ("обязательно", "минимум", "нужно", "должно", "фиксировать", "оставляем", "перед передачей"))
            and "agreement" not in asked_stages
        ):
            if is_peer_dialog:
                return "Подходит. Тогда предлагаю так и зафиксировать: перед передачей оставляем этот минимум в карточке, а если данных не хватает, отдельно помечаем это в комментарии, а не просто переводим заявку дальше. Ты с этим согласен?"
            return "Хорошо. Давайте тогда это зафиксируем как правило работы. Вы готовы на таком варианте договориться?"

        if (
            wants_change_commitment
            and "change_commitment" not in asked_stages
        ):
            if is_peer_dialog:
                return "Хорошо, это уже ближе к делу. Тогда что именно ты готов поменять уже на этой неделе, чтобы команда снова видела понятный статус и следующий шаг без дополнительных уточнений?"
            return "Хорошо. Тогда что именно вы готовы изменить уже в ближайшие дни, чтобы проблема не повторялась в том же виде?"

        if (
            "agreement" in asked_stages
            and "closure" not in asked_stages
            and any(
                token in normalized_user
                for token in (
                    "соглас",
                    "договор",
                    "достаточно",
                    "подойдет",
                    "подойдёт",
                    "окей",
                    "хорошо",
                    "если ты",
                    "если вы",
                    "давай так",
                    "так и договоримся",
                )
            )
        ):
            if is_peer_dialog:
                return "Договорились. Тогда фиксируем так: перед передачей ты оставляешь обязательный минимум в карточке, а если видишь риск срыва или пробел по данным, отдельно пишешь об этом сразу. С моей стороны я тоже не возвращаю задачу молча, а прямо отмечаю, чего не хватает."
            return "Договорились. Тогда фиксируем этот порядок как рабочее правило и в следующий раз сразу отдельно отмечаем риск, если данных или подтверждений не хватает."

        if counterpart_role == "client":
            staged_prompt = self.state_machine.build_stage_prompt(
                counterpart_role=counterpart_role,
                is_development_dialog=is_development_dialog,
                asked_stages=asked_stages,
            )
            return staged_prompt or "Хорошо. Тогда подтвердите коротко: какой следующий шаг вы фиксируете и когда вернетесь с обновлением?"

        if counterpart_role in {"manager", "stakeholder"}:
            staged_prompt = self.state_machine.build_stage_prompt(
                counterpart_role=counterpart_role,
                is_development_dialog=is_development_dialog,
                asked_stages=asked_stages,
            )
            return staged_prompt or "Договорились. Тогда зафиксируем выбранный формат и контрольную точку, на которой проверим, что договоренность действительно сработала."

        if is_peer_dialog:
            if assistant_turn_count == 0:
                return "Давай начнем с причины: где именно в этой ситуации у тебя возник основной сбой или перегруз, из-за которого все пошло по кругу?"
            if "root_cause" not in asked_stages:
                return "Давай тогда сначала разберем причину: где именно сейчас ломается процесс или не хватает ресурса, из-за чего эта ситуация повторяется?"
            if (
                "missing_info" not in asked_stages
                and (
                    has_root_cause_answer
                    or (
                        "root_cause" in asked_stages
                        and not any(
                            (
                                has_missing_info_answer,
                                has_workflow_rule_answer,
                                has_change_commitment_answer,
                                has_support_answer,
                                has_agreement_answer,
                            )
                        )
                    )
                )
            ):
                return "Хорошо, тогда давай конкретно: каких данных или комментариев тебе не хватало в карточке, чтобы ты мог взять инцидент в работу без дополнительного круга уточнений?"
            if (
                "workflow_rule" not in asked_stages
                and (
                    has_missing_info_answer
                    or has_workflow_rule_answer
                    or ("missing_info" in asked_stages and has_root_cause_answer)
                )
            ):
                return "Окей, это уже конкретно. Тогда давай договоримся предметно: что именно должно быть обязательным минимумом в карточке перед передачей, чтобы следующая смена могла сразу брать задачу в работу?"
            if (
                "change_commitment" not in asked_stages
                and (
                    has_workflow_rule_answer
                    or has_future_change_answer
                    or ("workflow_rule" in asked_stages and has_missing_info_answer)
                )
            ):
                return "Хорошо, давай тогда предметно: что именно ты предлагаешь изменить в нашей работе после этого разговора?"
            if (
                "support_need" not in asked_stages
                and (
                    has_change_commitment_answer
                    or has_future_change_answer
                    or ("change_commitment" in asked_stages and has_workflow_rule_answer)
                )
            ):
                return "Окей. А какая поддержка или договоренность с моей стороны нужна, чтобы это изменение реально закрепилось в работе?"
            if (
                "agreement" not in asked_stages
                and (
                    has_support_answer
                    or has_change_commitment_answer
                    or has_workflow_rule_answer
                    or ("support_need" in asked_stages and has_future_change_answer)
                )
            ):
                return "Тогда предлагаю зафиксировать это как рабочую договоренность. Ты готов на таком варианте остановиться?"
            if (
                "closure" not in asked_stages
                and (
                    has_agreement_answer
                    or ("agreement" in asked_stages and has_support_answer)
                )
            ):
                return "Договорились. Тогда коротко фиксируем новый порядок и контрольную точку, чтобы через несколько дней проверить, что он действительно работает."
            staged_prompt = self.state_machine.build_stage_prompt(
                counterpart_role=counterpart_role,
                is_development_dialog=is_development_dialog,
                asked_stages=asked_stages,
            )
            return staged_prompt or "Хорошо, тогда так и работаем дальше: держим этот порядок и возвращаемся к нему на ближайшей контрольной точке."

        return "Хорошо. Скажите прямо: что именно в этой ситуации нужно прояснить или изменить уже сейчас, чтобы разговор сдвинулся с места?"

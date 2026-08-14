from Api.assessment.interview import DialogFallbackEngine, DialogStateMachine


def test_direct_answer_rules_have_priority_after_safety_guard() -> None:
    engine = DialogFallbackEngine(state_machine=DialogStateMachine())

    result = engine.build_reply(
        user_message="Почему сорвался срок?",
        dialogue=[{"role": "assistant", "content": "Вы клиент внутри рабочей ситуации."}],
    )

    assert "не готов обещать срок" in result


def test_personal_attack_is_returned_to_work_context() -> None:
    result = DialogFallbackEngine().build_reply(
        user_message="От тебя пахнет одеколоном",
        dialogue=[{"role": "assistant", "content": "Мы коллеги из смежной команды, следующая смена ждёт."}],
    )

    assert "личные оценки" in result
    assert "рабочей ситуации" in result


def test_peer_dialog_starts_with_root_cause() -> None:
    result = DialogFallbackEngine().build_reply(
        user_message="Давайте обсудим ситуацию",
        dialogue=[{"role": "assistant", "content": "Между нами как коллегами возник сбой при передаче."}],
    )

    assert "разберем причину" in result


def test_client_dialog_advances_by_stage_plan() -> None:
    result = DialogFallbackEngine().build_reply(
        user_message="Продолжим",
        dialogue=[{"role": "assistant", "content": "Вы клиент. Что предлагаете сделать следующим шагом?"}],
    )

    assert "ограничивает вас" in result


def test_non_question_does_not_produce_direct_answer() -> None:
    assert DialogFallbackEngine.build_direct_answer(
        normalized_user="продолжаем разговор",
        counterpart_role="peer",
        asked_stages=set(),
    ) is None


def test_peer_support_question_gets_in_role_answer() -> None:
    answer = DialogFallbackEngine.build_direct_answer(
        normalized_user="какая поддержка тебе нужна?",
        counterpart_role="peer",
        asked_stages={"root_cause"},
    )

    assert "сразу пишу это в Service Desk" in str(answer)

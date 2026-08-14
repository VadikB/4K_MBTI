from Api.assessment.interview import DialogFallbackEngine, DialogStateMachine


class FakePolicy:
    def __init__(self, direct_answer=None):
        self.direct_answer = direct_answer

    def _build_dialog_direct_answer(self, **_kwargs):
        return self.direct_answer


def test_direct_answer_has_priority_after_safety_guard() -> None:
    engine = DialogFallbackEngine(state_machine=DialogStateMachine())

    result = engine.build_reply(
        policy=FakePolicy("Прямой ответ собеседника"),
        user_message="Когда будет готово?",
        dialogue=[{"role": "assistant", "content": "Вы клиент внутри рабочей ситуации."}],
    )

    assert result == "Прямой ответ собеседника"


def test_personal_attack_is_returned_to_work_context() -> None:
    result = DialogFallbackEngine().build_reply(
        policy=FakePolicy(),
        user_message="От тебя пахнет одеколоном",
        dialogue=[{"role": "assistant", "content": "Мы коллеги из смежной команды, следующая смена ждёт."}],
    )

    assert "личные оценки" in result
    assert "рабочей ситуации" in result


def test_peer_dialog_starts_with_root_cause() -> None:
    result = DialogFallbackEngine().build_reply(
        policy=FakePolicy(),
        user_message="Давайте обсудим ситуацию",
        dialogue=[{"role": "assistant", "content": "Между нами как коллегами возник сбой при передаче."}],
    )

    assert "разберем причину" in result


def test_client_dialog_advances_by_stage_plan() -> None:
    result = DialogFallbackEngine().build_reply(
        policy=FakePolicy(),
        user_message="Продолжим",
        dialogue=[{"role": "assistant", "content": "Вы клиент. Что предлагаете сделать следующим шагом?"}],
    )

    assert "ограничивает вас" in result

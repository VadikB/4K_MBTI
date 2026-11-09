import pytest
from pydantic import ValidationError
from Api.m7_completion_contracts import ReturnContinueRequest


def test_continue_accepts_open_clarification_state_but_rejects_terminal_states():
    payload=dict(position_no=1,expected_assessment_situation_id='synthetic-as',idempotency_key='synthetic-key')
    assert ReturnContinueRequest(**payload,expected_state='scenario_ended').expected_state=='scenario_ended'
    for terminal in ('closed','terminated','rejected','prepared'):
        with pytest.raises(ValidationError):ReturnContinueRequest(**payload,expected_state=terminal)

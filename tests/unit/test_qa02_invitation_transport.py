from datetime import datetime
from io import BytesIO
from urllib.error import HTTPError
from http.client import IncompleteRead
import json
import pytest
from Api import email_service as mail, invitation_outcomes as facts


class Response:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self):
        if isinstance(self.body, Exception): raise self.body
        return self.body


@pytest.mark.parametrize('provider,body,expected', [
    ('unisender_go', b'{"status":"success"}', None),
    ('postmark', b'{"ErrorCode":0}', None),
    ('unisender_go', b'{"status":"error","code":102}', 'provider_access'),
    ('unisender_go', b'{"status":"error","code":206}', 'provider_sender'),
    ('unisender_go', b'{"status":"error","code":901}', 'provider_limit'),
    ('postmark', b'{"ErrorCode":406}', 'provider_recipient'),
    ('postmark', b'{"ErrorCode":10}', 'provider_access'),
    ('postmark', b'{"ErrorCode":100}', 'provider_temporary'),
    ('postmark', b'{"ErrorCode":300,"Message":"recipient? secret"}', 'provider_rejected'),
    ('unisender_go', b'{"status":"error","code":999999}', 'provider_rejected'),
])
def test_typed_provider_receipts_only(monkeypatch, provider, body, expected):
    calls = []
    monkeypatch.setattr(mail.urlrequest, 'urlopen', lambda *a, **k: calls.append(a) or Response(body))
    if expected:
        with pytest.raises(mail.EmailDeliveryError) as failure: mail._dispatch(object(), provider)
        assert not isinstance(failure.value, mail.EmailDeliveryUncertainError)
        assert failure.value.reason_code == expected
        assert 'secret' not in str(failure.value)
    else: mail._dispatch(object(), provider)
    assert len(calls) == 1


@pytest.mark.parametrize('provider', ['unisender_go', 'postmark'])
@pytest.mark.parametrize('body', [b'{', b'', b'[]', b'null', b'{"status":"mystery"}', TimeoutError(), IncompleteRead(b'partial')])
def test_response_loss_after_dispatch_is_unknown_without_retry(monkeypatch, provider, body):
    calls = []
    monkeypatch.setattr(mail.urlrequest, 'urlopen', lambda *a, **k: calls.append(a) or Response(body))
    with pytest.raises(mail.EmailDeliveryUncertainError): mail._dispatch(object(), provider)
    assert len(calls) == 1


@pytest.mark.parametrize('status,body,outcome', [(500,b'proxy failure','unknown'), (500,b'{"status":"error","code":150}','unknown'), (422,b'invalid','failed')])
def test_http_status_does_not_invent_specific_reason(monkeypatch,status,body,outcome):
    def dispatch(*a, **k): raise HTTPError('https://synthetic.invalid',status,'error',{},BytesIO(body))
    monkeypatch.setattr(mail.urlrequest,'urlopen',dispatch)
    with pytest.raises(mail.EmailDeliveryError) as failure: mail._dispatch(object(),'unisender_go')
    assert isinstance(failure.value,mail.EmailDeliveryUncertainError) == (outcome == 'unknown')


@pytest.mark.parametrize('stored', ['secret provider traceback', '{', '{"contract":"invitation_reason/1","reason_code":"evil","reason_params":{"secret":"key"}}'])
def test_legacy_error_preserves_refusal_without_leaking_text(stored):
    value=facts.facts('error',stored)
    assert value['outcome']=='failed' and value['reason_code']=='failed_unclassified'
    assert value['reason_params']=={}


def test_persisted_metadata_is_bounded_safe_and_does_not_copy_recipient_list():
    stored=facts.encode_reason('error','provider_limit',{'retry_after_seconds':120,'secret':'SECRET'},recipients=['person@example.test']*500)
    assert 'SECRET' not in stored and 'person@example.test' not in stored
    assert len(stored)<500
    assert facts.stored_recipient_fingerprint(stored)==facts.recipient_fingerprint(['person@example.test'])
    assert facts.facts('error',stored)['reason_params']=={'retry_after_seconds':120}

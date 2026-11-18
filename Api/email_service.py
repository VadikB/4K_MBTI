from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from http.client import HTTPException as HTTPProtocolError

from Api.config import settings


logger = logging.getLogger("agent4k.email")


def _utc_expiry_label(expires_at: datetime) -> str:
    utc_value = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at.astimezone(timezone.utc)
    return utc_value.strftime("%d.%m.%Y %H:%M UTC")


class EmailDeliveryError(RuntimeError):
    def __init__(self, message, *, reason_code='provider_rejected', reason_params=None):
        self.reason_code = reason_code
        self.reason_params = reason_params or {}
        super().__init__(message)


class EmailDeliveryUncertainError(EmailDeliveryError):
    """Transport failed after dispatch; provider acceptance cannot be proven."""


def _provider_rejection(provider, result, http_status):
    # Only typed provider codes are diagnostic evidence. No message matching.
    key = 'ErrorCode' if provider == 'postmark' else 'code'
    code = result.get(key) if isinstance(result, dict) else None
    if type(code) is not int:
        code = None
    mapping = ({10: 'provider_access', 406: 'provider_recipient', 100: 'provider_temporary'}
               if provider == 'postmark' else
               {101: 'provider_access', 102: 'provider_access', 105: 'provider_access',
                106: 'provider_access', 215: 'provider_access', 206: 'provider_sender',
                901: 'provider_limit'})
    reason = mapping.get(code, 'provider_limit' if http_status == 429 else 'provider_rejected')
    return EmailDeliveryError('Почтовый сервис отклонил запрос.', reason_code=reason)


def _dispatch(req, provider):
    """No retry here: a lost/invalid response after POST cannot disprove acceptance."""
    try:
        try:
            with urlrequest.urlopen(req, timeout=15) as response:
                status = getattr(response, 'status', None) or response.getcode()
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            try:
                raw = exc.read()
            except (OSError, HTTPProtocolError):
                raw = b''
        try:
            result = json.loads(raw)
        except (ValueError, TypeError, UnicodeError):
            result = None
        if isinstance(result, dict):
            rejected = (type(result.get('ErrorCode')) is int and result['ErrorCode'] != 0
                        if provider == 'postmark' else result.get('status') == 'error')
            if rejected:
                if status >= 500 and not (provider == 'postmark' and result.get('ErrorCode') == 100):
                    raise EmailDeliveryUncertainError('Приём письма после сбоя сервиса не подтверждён.')
                raise _provider_rejection(provider, result, status)
            accepted = (result.get('ErrorCode') == 0 and type(result.get('ErrorCode')) is int
                        if provider == 'postmark' else result.get('status') in {'success', 'ok'})
            if accepted and 200 <= status < 300:
                return
        if 400 <= status < 500:
            raise _provider_rejection(provider, {}, status)
        raise EmailDeliveryUncertainError('Приём письма почтовым сервисом не подтверждён.')
    except (URLError, OSError, HTTPProtocolError) as exc:
        raise EmailDeliveryUncertainError('Ответ почтового сервиса не получен.') from exc


def _build_magic_link_email_payload(email: str, login_url: str, expires_at: datetime) -> dict[str, object]:
    expires_label = _utc_expiry_label(expires_at)
    subject = settings.auth_magic_link_subject
    text_body = (
        "Здравствуйте!\n\n"
        "Для входа в 4K Ассистент используйте эту одноразовую ссылку:\n"
        f"{login_url}\n\n"
        f"Ссылка действует до {expires_label}.\n"
        "Если это были не вы, просто проигнорируйте это письмо."
    )
    html_body = (
        "<p>Здравствуйте!</p>"
        "<p>Для входа в <strong>4K Ассистент</strong> используйте эту одноразовую ссылку:</p>"
        f'<p><a href="{login_url}">{login_url}</a></p>'
        f"<p>Ссылка действует до <strong>{expires_label}</strong>.</p>"
        "<p>Если это были не вы, просто проигнорируйте это письмо.</p>"
    )
    return {
        "From": settings.auth_magic_link_from_email,
        "To": email,
        "Subject": subject,
        "TextBody": text_body,
        "HtmlBody": html_body,
        "MessageStream": settings.postmark_message_stream,
    }


def _send_via_postmark(email: str, login_url: str, expires_at: datetime) -> None:
    if not settings.postmark_server_token:
        raise EmailDeliveryError("Postmark не настроен: отсутствует POSTMARK_SERVER_TOKEN.", reason_code="mail_not_configured")

    payload = _build_magic_link_email_payload(email, login_url, expires_at)
    raw_body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        "https://api.postmarkapp.com/email",
        data=raw_body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": settings.postmark_server_token,
        },
    )
    _dispatch(req, 'postmark')


def _send_via_unisender_go(*, email: str, subject: str, text_body: str, html_body: str) -> None:
    if not settings.unisender_go_api_key:
        raise EmailDeliveryError("Unisender Go не настроен: отсутствует UNISENDER_GO_API_KEY.", reason_code="mail_not_configured")
    payload = {
        "message": {
            "recipients": [{"email": email}],
            "subject": subject,
            "from_email": settings.auth_magic_link_from_email,
            "from_name": settings.auth_email_from_name,
            "body": {"plaintext": text_body, "html": html_body},
            "options": {},
        }
    }
    req = urlrequest.Request(
        settings.unisender_go_api_base_url + "/email/send.json",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": settings.unisender_go_api_key,
        },
    )
    _dispatch(req, 'unisender_go')


def send_magic_link_email(*, email: str, login_url: str, expires_at: datetime) -> None:
    provider = settings.email_provider
    if provider == "postmark":
        _send_via_postmark(email, login_url, expires_at)
        logger.info("Magic link email sent via Postmark")
        return
    if provider == "unisender_go":
        payload = _build_magic_link_email_payload(email, login_url, expires_at)
        _send_via_unisender_go(
            email=email,
            subject=str(payload["Subject"]),
            text_body=str(payload["TextBody"]),
            html_body=str(payload["HtmlBody"]),
        )
        logger.info("Magic link email sent via Unisender Go")
        return
    raise EmailDeliveryError(
        "Email-провайдер для magic link не настроен. Укажите EMAIL_PROVIDER=postmark и задайте POSTMARK_SERVER_TOKEN."
    )


def send_auth_action_email(*, email: str, action_url: str, expires_at: datetime, purpose: str) -> None:
    if purpose == "email_verification":
        subject = "Подтвердите email — 4K Ассистент"
        intro = "Подтвердите рабочий email, чтобы задать пароль:"
    elif purpose == "password_reset":
        subject = "Восстановление пароля — 4K Ассистент"
        intro = "Чтобы задать новый пароль, перейдите по ссылке:"
    elif purpose == "organization_invitation":
        subject = "Приглашение в 4K Ассистент"
        intro = "Вас пригласили пройти оценку. Чтобы продолжить, перейдите по персональной ссылке:"
    else:
        raise EmailDeliveryError("Неизвестный тип письма авторизации.")
    expires_label = _utc_expiry_label(expires_at)
    payload = {
        "From": settings.auth_magic_link_from_email,
        "To": email,
        "Subject": subject,
        "TextBody": f"Здравствуйте!\n\n{intro}\n{action_url}\n\nСсылка действует до {expires_label}.\nЕсли это были не вы, проигнорируйте письмо.",
        "HtmlBody": f'<p>Здравствуйте!</p><p>{intro}</p><p><a href="{action_url}">{action_url}</a></p><p>Ссылка действует до <strong>{expires_label}</strong>.</p><p>Если это были не вы, проигнорируйте письмо.</p>',
        "MessageStream": settings.postmark_message_stream,
    }
    if settings.email_provider == "unisender_go":
        _send_via_unisender_go(
            email=email,
            subject=subject,
            text_body=str(payload["TextBody"]),
            html_body=str(payload["HtmlBody"]),
        )
        logger.info("Auth action email sent via Unisender Go purpose=%s", purpose)
        return
    if settings.email_provider != "postmark":
        raise EmailDeliveryError("Email-провайдер не настроен. Укажите EMAIL_PROVIDER=unisender_go.", reason_code="mail_not_configured")
    if not settings.postmark_server_token:
        raise EmailDeliveryError("Postmark не настроен: отсутствует POSTMARK_SERVER_TOKEN.", reason_code="mail_not_configured")
    raw_body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        "https://api.postmarkapp.com/email",
        data=raw_body,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json", "X-Postmark-Server-Token": settings.postmark_server_token},
    )
    _dispatch(req, 'postmark')

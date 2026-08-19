from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from Api.config import settings


logger = logging.getLogger("agent4k.email")


class EmailDeliveryError(RuntimeError):
    pass


def _build_magic_link_email_payload(email: str, login_url: str, expires_at: datetime) -> dict[str, object]:
    expires_label = expires_at.strftime("%d.%m.%Y %H:%M UTC")
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
        raise EmailDeliveryError("Postmark не настроен: отсутствует POSTMARK_SERVER_TOKEN.")

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
    try:
        with urlrequest.urlopen(req, timeout=15) as response:
            status_code = getattr(response, "status", response.getcode())
            if status_code >= 400:
                raise EmailDeliveryError(f"Postmark вернул статус {status_code}.")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise EmailDeliveryError(
            f"Не удалось отправить письмо через Postmark: HTTP {exc.code}. {detail[:240]}"
        ) from exc
    except URLError as exc:
        raise EmailDeliveryError(f"Не удалось подключиться к Postmark: {exc.reason}") from exc


def _send_via_unisender_go(*, email: str, subject: str, text_body: str, html_body: str) -> None:
    if not settings.unisender_go_api_key:
        raise EmailDeliveryError("Unisender Go не настроен: отсутствует UNISENDER_GO_API_KEY.")
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
    try:
        with urlrequest.urlopen(req, timeout=15) as response:
            status_code = getattr(response, "status", response.getcode())
            response_body = response.read().decode("utf-8", errors="ignore")
            if status_code >= 400:
                raise EmailDeliveryError(f"Unisender Go вернул статус {status_code}.")
            try:
                result = json.loads(response_body or "{}")
            except json.JSONDecodeError as exc:
                raise EmailDeliveryError("Unisender Go вернул некорректный ответ.") from exc
            if str(result.get("status") or "").lower() not in {"success", "ok"}:
                raise EmailDeliveryError(f"Unisender Go отклонил письмо: {str(result)[:240]}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise EmailDeliveryError(f"Unisender Go вернул HTTP {exc.code}: {detail[:240]}") from exc
    except URLError as exc:
        raise EmailDeliveryError(f"Не удалось подключиться к Unisender Go: {exc.reason}") from exc


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
    else:
        raise EmailDeliveryError("Неизвестный тип письма авторизации.")
    expires_label = expires_at.strftime("%d.%m.%Y %H:%M UTC")
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
        raise EmailDeliveryError("Email-провайдер не настроен. Укажите EMAIL_PROVIDER=unisender_go.")
    if not settings.postmark_server_token:
        raise EmailDeliveryError("Postmark не настроен: отсутствует POSTMARK_SERVER_TOKEN.")
    raw_body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        "https://api.postmarkapp.com/email",
        data=raw_body,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json", "X-Postmark-Server-Token": settings.postmark_server_token},
    )
    try:
        with urlrequest.urlopen(req, timeout=15) as response:
            if getattr(response, "status", response.getcode()) >= 400:
                raise EmailDeliveryError("Провайдер отклонил письмо авторизации.")
    except (HTTPError, URLError) as exc:
        raise EmailDeliveryError(f"Не удалось отправить письмо авторизации: {exc}") from exc

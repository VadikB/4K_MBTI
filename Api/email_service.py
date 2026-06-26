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


def send_magic_link_email(*, email: str, login_url: str, expires_at: datetime) -> None:
    provider = settings.email_provider
    if provider == "postmark":
        _send_via_postmark(email, login_url, expires_at)
        logger.info("Magic link email sent via Postmark")
        return
    raise EmailDeliveryError(
        "Email-провайдер для magic link не настроен. Укажите EMAIL_PROVIDER=postmark и задайте POSTMARK_SERVER_TOKEN."
    )

"""Technical boundary: a profile edit is not an identity verification flow."""


def require_unchanged_email(current: str | None, requested: str | None) -> None:
    if str(current or '').strip().lower() != str(requested or '').strip().lower():
        raise ValueError('Изменение адреса входа через профиль недоступно. Сохраните подтверждённый email.')

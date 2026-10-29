"""Trusted operator-configured origins; never derive authentication URLs from Host."""
from __future__ import annotations

from ipaddress import ip_address
import json
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlsplit


def validate_public_origin(value: str, *, mode: str) -> str:
    if mode not in {"public", "local"}:
        raise ValueError("APP_ORIGIN_MODE must be public or local")
    invalid = ValueError("APP_BASE_URL must be a trusted origin; public mode requires HTTPS and a DNS hostname")
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise invalid
    try:
        parsed = urlsplit(value)
        host = str(parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        raise invalid from None
    if (parsed.scheme not in {"http", "https"} or not host or parsed.username is not None
            or parsed.password is not None or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or "?" in value or "#" in value):
        raise invalid
    if mode == "public":
        try:
            ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
        if (parsed.scheme != "https" or is_ip or "." not in host or host.endswith(".localhost")
                or host == "localhost" or not re.fullmatch(r"[a-z0-9.-]+", host)
                or len(host) > 253
                or any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in host.split("."))):
            raise invalid
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return f"{parsed.scheme}://{netloc}"


def build_public_link(origin: str, query: dict[str, str], *, mode: str) -> str:
    return validate_public_origin(origin, mode=mode) + "/?" + urlencode(query, quote_via=quote, safe="")


def read_deployment_origin(root: Path) -> str | None:
    """A dedicated public-only deployment file overrides legacy dotenv origin only."""
    path = root / ".public-origin.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid deployment public origin file") from exc
    if (not isinstance(value, dict) or set(value) != {"schema_version", "origin", "mode"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["mode"] != "public"):
        raise ValueError("Invalid deployment public origin schema")
    return validate_public_origin(value["origin"], mode="public")

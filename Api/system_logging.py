from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

from Api.database import get_connection

_handler_lock = threading.Lock()
_logging_guard = threading.local()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_json_dumps(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"serialization_error": True}, ensure_ascii=False)


def write_system_log(
    *,
    level: str,
    logger_name: str,
    message: str,
    event_type: str = "application",
    source: str = "backend",
    request_method: str | None = None,
    request_path: str | None = None,
    status_code: int | None = None,
    user_id: int | None = None,
    session_id: int | None = None,
    client_ip: str | None = None,
    payload: dict[str, Any] | None = None,
    traceback_text: str | None = None,
    created_at: datetime | None = None,
) -> None:
    if getattr(_logging_guard, "active", False):
        return
    _logging_guard.active = True
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO system_logs (
                    created_at,
                    level,
                    logger_name,
                    message,
                    event_type,
                    source,
                    request_method,
                    request_path,
                    status_code,
                    user_id,
                    session_id,
                    client_ip,
                    payload_json,
                    traceback_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    created_at or _utc_now(),
                    level[:20],
                    logger_name[:255],
                    message[:4000],
                    event_type[:100],
                    source[:100],
                    request_method[:16] if request_method else None,
                    request_path[:512] if request_path else None,
                    status_code,
                    user_id,
                    session_id,
                    client_ip[:128] if client_ip else None,
                    _safe_json_dumps(payload),
                    traceback_text[:12000] if traceback_text else None,
                ),
            )
    except Exception as exc:
        print(f"[system_logs] failed to persist log: {exc}", file=sys.stderr)
    finally:
        _logging_guard.active = False


class DatabaseLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_logging_guard, "active", False):
            return
        try:
            message = self.format(record)
            traceback_text = None
            if record.exc_info:
                traceback_text = "".join(traceback.format_exception(*record.exc_info))
            write_system_log(
                level=record.levelname,
                logger_name=record.name,
                message=message,
                event_type="python_logging",
                source="logging",
                traceback_text=traceback_text,
                created_at=datetime.fromtimestamp(record.created, tz=timezone.utc),
            )
        except Exception as exc:
            print(f"[system_logs] handler emit failed: {exc}", file=sys.stderr)


def configure_database_logging() -> None:
    with _handler_lock:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, DatabaseLogHandler):
                return
        handler = DatabaseLogHandler(level=logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root_logger.addHandler(handler)
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)

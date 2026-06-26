from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from Api.config import settings
from Api.database import get_connection

_handler_lock = threading.Lock()
_logging_guard = threading.local()
_managed_handler_flag = "_agent4k_managed_handler"
_managed_logger_flag = "_agent4k_managed_logger"


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


def _resolve_log_level(level_name: str) -> int:
    return getattr(logging, str(level_name or "INFO").upper(), logging.INFO)


def _build_log_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )


def _mark_handler(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _managed_handler_flag, True)
    return handler


def _is_managed_handler(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _managed_handler_flag, False))


def _clear_logger_handlers(target_logger: logging.Logger, *, managed_only: bool = False) -> None:
    handlers = list(target_logger.handlers)
    for handler in handlers:
        if managed_only and not _is_managed_handler(handler):
            continue
        target_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def _ensure_log_directory() -> Path:
    log_dir = Path(settings.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _build_runtime_handlers() -> list[logging.Handler]:
    formatter = _build_log_formatter()
    handlers: list[logging.Handler] = []
    if settings.log_to_stdout:
        stream_handler = _mark_handler(logging.StreamHandler(sys.stdout))
        stream_handler.setLevel(_resolve_log_level(settings.log_level))
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)
    if settings.log_to_file:
        log_dir = _ensure_log_directory()
        file_handler = _mark_handler(
            TimedRotatingFileHandler(
                log_dir / settings.log_filename,
                when=settings.log_rotation_when,
                backupCount=max(settings.log_backup_count, 1),
                encoding="utf-8",
                utc=True,
            )
        )
        file_handler.setLevel(_resolve_log_level(settings.log_level))
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

        error_handler = _mark_handler(
            TimedRotatingFileHandler(
                log_dir / settings.log_error_filename,
                when=settings.log_rotation_when,
                backupCount=max(settings.log_backup_count, 1),
                encoding="utf-8",
                utc=True,
            )
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        handlers.append(error_handler)
    return handlers


def configure_application_logging() -> None:
    with _handler_lock:
        root_logger = logging.getLogger()
        _clear_logger_handlers(root_logger)
        root_logger.setLevel(_resolve_log_level(settings.log_level))

        for handler in _build_runtime_handlers():
            root_logger.addHandler(handler)

        for logger_name in ("agent4k", "uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
            target_logger = logging.getLogger(logger_name)
            _clear_logger_handlers(target_logger)
            target_logger.setLevel(_resolve_log_level(settings.log_level))
            target_logger.propagate = True
            setattr(target_logger, _managed_logger_flag, True)


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

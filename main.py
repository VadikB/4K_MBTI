import logging
import os
import traceback
from time import perf_counter
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.requests import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from Api.database import ensure_core_schema
from Api.routes import router as users_router
from Api.system_logging import configure_database_logging, write_system_log
from Api.web_session_service import web_session_service

app = FastAPI(title="Agent_4K API")
app.include_router(users_router)
logger = logging.getLogger("agent4k")

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DEV_PREVIEWS_DIR = BASE_DIR / "dev_previews"

ensure_core_schema()
web_session_service.ensure_schema()
configure_database_logging()
logger.info("Agent_4K API startup complete")

app.mount("/favicons", StaticFiles(directory=WEB_DIR / "favicons"), name="favicons")
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
if os.getenv("AGENT4K_ENABLE_SCREEN_PREVIEWS") == "1":
    app.mount("/__screen-previews", StaticFiles(directory=DEV_PREVIEWS_DIR), name="screen-previews")


def _resolve_request_user(request: Request):
    if getattr(request.state, "_log_user_resolved", False):
        return getattr(request.state, "_log_user", None)
    token = request.cookies.get("agent4k_session_token")
    current_user = web_session_service.get_user_by_token(token) if token else None
    request.state._log_user = current_user
    request.state._log_user_resolved = True
    return current_user


@app.middleware("http")
async def disable_browser_cache(request: Request, call_next):
    started_at = perf_counter()
    current_user = _resolve_request_user(request)
    client_ip = request.client.host if request.client else None
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/web/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    write_system_log(
        level="INFO",
        logger_name="http.access",
        message=f"{request.method} {request.url.path} -> {response.status_code}",
        event_type="http_request",
        source="fastapi",
        request_method=request.method,
        request_path=str(request.url.path),
        status_code=response.status_code,
        user_id=current_user.id if current_user else None,
        client_ip=client_ip,
        payload={
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "query_params": dict(request.query_params),
        },
    )
    return response


@app.middleware("http")
async def log_unhandled_exceptions(request: Request, call_next):
    started_at = perf_counter()
    current_user = _resolve_request_user(request)
    client_ip = request.client.host if request.client else None
    try:
        return await call_next(request)
    except FastAPIHTTPException:
        raise
    except Exception as exc:
        traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        write_system_log(
            level="ERROR",
            logger_name="http.exception",
            message=f"Unhandled exception during {request.method} {request.url.path}: {exc}",
            event_type="http_exception",
            source="fastapi",
            request_method=request.method,
            request_path=str(request.url.path),
            status_code=500,
            user_id=current_user.id if current_user else None,
            client_ip=client_ip,
            payload={
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "query_params": dict(request.query_params),
            },
            traceback_text=traceback_text,
        )
        logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
        raise


@app.get("/")
def read_root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/__screens")
def read_screen_gallery() -> FileResponse:
    if os.getenv("AGENT4K_ENABLE_SCREEN_PREVIEWS") != "1":
        raise FastAPIHTTPException(status_code=404, detail="Screen previews are disabled.")
    return FileResponse(DEV_PREVIEWS_DIR / "screen-gallery.html")


@app.get("/__screen-canvas")
def read_screen_canvas() -> HTMLResponse:
    if os.getenv("AGENT4K_ENABLE_SCREEN_PREVIEWS") != "1":
        raise FastAPIHTTPException(status_code=404, detail="Screen previews are disabled.")
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" defer></script>',
        '<script src="/__screen-previews/preview-app-stub.js"></script>\n'
        '  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" defer></script>',
    )
    return HTMLResponse(html)

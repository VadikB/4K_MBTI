"""Bounded, fail-closed Typst rendering of an immutable report projection."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class TypstRenderError(RuntimeError):
    pass


def render_typst_report(payload: dict[str, Any], template_name: str) -> bytes:
    if template_name not in {"m8_participant_report_v2.typ", "m8_participant_report_v3.typ", "m8_report_comparison_v2.typ"}:
        raise TypstRenderError("PDF_TEMPLATE_UNSUPPORTED")
    template_path = Path(__file__).with_name("pdf_templates") / template_name
    if not template_path.is_file():
        raise TypstRenderError("PDF_TEMPLATE_UNAVAILABLE")
    try:
        timeout = float(os.getenv("AGENT4K_TYPST_TIMEOUT_SECONDS", "20"))
    except ValueError as exc:
        raise TypstRenderError("PDF_RENDER_TIMEOUT_INVALID") from exc
    if not 0 < timeout <= 120:
        raise TypstRenderError("PDF_RENDER_TIMEOUT_INVALID")
    fonts = Path(__file__).with_name("pdf_assets") / "fonts"
    with tempfile.TemporaryDirectory(prefix="agent4k-typst-") as directory:
        work = Path(directory)
        (work / "report-data.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        source = work / template_name
        source.write_bytes(template_path.read_bytes())
        if payload.get("radars"):
            from Api.m8_pdf_radar import write_radars
            try:
                write_radars(payload["radars"], work)
            except (TypeError, ValueError) as exc:
                raise TypstRenderError("PDF_RADAR_INVALID") from exc
        command = [sys.executable, str(Path(__file__).with_name("typst_pdf_worker.py")),
                   str(source), str(work / "report.pdf"), str(work), str(fonts)]
        try:
            process = subprocess.Popen(command, cwd=work, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
        except OSError as exc:
            raise TypstRenderError("PDF_RENDER_UNAVAILABLE") from exc
        try:
            _, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise TypstRenderError("PDF_RENDER_TIMEOUT") from exc
        if process.returncode != 0:
            raise TypstRenderError("PDF_RENDER_FAILED: " + stderr.decode("utf-8", errors="replace")[-1200:])
        output = work / "report.pdf"
        if not output.is_file() or not output.read_bytes().startswith(b"%PDF-"):
            raise TypstRenderError("PDF_RENDER_INVALID_OUTPUT")
        return output.read_bytes()

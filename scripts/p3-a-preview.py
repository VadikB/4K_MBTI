"""Owned PostgreSQL / real HTTP preview for P3-A. No paid provider or external mail.

The public long-AS fixture is inserted once, before snapshot persistence. It is
an explicit UI/runtime fixture, NOT case authoring, pilot admission or AC18 PATH.
Only this test entrypoint installs the existing component plan-policy boundary.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import html
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import NAMESPACE_URL, uuid4, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import check_port, environment, owned

FIXTURE = "p3-a-saved-public-as/1"
STATES = ("long", "short", "paused", "continue", "delayed", "unknown", "restored")


def source_identity(state):
    files = [ROOT / item for item in ("scripts/p3-a-preview.py", "web/index.html",
        "web/styles/screens/interview.css", "web/js/screens/interview.js", "web/js/wiring.js")]
    files += sorted((ROOT / "web/dist").glob("*.js"))
    return {"fixture": FIXTURE, "run_id": state["run_id"],
        "seed_base_sha": state["p3_a_revision"],
        "source_head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "startup_fingerprints": {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                                 for file in files}}


def fixture_environment(state):
    env = environment(state)
    env["AGENT4K_COMPONENT_PLAN_FIXTURE"] = "browser-component-plan-boundary/1"
    return env


def read_state(path):
    state = json.loads(path.read_bytes())
    if (state.get("p3_a_fixture") != FIXTURE or state.get("provider_mode") != "disabled"
            or state.get("gateway") != 1):
        raise ValueError("P3_A_OWNED_DISABLED_PROVIDER_FIXTURE_REQUIRED")
    with owned(state):
        pass
    return state


def install(state):
    from tests.browser_component_app import install as install_component
    install_component(state)
    from Api import m5_storage
    original = m5_storage.build_assessment_situation

    def public_as_fixture(**kwargs):
        situation, execution = original(**kwargs)
        profile = kwargs["profile_ref"]["id"].rsplit(":", 1)[-1]
        if int(profile) in state["p3_a_long_profiles"]:
            situation = deepcopy(situation)
            public = situation["participant_payload"]
            public["title"] = "Синтетическая длинная ситуация P3-A"
            public["introduction"] = (
                "Техническая ситуация для проверки чтения, прокрутки и ввода. "
                "Она не является методологически принятой AS или допуском пилота.")
            public["initial_materials"] = [{
                "material_id": f"P3A-PUBLIC-{index:02}",
                "title": f"Синтетический публичный материал {index}",
                "text": (f"Материал {index}. Участники обсуждают технический пример: "
                         "проверить исходные условия, зависимости, доступные сведения и следующий шаг. "
                         "Все имена и обстоятельства вымышлены. ") * 5,
            } for index in range(1, 13)]
        return situation, execution

    m5_storage.build_assessment_situation = public_as_fixture


def prepare(path):
    state = read_state(path)
    from Api.database import get_connection
    with get_connection() as connection:
        participants = connection.execute("""SELECT u.id,u.email,p.id AS profile_id
            FROM users u JOIN assessment_personalized_profiles p ON p.user_id=u.id
            WHERE u.email IN ('participant@example.test','other@example.test') AND p.status='ready'
            ORDER BY u.id""").fetchall()
    if len(participants) != 2:
        raise ValueError("P3_A_TWO_SEEDED_PARTICIPANTS_REQUIRED")
    state["p3_a_long_profiles"] = [row["profile_id"] for row in participants
                                     if row["email"] == "participant@example.test"]
    path.write_text(json.dumps(state))
    install(state)
    from Api.m10_product_flow import start_or_resume, read_runtime
    previews = {}
    with get_connection() as connection:
        for row in participants:
            started = start_or_resume(connection, user_id=row["id"], profile_id=row["profile_id"],
                                      key="p3-a-preview-initial")
            cycle = str(started["plan"]["cycle_id"])
            model = read_runtime(connection, cycle_id=cycle)
            current = model["current_situation"]
            previews["long" if row["email"] == "participant@example.test" else "short"] = {
                "email": row["email"], "user_id": row["id"], "cycle_id": cycle,
                "assessment_situation_id": current["assessment_situation_id"],
            }
        connection.commit()
    state["p3_a_previews"] = previews
    state["p3_a_revision"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    path.write_text(json.dumps(state))
    print("P3-A saved synthetic AS ready; real PostgreSQL; provider disabled; NOT AC18 PATH")


def create_app(path):
    state = read_state(path)
    identity = source_identity(state)
    install(state)
    from main import app
    from fastapi import HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import urllib.error
    import urllib.request

    @app.get("/p3-a/identity")
    def public_identity():
        return identity

    # Transport-only fault injection: the real endpoint commits first. Runtime,
    # auth, saved turns and SQL are never fulfilled by a browser/network mock.
    @app.middleware("http")
    async def delivery_fault(request, call_next):
        response = await call_next(request)
        if (request.method == "POST" and "/m5/situations/" in request.url.path
                and request.url.path.endswith("/turns") and response.status_code < 300):
            mode = request.cookies.get("p3_a_delivery")
            if mode == "delayed":
                await asyncio.sleep(6)
            elif mode == "unknown":
                return JSONResponse({"detail": "P3_A_SYNTHETIC_RESPONSE_LOST_AFTER_REAL_COMMIT"}, status_code=503)
        return response

    @app.get("/p3-a/", response_class=HTMLResponse)
    def menu():
        current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        links = "".join(f'<li><a href="/p3-a/open/{mode}">{label}</a></li>' for mode, label in [
            ("long", "Длинная активная AS"), ("short", "Короткая активная AS"),
            ("paused", "Подтверждённая сервером пауза"),
            ("continue", "Разрешённое возобновление control (R1 Continue: NOT_PREPARED)"),
            ("delayed", "Задержка ответа отправки на 6 секунд"),
            ("unknown", "Неизвестный клиенту исход: ответ потерян после сохранения"),
            ("restored", "Восстановленный диалог: один сохранённый synthetic Turn"),
        ])
        return ("<!doctype html><html lang=ru><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                "<style>body{font:18px/1.6 system-ui;max-width:52rem;margin:32px auto;padding:0 20px}li{margin:12px 0}</style>"
                "<title>P3-A — визуальная проверка</title><h1>P3-A: синтетический просмотр</h1>"
                f"<p>Seed base SHA: <code>{html.escape(state['p3_a_revision'])}</code>. "
                f"Текущий HEAD: <code>{current}</code>; worktree dirty={str(dirty).lower()}. "
                "Текущие исходники worktree. Real HTTP + owned PostgreSQL; test gateway; без платной генерации.</p>"
                f"<ul>{links}</ul><p>Длинная AS и её история общие для состояний; короткая AS принадлежит "
                "другому синтетическому участнику. Вход выполняется автоматически через штатный endpoint. "
                "Пауза, отправка и возобновление control сохраняют реальные изменения на этом временном стенде. "
                "R1 explicit return-state/return-continue не подготовлен: нужен checkpoint 3Б.</p>"
                "<p>Проверьте 320/390/430/768/1440 px, 200%, начало/конец истории, многострочный "
                "черновик и reload. Эмуляция уменьшенной высоты не доказывает физическую экранную клавиатуру "
                "или iOS Safari/Android Chrome. VISUAL_ACCEPTED назначает владелец.</p></html>")

    @app.get("/p3-a/open/{mode}")
    async def open_state(mode: str):
        if mode not in STATES:
            raise HTTPException(404)
        target = state["p3_a_previews"]["short" if mode == "short" else "long"]
        origin = f"http://127.0.0.1:{state['port']}"
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        async def call(method, path, payload=None):
            def perform():
                request = urllib.request.Request(origin + path, method=method,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Content-Type": "application/json"})
                try:
                    response = client.open(request, timeout=15)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    return response.code, json.loads(response.read()), response.headers
            return await asyncio.to_thread(perform)
        login = await call("POST", "/users/auth/email/password-login", {
            "email": target["email"], "password": state["password"]})
        if login[0] != 200:
            raise HTTPException(500, "P3_A_SYNTHETIC_LOGIN_FAILED")
        prefix = f"/users/assessment/m7/cycles/{target['cycle_id']}"
        model = await call("GET", f"/users/assessment/cycles/{target['cycle_id']}/runtime")
        if model[0] == 200:
            paused = model[1]["status"]["collection_status"] == "paused"
            want_paused = mode in ("paused", "continue")
            if paused != want_paused:
                controlled = await call("POST", prefix + "/control", {
                    "action": "pause" if want_paused else "resume", "reason": "p3_a_synthetic_preview",
                    "idempotency_key": str(uuid4())})
                if controlled[0] != 200:
                    raise HTTPException(500, "P3_A_SYNTHETIC_CONTROL_FAILED")
        if mode == "restored":
            fixture = json.loads((ROOT / "tests/browser/fixtures/v1.json").read_text())
            sent = await call("POST", f"/users/assessment/m5/situations/{target['assessment_situation_id']}/turns", {
                "request_id": f"p3-a-restored-{state['run_id']}",
                "turn_id": str(uuid5(NAMESPACE_URL, f"p3-a-restored:{state['run_id']}")),
                "content": fixture["answer"]})
            if sent[0] != 200:
                raise HTTPException(500, "P3_A_SYNTHETIC_RESTORED_TURN_FAILED")
        destination = f"/?screen=interview&cycle_id={target['cycle_id']}"
        # The selector switches synthetic actors on this isolated origin. Clear
        # old actor/profile localStorage, keeping AS-scoped sessionStorage drafts.
        # Otherwise main correctly rejects the previous actor's session-bootstrap.
        result = HTMLResponse("<!doctype html><meta charset=utf-8><title>P3-A вход</title>"
            "<p>Открываем синтетическое состояние…</p><script>"
            "Object.keys(localStorage).filter(k=>k.startsWith('agent4k.')).forEach(k=>localStorage.removeItem(k));"
            f"location.replace({json.dumps(destination)});</script>")
        for cookie in login[2].get_all("set-cookie", []):
            result.headers.append("set-cookie", cookie)
        # This cookie controls only transport fault injection on the owned test app.
        result.set_cookie("p3_a_delivery", mode if mode in ("delayed", "unknown") else "normal",
                          httponly=True, samesite="strict")
        return result

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "serve", "destroy", "inspect", "_inspect", "_prepare", "_serve"))
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18931)
    args = parser.parse_args()
    path = args.state.resolve()
    if args.action == "create":
        if path.exists():
            raise ValueError("P3_A_STATE_EXISTS_USE_SERVE_OR_NEW_PATH")
        check_port(args.port)
        def cli(action):
            subprocess.run([sys.executable, str(ROOT / "scripts/test_stand.py"), action,
                            "--state", str(path), "--port", str(args.port), "--gateway", "1",
                            "--provider", "disabled"], cwd=ROOT, check=True)
        cli("create")
        state = json.loads(path.read_bytes())
        state.update(p3_a_fixture=FIXTURE, qa_orchestration=True, browser_scenario="acceptance-v1",
                     component_plan_fixture="browser-component-plan-boundary/1")
        path.write_text(json.dumps(state))
        cli("bootstrap")
        cli("seed")
        subprocess.run([sys.executable, __file__, "_prepare", "--state", str(path)],
                       cwd=ROOT, env=fixture_environment(state), check=True)
        print(f"Preview prepared: http://127.0.0.1:{args.port}/p3-a/")
    elif args.action == "destroy":
        read_state(path)
        subprocess.run([sys.executable, str(ROOT / "scripts/test_stand.py"), "destroy", "--state", str(path)],
                       cwd=ROOT, check=True)
    elif args.action == "_prepare":
        prepare(path)
    elif args.action == "inspect":
        state = read_state(path)
        subprocess.run([sys.executable, __file__, "_inspect", "--state", str(path)],
                       cwd=ROOT, env=fixture_environment(state), check=True)
    elif args.action == "_inspect":
        state = read_state(path)
        from Api.database import get_connection
        from Api.m5_case_runtime import checksum
        with get_connection() as connection:
            records = []
            for kind, preview in state["p3_a_previews"].items():
                situation = connection.execute("""SELECT id,status,snapshot_json,snapshot_checksum
                    FROM m5_assessment_situations WHERE assessment_situation_id=%s""",
                    (preview["assessment_situation_id"],)).fetchone()
                turns = connection.execute("""SELECT turn_id::text AS turn_id,speaker_type,request_id
                    FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no""",
                    (situation["id"],)).fetchall()
                request_ids = [row["request_id"] for row in turns if row["speaker_type"] == "assessee"]
                records.append({"kind": kind, "assessment_situation_id": preview["assessment_situation_id"],
                    "status": situation["status"],
                    "snapshot_checksum_valid": checksum(situation["snapshot_json"]) == situation["snapshot_checksum"],
                    "assessee_turns": len(request_ids), "duplicate_assessee_request_ids": len(request_ids) != len(set(request_ids)),
                    "turn_ids": [row["turn_id"] for row in turns]})
        print(json.dumps({"run_id": state["run_id"], "scope": "owned synthetic PostgreSQL readback", "situations": records}, indent=2))
    elif args.action == "serve":
        state = read_state(path)
        check_port(state["port"])
        os.execve(sys.executable, [sys.executable, __file__, "_serve", "--state", str(path)], fixture_environment(state))
    else:
        state = read_state(path)
        import uvicorn
        uvicorn.run(create_app(path), host="127.0.0.1", port=state["port"], access_log=False)


if __name__ == "__main__":
    main()

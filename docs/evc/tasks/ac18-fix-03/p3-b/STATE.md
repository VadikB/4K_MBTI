# P3-B STATE

- Base: `origin/main=023bf85ec796d212d29b33218d906a1ed2023941`,
  APP_RELEASE `2.0.86`; локальный PATCH-кандидат `2.0.87`.
- Branch/worktree: `codex/ac18-p3-b-time-return`,
  `/Users/vadim_bogachev/Developer/4K/worktrees/ac18-p3-b-time-return`.
- Implementation commits: `ab03144cf465b5213a722a26f9cf6538af64235e`,
  `c06f7a74822c338767eb6f3e81fa5fe15e654c69`; task-state commit
  `d9e74914f111606706246a4db94ae76f827edbf4`; предыдущий docs/head
  `758b492982eab38a31f932799e9f03deef804c8e`. Release commit
  `43c42c2f4b0b825007af97f844f2d3946e055687`.
- Scope: P3-T03/T04/T05, AC04–08 и локальная часть AC10; P3-A/P3-I вне scope.
- Checkpoint для P3-A: S0=`023bf85e`; fixture contract — `cycle_id` + current AS
  задают scope, `participant_payload` — единственный вход условий, trace — сохранённая
  история, `route.progress.total_positions` — длина frozen `plan.route`, completed —
  серверный факт route; timing `0` известен, null/missing/invalid неизвестен;
  pause только по server collection/return action; Continue повторяет один key и
  сначала делает readback. Policy `sales-pilot-return-r1@2.0`, checksum
  `1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14`.
- Владение: P3-B меняет только time/progress/return зоны `interview.js`, M7 runtime
  consumers и owned tests; dialogue/message/scroll/draft P3-A не затронуты.
- Сделано: saved-plan denominator в runtime/return-state; unknown timing не
  превращается в `0`/«Без лимита»; Continue сохраняет idempotency key и выполняет
  readback при неизвестном исходе. Return-card синхронизирует верхний прогресс
  с планом; ключ команды переживает rerender/reload, а после подтверждённого
  active runtime удаляется. Поздние ответы другого Cycle/пользователя не рендерятся.
- Visual states: `node scripts/p3b_visual_preview.mjs` →
  `http://127.0.0.1:18769/p3b-visual` на той же машине; шесть синтетических
  состояний, ни БД, ни LLM, ни рабочие данные. `VISUAL.md`, `CHECKS.csv`,
  `PR_BODY.md`, `QUESTIONS.md` фиксируют локальную передачу.
- Прямой ответ владельца «следующий patch» принят только для локального
  `version_bump`: `npm run ready:prepare -- --candidate 2.0.87` — PASS,
  release gate `python3.12 scripts/check_release_version.py --base-ref origin/main`
  — PASS. `origin/main` перепроверен и не изменился. Preview `/users/version`
  возвращает `2.0.87`; исходный r1 bundle относится к pre-release SHA и не
  должен использоваться вместо кандидата.
- Проверки: frontend contract — PASS 3; все frontend tests — PASS 157;
  ESLint — PASS; Python compile — PASS; M7 unit — PASS 3; HTTP P03 — PASS 2;
  browser P03/P3-B — PASS 4 (включая accepted/lost Continue и reload);
  полный M7 owned PostgreSQL integration — PASS 31 на исходном продуктном diff,
  новая runtime projection assertion — адресно PASS 1; backend local minimum —
  PASS 977 (362 deselected) на неизменённом backend после `ab03144c`;
  frontend build — PASS; `git diff --check` — PASS. Visual Chromium: 24/24
  обычных viewport/state PASS, 200% text на 390 px — FAIL (543 px overflow).
  Первые browser/PG попытки получили sandbox `EPERM`; разрешённые локальные
  loopback-повторы прошли. Ошибочный запрос отсутствующего
  `tests/unit/test_m10_product_flow.py` не являлся тестовым прогоном;
  применимый projection-файл вошёл в backend minimum. Два повторных вызова
  Python compile сначала не запустились: `.venv` находится в root checkout,
  а системный Python пытался писать в закрытый cache. Повтор с
  `PYTHONPYCACHEPREFIX=/private/tmp/p3b-pycache` — PASS.
- На release commit `43c42c2f`: frontend 157 PASS, backend minimum 977 PASS,
  HTTP P03 2 PASS, browser P03/P3-B 4 PASS, visual 24 обычных состояния PASS,
  `npm run lint:js`, адресный ESLint preview, build, version gate и diff — PASS.
  M7 owned PostgreSQL 31 PASS относится к предыдущему commit с тем же backend;
  version-only изменение Python-логики не затрагивает. Visual 200% остаётся FAIL.
- Граница 3А: topbar и textarea при удвоенном тексте переполняют мобильный
  viewport; evidence `.test-stand/p3-b-visual/active-long-390-text200.png` и
  manifest. Checkpoint для 3А дополнен этим фактом, но согласованный канал
  отправки не определён. Физические iOS Safari/Android Chrome и решение владельца
  — NOT_RUN. Общий P3-AC10 не принят.
- Саморевью по `docs/evc/review-checklist.md`: scope и API/БД/артефакты
  сохранены; новые предметные defaults, secrets и реальные данные отсутствуют;
  регрессии возврата и local minimum приложены, откат — revert продуктовых и
  release commits и `npm run build:web`. Незакрытые пункты: 200%/физические устройства,
  human visual review и CI точного release-кандидата.
- Внешние этапы: `branch_push` и draft PR прямо разрешены ответом владельца
  «да» на вопрос об этих действиях с открытым FAIL. Ветка опубликована;
  draft PR #199: `https://github.com/VadikB/4K_MBTI/pull/199`. На SHA
  `0b26224d27c6f79df8816d04398be1b7d7ec9a66` быстрые CI job
  `frontend`/`pytest` — PASS, Full verification — SKIPPED для draft;
  актуальный итог последнего SHA — на вкладке Checks PR. Локальный
  `version_bump=2.0.87` разрешён ранее ответом «следующий patch».
  `merge`/`deploy` — NOT_RUN, перевод в Ready и приёмка AC10 при открытом FAIL
  не заявлены.
- OPS01 исторического test Cycle — NOT_RUN: доступ к test и отдельный внешний этап
  в текущем запросе не подтверждены.

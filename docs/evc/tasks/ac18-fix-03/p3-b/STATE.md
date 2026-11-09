# P3-B STATE

## Совместный кандидат P3-A+P3-B — 09.11.2026

- Существующие ветка/worktree/draft PR #199 сохранены. База обоих результатов:
  `023bf85ec796d212d29b33218d906a1ed2023941` (`origin/main`, APP_RELEASE
  `2.0.86`). Передача P3-A R1: ZIP SHA256
  `252be1721ac170ddb832614e804078d03d34d7db6b40246c5a3272bd79ad4f46`,
  manifest/base `023bf85e`, проверенный code SHA
  `7f0a77be8ba456a4e6bb52bb676d623672d8dcbc`, delivery head
  `5b502f13d72f63b3e75531e9ef8accd084f0913c`. `SHA256SUMS.txt`,
  `git bundle verify`, base→head `CHANGED_FILES.txt` и отсутствие product-diff
  между code/delivery SHA — PASS. Ветка P3-A не опубликована в `origin`;
  проверенный bundle загружен только в `FETCH_HEAD`.
- Происхождение: P3-A `f55be32a` → `f6ccbb2a` → `65e33d96` → `7f0a77be` →
  `5b502f13`; P3-B head до объединения `8be8e8e5db0ef9ad397d74a0753ea8d5ba26d23d`.
  Штатный `git merge --no-ff` создал `e343ecc3dc775319088a4f3ad46727494fcb684b`
  с обоими родителями; тестовая стабилизация —
  `abce5f73cb452a6a71e9369e7a45d94533436a4e`. Кодовый кандидат:
  `abce5f73cb452a6a71e9369e7a45d94533436a4e`.
  Новая интеграционная ветка и PR не создавались.
- Конфликт в `web/js/screens/interview.js` разрешён с сохранением переменных
  R1 Continue и P3-A scroll/delivery; `web/dist` пересобран штатно.
  Переполнение 390 px/200% устранено слоем P3-A. Общий загрузчик теперь
  проверяет owner, Cycle, AS, identity epoch, screen и poll generation до
  применения runtime/return-state и после ожидания presence. Поздний ответ
  старого контекста не рендерит AS и не меняет новый scope; адресная регрессия
  `tests/frontend/p3-b-loader-scope.test.mjs` — 4 PASS.
- Проверки **сочетания**, а не сумма отдельных проверок: Node frontend
  192/192 PASS; `npm run lint:js`, `npm run build:web`, `git diff --check` PASS;
  backend minimum 977 PASS (362 deselected); M7 owned PostgreSQL integration
  31 PASS на отдельной `product4k_pytest_*` БД; HTTP P03 2 PASS; custom real
  HTTP/PG browser P3-A 12 PASS; browser P03/P3-B 4 PASS; визуальный стенд
  24 обычных состояния + 390 px/200% PASS (documentWidth=390,
  viewportWidth=390, offenders=[]). Первый полный P3-A browser прогон дал
  11 PASS/1 FAIL: тестовый вход стартовал до завершения async logout;
  после ожидания завершения выхода адресный 1 PASS и полный 12 PASS.
  Первичное evidence и команды — `CHECKS.csv`, `.test-stand/p3-b-visual/manifest.json`
  и `.test-stand/p3-a/**/evidence/` (игнорируемые локальные synthetic outputs).
- `npm run ready:prepare -- --candidate 2.0.87` после свежего `git fetch
  origin main` — PASS: base не сдвинулся, release `2.0.87`, product paths 63,
  сборка повторена. Это локальный preflight, не перевод draft PR в Ready.
- Исторические FAIL не переписаны: P3-B `43c42c2f`/AC10 543 px при 390 px;
  P3-A `5b502f13`/OPEN_SHARED_3B stale loader; более ранние P3-A
  unknown/text200/initial-readiness перечислены в переданном `CHECKS.csv`.
  Для нового сочетания технический AC10 subset PASS, но физические iOS/Android,
  native text zoom/software keyboard, owner visual acceptance и полный путь
  AC18/исторический TEST Cycle — NOT_RUN. Whole AC10/визуальная приёмка не объявлены.
- Источники: README.md, CONTRIBUTING.md, `docs/evc/agent-workflow.md`,
  `verification-matrix.md`, `artifact-recipe.md`, Product context/Registry,
  Change 01 и task manifest; адресные контракты ADR-002, M7 R1 v2 и тесты.
  Policy `sales-pilot-return-r1@2.0`, checksum
  `1121db8c84b6997ee427264a589b5db088588e134734d8ae0dbc0d2220a36f14`
  не менялась. Не найдено новых предметных норм или оснований для CURRENT M1.
  Публичные API, схема БД, runtime-артефакты и рабочие данные не менялись;
  платный LLM не использован. Откат — revert merge и связанных fix/test-коммитов,
  затем `npm run build:web`; миграции нет.
- Дальше: push только существующей ветки и проверка quick CI на новом head;
  human review/визуальная приёмка и явный допуск Ready требуются до full CI.
  Merge в `main`, TEST deploy и pilot promotion не выполняются без условий
  `docs/evc/verification-matrix.md` и решения владельца. 3И/OPS01 остаются
  отдельными зависимостями.

## История P3-B до объединения

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

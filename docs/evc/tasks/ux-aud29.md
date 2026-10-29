# UX-AUD29 — пилот «Специалист» и критические UX-переходы

Дата: 2026-10-29. Ветка: `codex/ux-aud29`. База: `b1f9a73704456cc45b1dcde265c5b8b5463e1d82`,
release `2.0.36`; кандидат `2.0.37`. Один пакет / один PR.

## Результат и границы

Исправить TASK01–TASK08 из UX-AUD29 без изменения методологии, оценочных формул,
опубликованных snapshots и принятых прототипов. Пилот допускает только
`specialist_expert`; должность и рабочие задачи остаются контекстом. Роль и
техническая конфигурация не выбираются участником, администратором или
суперадминистратором.

В пакет входят auth/header/footer, атомарное назначение, onboarding textarea,
язык отчёта, текст возврата, регрессия первого сохранения/подтверждения,
диагностика подготовки и семантика снятия member-связи. Реальный provider и
публикация нового каталога не входят: отсутствие допущенной Specialist-AS
фиксируется как точный внешний блокер, а не обходится fixture или публикацией.

## Прочитанные источники

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`;
- `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`,
  `task-template.md`, `review-checklist.md`;
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`, Change 01,
  `docs/methodology/source-sets/2026-10-01/manifest.json`, M1 v1.4;
- `docs/adr/002-cycle-as-dialogue-contracts.md`,
  `docs/evc/change01-traceability.md`;
- `docs/evc/tasks/pers-functional-personalization.md`,
  `docs/evc/tasks/sls04-sales-return-budget.md`, M7 return policy v2;
- UX-AUD29 revision 2: `README`, `FINDINGS`, `SOURCE_PRIORITY`, TASK01–TASK08,
  `ACCEPTANCE` и применимые `reference/*`.

Архив UX-AUD29 проверен по `SHA256SUMS.txt`: все файлы `OK`. Прототипы и
reference-файлы не изменялись. Change 01 остаётся WORKING, M1 v1.4 —
FROZEN / CURRENT=NO; они не переключают runtime автоматически.

## Требование → код → расхождение → проверка

| ID | Фактическое изменение | Проверка |
| --- | --- | --- |
| 01 | Бренд вынесен над auth-card; release показывается только полной строкой в общем Onest-footer; нейтральное восстановление сессии сохранено | browser auth/reload/error, 1440/390/320 |
| 02 | Добавлен явный операторский `organization_assessment_pilot_bindings`; API проверяет published Specialist/config/catalog scope, связывает assignment атомарно и запрещает source override; UI делает один запрос без selectors | HTTP idempotency/override; PATH29 DB |
| 03 | Textarea 48–120 px, resize disabled, восстановленная высота, desktop Enter / Shift+Enter, IME/pending guard | browser keyboard/computed style |
| 04 | В participant Report заменены Cycle/M2/Evidence/«допустимый вклад» и нормативная формулировка на предметные пояснения без изменения чисел | frontend + M8/radar browser |
| 05 | Текст возврата выбирается по `resume_mode`; R1 обещает ту же AS, неизвестная политика не обещает замену | frontend policy regression |
| 06 | Существующая защита draft/generation/identity/unknown outcome подтверждена real-browser regression; первое сохранение, author, recipients, confirm/readback/reload | `adm28-real.spec.mjs` |
| 07 | Подготовка сохраняет operation/error и показывает безопасный точный код отсутствия допущенной Specialist-AS | unit projection + PATH29 DB |
| 08 | UI явно снимает участие, объясняет сохранение аккаунта; DB-regression проверяет delete/readback/re-add/same user/no extra invitation/login | PATH29 DB |

## Доказанная причина и состояние

- TASK02: ложное завершение создавалось до binding; frontend намеренно выполнял
  первый POST без источников, затем требовал selectors и второй POST. Исправлено.
- TASK06: на базе `b1f9a73` механизм generation/identity/draft уже закрывал
  поздний GET, потерянный POST-response и смену scope. Real-browser readback
  подтверждает первое сохранение и reload; отдельная новая причина потери данных
  на этой базе не воспроизвелась, поэтому спекулятивный механизм не добавлялся.
- TASK08: DELETE корректно удаляет только `role='member'`; наблюдение «уже
  зарегистрирован» объяснялось сохранённым глобальным аккаунтом. Исправлены текст
  и статусы; DB-readback подтвердил снятие и повторное добавление того же `user_id`.
- TASK07: на изолированном текущем контролируемом каталоге первая нарушенная
  граница — `M7_NO_ADMISSIBLE_CASE` для `specialist_expert`. Создание Cycle/AS не
  произошло. Код причины теперь доступен участнику безопасной формулировкой.

## Проверки и выпуск

Локальный минимум на кандидате `2.0.37`:

- `npm run lint:js` — PASS;
- `npm run build:web` — PASS, versioned `web/dist` пересобран;
- `node --test tests/frontend/*.test.mjs` — 90 PASS;
- `npm run test:backend` — 655 PASS, 260 deselected;
- `npm run test:backend:http` — 82 PASS, 12 deselected;
- `npm run test:backend:integration` с явными изолированными
  `STAND_ADMIN_URL`/`TEST_DATABASE_URL` — 172 PASS, 2 штатных real-LLM SKIP,
  741 deselected;
- критический browser-набор auth/assignment/textarea/ADM28 — 16 PASS;
- browser report/radar — 6 PASS;
- `adm28-real.spec.mjs` после version bump — 1 PASS: draft, author,
  recipients, confirm/readback/reload, assignment и размеры 1440/1280/390/320;
- изолированный PATH29 — 1 PASS: atomic binding, точный blocker подготовки,
  delete/readback/re-add с тем же `user_id` без нового invitation и login;
- real-browser PATH29 — 1 PASS: атомарное Specialist-назначение, сохранение после
  reload, durable preparation и явный старт первой синтетической Specialist-AS;
- `git diff --check`, `node --check`, Python `py_compile` — PASS.

Screenshot-readback управления сохранён в
`docs/evc/tasks/artifacts/ux-aud29/management-{1440,1280,390,320}.png`.
Реальный provider smoke — `NOT_RUN/BLOCKED`, пока оператор не укажет допущенный
Specialist-каталог и не создаст binding штатным
`scripts/configure_specialist_pilot_binding.py`. CI `frontend` + `pytest` и
deploy/readback test фиксируются после создания PR.

После merge автоматический `deploy-test`; затем HTTPS readback версии/SHA,
повтор первого сохранения, полного назначения и, при допущенном каталоге,
подготовки первой AS и явного старта. Визуальная приёмка владельцем/Катей остаётся
отдельным состоянием и не объявляется выполненной разработчиком.

## Риски и откат

- Схема добавляет явную таблицу binding без изменения старых assignments/snapshots.
- Без binding назначение получает определённый `PILOT_BINDING_NOT_CONFIGURED`,
  а не случайный default.
- Откат: revert PR возвращает `2.0.36`; новая таблица совместима и может остаться
  неиспользуемой. Записи binding не удаляются автоматически. Старые Cycle/AS,
  профили, результаты и member-история не пересчитываются.

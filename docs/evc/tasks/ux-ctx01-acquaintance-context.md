# UX-CTX01 — ответы знакомства в контексте оценки

## Результат

Три подтверждённых ответа корпоративного знакомства сохраняются с явной схемой и
происхождением, входят в подтверждённый `UserContext` и frozen
`PersonalizedProfile`, а затем без повторного чтения текущей анкеты проходят в
вход M5 и сохранённый M8 Results/Report.

## Область

- Включено: корпоративные вопросы W02, assignment scope, неизменяемая ревизия
  ответов, связывание с M4, точный профиль late-readiness, исторические snapshots.
- Не входит: трактовка ответов как Evidence, изменение фактической оценки,
  университетский вариант, разрешение содержательных конфликтов, UI-редизайн.

## Источники и решения

- Постановка: `UX-CTX01_Acquaintance_Context_Flow_2026-10-17.txt`, редакция 1.0,
  SHA-256 `ec770c5ec18fadf9986e239631c105e32576e055d21833e6dd7434dd1c976532`.
- База: `main` / `ca6b95ff8e883f6bf7d747cb6dcbe89a94fc779b` после UX-REP01.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe,
  Change 01 и manifest, ADR-002, M1 v1.4, Registry, W02/10.5 задачи, M4/M5/M8
  runtime-код и относящиеся тесты.
- Архитектурная граница: W02 фиксирует слова участника; M4 владеет UserContext и
  PersonalizedProfile; M5 потребляет frozen профиль; PM-05/PM-07 сохраняют и
  представляют тот же исторический snapshot. Ответы не являются Evidence.
- Три канонических вопроса — версионируемая часть подтверждённого briefing; для
  старых произвольных briefing сохранение W02 совместимо, но автоматическое
  предметное связывание закрыто fail-safe.
- Артефакт: `assessment_definitions/questionnaires/participant_context/corporate/1.0`,
  `definition.json` SHA-256 `3d4c18bbec032822b1c90e912f7ffadb4cd6f2765439d5fec16d2142a2d49071`;
  загрузчик проверяет manifest и не имеет встроенного fallback.
- При нескольких конфигурациях CTX01 не выбирает конфигурацию автоматически:
  ответы добавляются в M4 при явном выборе участника. Стоп-условий нет; изменение
  схемы аддитивно, API совместим, опубликованные snapshots не переписываются.

## Прослеживаемость

| Правило | Контракт/данные | Реализация | Проверка |
| --- | --- | --- | --- |
| Три смысла не смешиваются | stable key/version/text/raw/normalized | `PARTICIPANT_QUESTION_SCHEMA`, confirmation JSON | unit + PostgreSQL |
| Назначения не смешиваются | organization + `assignment_ref` + revision | W02 state/confirmation, exact late-readiness | integration |
| Ответы входят в M4 | confirmed answer set → UserContext → profile | `acquaintance`, `participant_profile.confirm` | M4/M10 integration |
| M5 получает frozen профиль | AS `execution_payload.profile_snapshot` | существующий M5 storage/runtime | M10 integration |
| Results/Report историчны | M8 `personalized_profile_snapshot` | существующий M8 Results/C-67 | M10 integration |

## План и состояние

- Завершено: разведка, схема вопросов и хранения, M4 binding, точный профиль
  late-readiness, сквозная regression fixture.
- Завершено: локальная адресная проверка и самопроверка diff.
- Завершено: commit, push и отдельный PR #61.
- Активный шаг: исправление выявленных CI-регрессий clean bootstrap и S10-A.
- Следующий шаг: повторный обязательный CI и review; слияние только после зелёного CI.
- Ветка: `codex/ux-ctx01-acquaintance-context`.

## Критерии приёмки

- [x] У каждого ответа сохранены stable key, версия/текст вопроса, raw,
  normalized и источник преобразования.
- [x] Организационные поля, роль и слова участника остаются разными источниками.
- [x] Повтор подтверждения идемпотентен; другая assignment не переиспользует state.
- [x] M5 C-45 и M8 snapshot используют frozen профиль со всеми тремя полями.
- [x] Старые Cycle/Results/Report не меняются после нового подтверждения.
- [x] GET не создаёт UserContext/Profile и не подтверждает ответы.

## Проверка и откат

- Локально: Python compile, `git diff --check`, unit questionnaire, W02 PostgreSQL,
  M4/M10 integration; полный применимый backend набор по матрице.
- Фактически: compile и `git diff --check` — PASS; 47 адресных unit — PASS;
  W02 + M4 + M5 prepare integration — 3 PASS.
- Сквозная существующая S10-A дошла до проверки CTX01 в frozen C-45, затем FAIL
  на известной baseline-границе `M6_AI_IDENTITY_MISMATCH` (`M6_EVIDENCE_FAILED`);
  M8 snapshot дополнительно покрыт существующей неизменяемой передачей полного
  `PersonalizedProfile` и адресными M8 unit. Реальные LLM не запускались.
- Первый CI push выявил две собственные регрессии: создание confirmation-таблицы
  до её M4-зависимостей и устаревшее имя `result_id` в S10-A. Создание перенесено
  после `ensure_assessment_context_schema`, запрос исправлен на `results_id`;
  локально compile и `git diff --check` — PASS. Локальная PostgreSQL для повтора
  недоступна; доказательство полного исправления ожидается в изолированном CI.
- Второй CI подтвердил clean bootstrap и S10-A, но автономный integration-loader
  questionnaire не создаёт M4-зависимости по своему контракту. Confirmation-схема
  выделена в отдельный bootstrap-шаг после M4; самостоятельный loader снова не
  зависит от `assessment_user_context_versions`.
- Третий и четвёртый CI подтвердили unit/HTTP/PostgreSQL integration, включая
  questionnaire, и выявили единый browser stop на финальном шаге знакомства.
  Trace/snapshot доказали не задержку, а корректный `W02_ANSWERS_NOT_BOUND`:
  synthetic stand публиковал устаревшие неканонические вопросы. Fixture переведён
  на `participant_context/corporate/1.0`, ответы связаны с подготовленным runtime
  profile; строгое ожидание смены шага оставлено равным 5 секундам.
- Пятый CI остановился до browser acceptance на собственном `KeyError`: fixture
  принял возвращаемый acquaintance state за confirmation row. Confirmation теперь
  выбирается явно в tenant/user scope перед привязкой synthetic runtime profile.
- Полный локальный backend: 427 PASS / 13 FAIL. Сбои относятся к предсуществующему
  локальному рассогласованию M6 provider artifact/fixture; в CI unit-этап прошёл,
  а внесённые исправления M6 не затрагивают.
- CI обязателен до слияния; реальные LLM не вызываются.
- Откат: revert коммита. Аддитивные колонки и confirmation rows оставить для
  сохранности данных; удаление ответов требует отдельного допуска и не является
  частью отката. Frozen M4/Cycle/M8 snapshots не изменять.

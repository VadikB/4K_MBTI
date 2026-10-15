# UX-P02 — Equivalent Situation Generation

Дата: 15.10.2026. Ветка: `codex/ux-p02-equivalent-generation`.

## Результат и границы

Реализовать технический механизм создания другой согласованной AS того же CaseVersion
и профиля, с устойчивой операцией, независимой проверкой и handoff в P01. Не включать
обычную оценку без опубликованного Case-specific variability/admission contract; не
менять маршрут, таймер, цели или содержательную норму.

## Источники и решения

- `UX-P02_Equivalent_Situation_Generation_2026-10-15.txt`, rev 1.0 — постановка.
- `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, EVC workflow/matrix/artifact recipe.
- Change 01, task manifest 2026-10-01; M1 v1.4 §§5–6; M5 v1.1 и CasePassport v1.1.
- `docs/architecture/m5-case-execution.md` и
  `docs/architecture/m7-route-replacement-contract.md`.
- База: `main@909979043a0aecc6ebfee34e1cf1092121cc8d14`, версия 2.1.33.

Решение владельца из постановки: технический механизм разрешён до готовности
содержательных пакетов; отсутствие GC/content approval не маскируется. Пробел:
опубликованных variability contracts продуктовых Cases нет, поэтому runtime provider
остаётся `None`, а добавленный fixture имеет только `qa` scope.

Стоп-условия: нет. Новый формат является явно заданным расширением существующего
Case-контура; схема аддитивна; миграции/удаления и смены публичного API нет.

## Реализация

- `Api/m5_equivalent_generation.py`: loader, обезличенный input, lease/idempotency,
  provider boundary без DB connection, validation/admission и immutable candidate AS.
- `Api/m7_route_replacement.py`: P01 adapter для уже готовой candidate.
- `Api/routes.py`: owner-scoped HTTP orchestration с транзакциями до/после provider.
- Admission policy загружается сервером из версионированного M5 package; клиент не
  может подменить содержательную норму в запросе.
- M5 variability schema и `qa_only` Case-specific fixture package.
- Unit, HTTP и PostgreSQL integration regression.

## Проверки

- `py_compile` затронутых Python-модулей — PASS.
- Unit + HTTP — PASS, 9.
- Полный e2e — PASS, 54; 10 тестов исключены штатными markers.
- PostgreSQL integration `test_m7_cycle_planner_db.py` — PASS, 13; включает P02→P01,
  replay, single lease и late result.
- `npm run test:backend` — 410 PASS / 13 FAIL: воспроизводятся известные baseline-сбои
  M6 provider contract (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`).
- Полный integration на изолированной `agent4k_pytest` — 76 PASS / 37 FAIL: тот же
  несвязанный M6/provider chain; профильный P02 integration отдельно зелёный.
- CI — ожидает PR.
- Real provider smoke и содержательная приёмка — NOT_RUN: разрешённых credentials и
  опубликованного content contract нет; это не входит в стандартный набор.

## Риски и откат

- Конфиг: production provider выключен; product Cases не активированы.
- Схема: одна аддитивная таблица; существующие snapshot неизменяемы.
- Безопасность: provider input исключает identity/contact и ответы/IA; сохраняется
  только содержательная часть frozen profile и anti-repeat content.
- Откат: отключить endpoint/provider и вернуть код; сохранённые snapshots не удалять.

## Следующий минимальный шаг

Методолог/владелец содержания выпускает новую версию variability contract конкретного
Case и независимое evidence; P03 включает только полностью допущенную конфигурацию.

## Открытые вопросы

Нет для технического механизма. Content admission продуктовых Cases остаётся отдельной
зависимостью и не считается выполненным.

# M6-A — завершение технического задания

Дата: 2026-10-02. Статус: **COMPLETE — technical QA scope**.

Решение владельца: завершить задание без ожидания независимых заключений.
Это изменяет порядок продолжения, но не критерии методологической приёмки:
кандидаты остаются `CANDIDATE`, утверждённых GC — 0, semantic acceptance — `NOT_RUN`.

## Результат

Реализован самостоятельный модуль PM-05 для M6-A:

- принимает сохранённый C-45 из QA-контура M5;
- формирует frozen нормализованный материал и критерии M2;
- выполняет draft QA-механизм через существующий AI gateway;
- валидирует Fragment → BS → Evidence → EB;
- сохраняет immutable request/attempt/analysis/bundle revisions;
- восстанавливается после timeout, retry, истечения lease и process exit до save;
- предоставляет защищённые superadmin HTTP-операции создания и чтения.

IA, C-54, агрегация, M7/M8 Results/Report и основной пользовательский маршрут
не входят в результат. Механизм не включён как default и не допущен для оценки пользователей.

## Источники и прослеживаемость

Применены M6 v1.8 §§1–5/9, M1 v1.4, точные M2 K1/K3 v1.1 и K2/K4 v1.0,
Change 01 И-4/И-6, ADR-002 и [контракт M6-A](../../architecture/m6-a-contracts.md).
Оригиналы, версии и SHA-256 зарегистрированы в SourceSet 2026-10-01.

Цепочка доказательств:

- M6.1.3 / C-45 → `Api/m6_input_resolver.py` → resolver/unit/integration tests;
- M6.2–5 → `Api/m6_contracts.py`, prompt package → span/author/context/M2 tests;
- Change 01 И-6 → repository/worker → replay/lease/timeout/process-exit tests;
- LU-05.6 → restricted HTTP → authorization e2e tests;
- M6.9 → [кандидаты и технические fixtures](../../../tests/fixtures/m6_gc/v1/manifest.json),
  без подмены независимого эталона проектом Codex.

## Проверки

- полный backend: **287 passed**, 82 deselected;
- полный HTTP/e2e: **24 passed**;
- M6 PostgreSQL integration: **20 passed** на изолированной
  `agent4k_m6_pytest`, включая девять цепочек кандидатов;
- M6 unit/package после blind packet: **33 package tests** и адресные M6 tests PASS;
- `py_compile`, manifest SHA-256, локальные Markdown-ссылки и `git diff --check` — PASS.

Изолированный PostgreSQL остановлен. Секреты и реальные пользовательские данные
не использовались. Существующий Starlette/httpx deprecation warning не относится к изменению.

## Непроверенное и ограничения

- независимые заключения назначенных методолога и эксперта: `NOT_RUN` по решению
  владельца не ожидать их в текущем задании;
- утверждённые GC и три реальных прогона каждого: `NOT_RUN`;
- реальный provider/LLM smoke: `NOT_RUN`;
- CI, PR review, merge, deploy, pilot и выпуск: `NOT_RUN`;
- C-54, IA, агрегация, C-46/C-56/C-67 и M7/M8: вне области;
- F01/F02 и задачи общей основы остаются у их владельца.

Отсутствие экспертных заключений не мешает статусу завершённой технической задачи,
но блокирует утверждение GC, semantic acceptance и применение к пользователям.

## Риски и откат

Схема расширена только новыми M6-таблицами. Legacy API и данные не мигрируются.
Для отката прекратить новые QA requests и worker, дождаться или завершить активные
attempts, сохранить immutable историю и совместимый reader. Таблицы не удалять
автоматически; fallback к старому evaluator не включать.

## Состояние передачи

Ветка: `codex/m6-task01-contracts`. Исходная база:
`dd3d2cadd90a31e3b7b3141ed6a0984afbd11ef6`.
Полные детали: [реализация](m6-a-implementation.md),
[пакет задачи 2](m6-task02/README.md),
[техническая проверка](m6-task03-technical-verification.md).

Открытых вопросов, блокирующих **эту техническую область**, нет.
Будущее возобновление методологической приёмки начинается с двух независимых
заключений по слепому пакету; повторное общее исследование M6-A не требуется.

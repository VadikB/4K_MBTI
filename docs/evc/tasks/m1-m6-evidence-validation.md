# M1/M6 — проверка основания оценки перед записью

20.11.2026. Ветка `codex/m1-m6-evidence-validation` от `e4bc5c88c45b775a6406f034750e75aa1e4c47be`. Кандидат TEST `2.1.41`.

## Результат

В PM-05 итоговые L1–L3 требуют фактической возможности и Evidence своего индикатора. Ссылка на Bundle другого индикатора отклоняется до записи ревизии и C-54. Simple Evidence требует одно наблюдаемое проявление. Правила применяются к `m6_indicator_assessment/1.0.1` и `m6_evidence/1.0.1`. L0 с проверяемой границей Dialogue и `INSUFFICIENT_EVIDENCE` проходят существующий контракт. Чтение истории и QA 1.0.0 используют прежние validators.

## Источники и область

- [M1 v1.4 §7–8](../../architecture/product-4k/m1/v1.4/source.md), FROZEN / CURRENT=NO. SHA-256 `282e69b87585c28b52327e657d71a620c15842f7ade134467788252829833299`.
- [M6 v1.8 §3.1, §6.2–6.3](../../methodology/source-sets/2026-10-01/derived/M6-v1.8.md), FROZEN, текст из [task SourceSet](../../methodology/source-sets/2026-10-01/manifest.json). SHA-256 `f081bc9ca795257b6a4afbebbd4b56f32243a1a75f5c25d91a77c64d64fc86fa`.
- [Change 01](../../architecture/product-4k/1.0/updates/2026-10-01/source.md) И-4/И-6, [ADR-002](../../adr/002-cycle-as-dialogue-contracts.md) и [T08](../change01-traceability.md). C-45 передаёт материал в PM-05, C-54 возвращает результат в PM-04. SHA-256 текста поправки `ee03f59d78e441f69964352bcd94a1e7c375c2ce306433a8d0cd056ba3af93d2`.
- [Registry](../../architecture/product-4k/registry.md) и [реестр решений](../decision-register.md). Для отдельной тестовой БД применяется `SYN-CONTOUR-OWNERSHIP`. Условия релиза определяют `CONTRIBUTING-MERGE-AUTH-01` и `CONTRIBUTING.md`.
- `Api/m6_evidence_service_v2.py` проверяет тип Simple при валидации ответа. `Api/m6_assessment_contracts.py`, `Api/m6_assessment_service_v2.py` и `Api/m6_assessment_repository.py` проверяют основание по сохранённому входу до записи. Регрессии поставляются в `tests/unit/test_m6_evidence.py` и `tests/unit/test_m6_indicator_assessment.py`.

Реализация совпадает с шестью файлами патча из пакета `P4K_M1_M6_TEST_Release_2026-11-20.zip` по `git patch-id --stable`. Дополнительно подготовлены файлы релиза приложения и эта карточка. Схема БД, публичный API и опубликованные предметные артефакты сохраняются. Содержательная приёмка реальных LLM и продвижение за TEST вне области. Новых предметных норм, миграций, смены владельца данных или внешней передачи данных задача не требует.

## Проверки

- `git apply --check`, `git diff --check` и `npm run ready:prepare -- --candidate 2.1.41` прошли.
- Адресный unit-набор M6 — 41 PASS. `npm run test:backend` — 1 305 PASS. Первый запуск ограничивал `ps` для девяти тестов управления дочерними процессами. Полный повтор с разрешённым доступом прошёл.
- `npm run test:backend:http` — 218 PASS, включая 11 адресных проверок M6 и восстановления M10.
- Интеграция на собственном PostgreSQL 16 — 474 PASS суммарно. `npm run test:backend:integration` дал 449 PASS и 25 ошибок настройки EXEC-FIX02 из-за ожидаемого имени БД. Все 25 прошли адресным повтором с именем `agent4k_pytest`. Две проверки с реальным LLM пропущены по условиям задачи.
- `npm run lint:js` прошёл. `node --test tests/frontend/*.test.mjs` — 476 PASS.
- `npm audit --audit-level=high` прошёл. В дереве dev-зависимостей ESLint есть предупреждения moderate, зависимости в этом выпуске не менялись.
- Два browser-сценария S10-A прошли на синтетических данных, включая оценку с уточнением, отчёт и PDF.
- Отдельная проверка на PostgreSQL 16 подтвердила отсутствие записей IA и C-54 при чужом Bundle, а также сохранение и чтение L0 и `INSUFFICIENT_EVIDENCE` через продуктовый механизм 1.0.1.

## Выпуск и откат

Граница выпуска — один PR в `main`, проверки `frontend`, `pytest` и `full-verification` для его HEAD, review и squash merge. GitHub Actions развёртывает merge SHA только на TEST. Контроль после деплоя включает `/users/version` и `/health/ready`.

20.11.2026 владелец ответил в чате «Да, разрешаю выпуск на TEST» на запрос о push этой ветки в `VadikB/4K_MBTI`, создании PR и squash merge после обязательных проверок и ревью со штатным деплоем на TEST. Допуск охватывает `branch_push=true`, `pr=true`, `version_bump=true` и условные `merge=true`, `deploy=true` после прохождения проверок и ревью. `START.md` определяет состав работы. Предметная публикация вне объёма задачи (`artifact_publish=false`). Откат через отдельный revert PR по штатному пути выпуска с сохранением исторических ревизий.

# ADM-STATUS-01 / 1.1 — отчёт рабочего цикла

## Основание и границы

- База: `origin/main` / `95d708a683c5db59ef002893ff2bf1159bba22af`, ветка `codex/adm-status-01`.
- Проверенный commit реализации до документальной фиксации SHA: `388ecde2008450c30c0be125a104e354c8618cba`; окончательный PR head включает только следующую правку этого отчёта.
- Пакет: `P4K_ADM_STATUS_01_2026-10-31_v1.zip`, SHA-256 `debf4a82ca88e8627a52f79f756b41bc26d6d3c5bee0c30225015dc7453985be`.
- Управляющий вход пакета: `START_ARCHITECT.txt`, SHA-256 `6fe1e8799d515b5ac0d36cf44851174e01ec3bb737e32ccf07caca88198d5eb3`.
- Постановка: `TASK.txt` `103ee1fb85deb7c711082ad3fed805ee232ddcf875fac41fe7ae2b918c951340`; критерии `ACCEPTANCE.txt` `80c5cde86d43e3f416d216c059fc1741bce1e551fc736b4bf0a17573a4948a6e`; матрица `STATUS_MATRIX.csv` `8b916df8ead8f1fb4d8767fd10ad7f6167fd163e28db384c73cf1100b4ad7c4a`.
- P06: принятая постановка `P06-ADD01`, SHA-256 `bdbe4752f9f94779cc44b8ff04ee6bef156efa743f1e11bc44322af4147f052a`.
- Прочитаны: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`, архитектурный context/registry, Change 01 (`ac082b…`), manifest (`f95a39…`), ADR-002 (`4a4e01…`) и traceability (`e528ba…`). CURRENT методологии не присваивался.

Результат ограничен списком участников выбранной оценки и ранее принятой отменой конкретного неначатого назначения P06. Новых предметных состояний, прав, массовой отмены, старта/продолжения Cycle администратором и доступа к содержимому отчёта не добавлено.

## Решение и трассировка

| Источник / правило | Контракт и данные | Реализация | Проверка |
|---|---|---|---|
| ADM-STATUS-01: один видимый основной этап | `assessment_stages[assignment_ref]` из серверной проекции | `Api/routes.py`, `web/js/screens/admin/organizations.js` | frontend + browser |
| Контекст не угадывается | выбранный `assignment_ref`, серверный `assessment_program` | блок `.admin-people-context` | browser screenshot |
| Одно основное действие, прочее в `⋯` | права и факты строки; без admin start/resume | participant row/menu | frontend + browser |
| Выбор не переносится между оценками | ключ `organization_id + assignment_ref` | management draft selection | frontend + browser same-scope reload |
| P06: отмена точного поколения до старта | `assignment_id`, advisory lock, `FOR UPDATE`, audit, idempotency | `Api/assessment_assignment_cancellation.py`, runtime guards, HTTP endpoint | HTTP 16 PASS; isolated DB 16 PASS |
| Новое назначение после отмены — новое поколение | partial unique active index; immutable source binding clone | `Api/database.py`, `Api/assessment_assignment_sources.py` | isolated DB |

## Изменённые контуры

- Backend/API: точная идентичность назначения в проекции и M5 Cycle, атомарная отмена, аудит, защита старых вкладок и повторное назначение.
- Frontend: компактная desktop/mobile строка, видимый этап и пояснение, карточка участника, `⋯`, одна групповая панель, раздельные подтверждения отзыва приглашения и отмены назначения.
- Тесты и доказательства: HTTP, DB race/idempotency, frontend contracts, Playwright и два синтетических снимка.

## Проверки

- `python -m py_compile …` — PASS.
- `pytest tests/e2e/test_adm27_assignment_http.py -q` — PASS, 16.
- `pytest tests/unit tests/e2e/test_adm27_assignment_http.py -q` — PASS, 679; одно внешнее deprecation warning.
- isolated `TEST_DATABASE_URL=…/f22_integration_pytest pytest tests/integration/test_adm_layout_31_cancellation_db.py -m integration --run-integration -q` — PASS, 16.
- `node --test tests/frontend/*.test.mjs` — PASS, 122.
- `npm run build:web` — PASS.
- `playwright … --grep ADM-STATUS-01` — PASS, 2; 1440 и 390 px, без горизонтального overflow.
- `STAND_ADMIN_URL=…/postgres npm run test:browser` — PASS, 90; полный isolated browser acceptance, включая ADM28 real и ширины 320/375/390/683/768/1024/1366/1440.
- `git diff --check` — PASS.
- Полный integration suite локально, реальные LLM, deploy и приёмка окружения — NOT_RUN; локальный минимум изменения покрыт, обязательный полный CI остаётся gate перед merge.

Детальный статус критериев: [adm-status-01-acceptance.csv](adm-status-01-acceptance.csv). Визуальные доказательства: [desktop](../evidence/adm-status-01/desktop-status-list.png) и [mobile](../evidence/adm-status-01/mobile-status-list.png).

## Пробелы и следующий шаг

- Разрешённый/запрещённый просмотр содержимого отчёта, все почтовые гонки и полный набор комбинаций `STATUS_MATRIX.csv` требуют отдельного интеграционного контура; UI не расширяет эти права.
- Тексты пояснения ограничены серверным `description` либо нейтральным сообщением без вывода нового предметного состояния.
- До merge нужны version bump по действующему release gate, полный CI и review.

## Откат

Код откатывается единым revert будущего commit. Схема добавочна, но partial unique index допускает историю поколений: возврат прежнего полного unique constraint возможен только после проверки отсутствия нескольких поколений на один ключ. Аудит и отменённые назначения не удалять; при откате UI/API оставить данные неизменными и отключить маршрут через revert приложения.

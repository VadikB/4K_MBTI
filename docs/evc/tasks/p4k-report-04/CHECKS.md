# Проверки P4K-REPORT-04

Текущая база `99d225119108526912c44a6b8a6e6012cc289b04`; точный SHA кандидата будет записан после коммита. Синтетические fixtures, один worker, retries=0, без LLM/почты. PostgreSQL 15 на `127.0.0.1:55434`, отдельные `p4k_report04_pytest` для адресных сценариев и `agent4k_pytest` для полного набора; maintenance `postgres` того же собственного кластера. Результаты до переноса обозначены отдельно.

| Критерий | Статус | Доказательство и предел |
| --- | --- | --- |
| AC01 эталон 1440/390, 320 и 200% | PASS локально | Playwright 3 PASS; снимки `evidence/report04-{1440,390}.png` и `evidence/report04-evidence-{1440,390}.png`. Устранены дублирующая панель claims, техническая шапка, карточки/отступы и переполнение 320 px. Детальный радар — REPORT-05, сравнительная секция — REPORT-07. |
| AC02 два исторических Cycles | PASS адресно | DB integration 4 PASS: две сохранённые программы и смена live configuration; полный product path сохраняет снимок до/после изменения названия. Frozen PersonalizedProfile проверен existing path. |
| AC03 основания, четыре исхода, публичный JSON | PARTIAL | Unit/HTTP 13 PASS; browser 3 PASS; служебные поля исключены из DOM, но сохранены в JSON ради действующего API. Их удаление воспроизводимо ломало HTTP/bootstrap, затем поля восстановлены и проверки прошли. Для новой публичной проекции нужен согласованный контракт. Семантический validator REPORT-03 сохранён. Качество живой LLM не проверялось. |
| AC04 immutable read и race | PASS адресно | Browser: два `report_id`, поздний ответ не заменяет новый; повторное открытие не делает POST M6/LLM. GET читает сохранённый C-67. |
| AC05 пробелы/ошибка основания | PASS адресно | Browser: нейтральная подпись при отсутствии снимка, сохранённые факты при failed descriptive; нет live UserContext lookup при чтении Report. |
| JS/frontend/build | PASS на `99d22511` | `npm run lint:js`; `node --test tests/frontend/*.test.mjs` — 354 PASS; `npm run build:web`. |
| Backend | PASS на `99d22511` | `PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -q -m 'not integration and not e2e and not llm' --tb=short` — 1126 PASS. Первый sandbox запуск до переноса: 9 FAIL из-за запрета `ps`; с системным доступом PASS. |
| Integration | PASS на `99d22511` | `STAND_ADMIN_URL=…/postgres TEST_DATABASE_URL=…/agent4k_pytest PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -q --run-integration -m integration --tb=short --maxfail=1` — 421 PASS, 2 SKIPPED (явный real-provider acceptance), exit 0, PostgreSQL 15. Ранние прогоны локализовали неполные synthetic fixtures M7/M8/истории; после их исправления заключительный прогон прошёл целиком. CI использует PostgreSQL 16 и остаётся отдельной проверкой. |
| HTTP e2e | PASS на `99d22511` | `PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -q -m e2e tests/e2e --tb=short` — 177 PASS. |
| `git diff --check` | PASS до финальной записи | Повторить после фиксации документов/сборки. |
| Ready/CI/production | NOT_RUN | Первый `ready:prepare` обновил remote до `99d22511` и вернул stale-base (exit 1). После fast-forward повторный preflight установил `2.1.16 → 2.1.17` и вернул exit 2: нужен утверждённый `--candidate`. Версия не изменена. Обязательные `frontend`, `pytest`, `full-verification` и review нужны на точном head PR; локальный PASS их не заменяет. |

Изолированная БД и browser preview не содержат реальных персональных данных. Фактический live LLM и содержательная оценка текста вне этой controlled-проверки.

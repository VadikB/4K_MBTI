# SLS07 — сквозной Cycle и gate первого Sales-пилота

Дата: 2026-10-21

Ветка: `codex/sls07-cycle-acceptance`

База: `61df52f398b1ca7ae4d162995e615e8c299f6070` (`main`, SLS06)

## Результат и границы

Задача фиксирует воспроизводимый технический gate для первого Sales-пилота и не
подменяет им содержательный допуск. В область входят девять Case/AS пакета
`sales-pilot/0.1`, общий бюджет Cycle 7200 секунд, R1 с продолжением той же AS,
четыре исхода Results, описательный Report и права получателей. В область не входят
присвоение `ADMITTED`, запуск людей, pilot/production, изменение опубликованных
snapshot и ручная вставка заранее правильных Evidence/IA/Score.

Текущий итог: **техническая synthetic-приёмка доступна; запуск людей BLOCKED** до
человеческого methodology review/admission. Real provider и authenticated visual
smoke в текущей среде `NOT_RUN`.

## Источники и решения

- `P4K_Sales_Pilot_Architect_Pack_2026-10-19.zip`, редакция 2.1:
  `RUN_CODEX.txt`, `P4K_Sales_00_Start.txt`, `P4K_Sales_07_Cycle.txt`,
  `P4K_Sales_Main_Recheck_2026-10-19.txt`,
  `references/P4K_Product_Development_Principles.txt`, `sources/manifest.json`.
- Контрольный `package-manifest.json`: 34 файла; manifest источников SHA-256
  `f81376c9ab62cd27b4f2efaea5a513886c232cf0fd42f1c9d2367ac7146ec8ce`.
- Репозиторий: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
  `docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
  `docs/architecture/product-4k/1.0/context.md`,
  `docs/architecture/product-4k/registry.md`,
  `docs/adr/002-cycle-as-dialogue-contracts.md`.
- Уже принятые решения владельца: девять Sales Case/AS; 7200 секунд на Cycle;
  календарное окно отдельно; R1 продолжает ту же AS; Report описательный;
  synthetic, real-provider и human admission учитываются раздельно.

Пробелы: provider-конфигурация и отдельный лимит стоимости не предоставлены;
человеческие заключения SLS06 отсутствуют. Это не блокирует synthetic regression,
но блокирует содержательный допуск людей.

## Трассировка gate

| Требование SLS07 | Доказательство | Статус |
| --- | --- | --- |
| Девять Case/AS и отличающиеся ветви | `test_m5_sales_package.py`, `test_m5_sales_package_db.py` | PASS/CI |
| Штатный Cycle/AS, frozen snapshots | `test_m5_cycle_runtime_db.py`, `test_m7_cycle_planner_db.py` | PASS/CI |
| 7200 секунд и отдельное календарное окно | `test_m7_parameter_resolution_db.py`, SLS04 tests | PASS/CI |
| R1: та же AS, короткий/длинный возврат | `test_m7_return_integration.py`, `test_m7_cycle_planner_db.py` | PASS/CI |
| Dialogue → Evidence → IA → Results → Report/PDF | `test_integrated_acceptance_db.py`, runtime browser G10.7 | PASS/CI |
| Полный/частичный/qualitative/no-result и ноль | `test_integrated_acceptance_db.py`, M8 comparison tests | PASS/CI |
| Права получателей | `test_m8_report_access_http.py` | PASS/CI |
| Реальный provider | нет разрешённой конфигурации/лимита | NOT_RUN |
| Authenticated визуальный UI smoke | нет тестовых credentials в задаче | NOT_RUN |
| Human methodology review/admission | пакет SLS06 подготовлен, заключения отсутствуют | BLOCKED |

`PASS/CI` означает, что адресное локальное доказательство дополнено обязательным
GitHub CI точного head перед merge. Оно не означает semantic GC или Reliability.

## Проверки

- `python -m pytest -q tests/unit/test_m5_sales_package.py tests/unit/test_m7_return_integration.py tests/unit/test_m8_report_comparison.py tests/unit/test_sls06_review_package.py`
  → 31 PASS.
- `python -m pytest -q tests/unit` → 470 PASS; предупреждение только о невозможности
  записать `.pytest_cache` в managed worktree, тестовые результаты не затронуты.
- Полная сверка bytes/SHA-256 всех записей `package-manifest.json` → 34 PASS.
- `TEST_DATABASE_URL` → `UNSET`; локальная PostgreSQL integration `NOT_RUN`,
  обязательна в CI на изолированной БД с `test`/`pytest` в имени.
- `DEEPSEEK_API_KEYS` / `DEEPSEEK_API_KEY` → `UNSET`; real provider `NOT_RUN`.
- `git diff --check` и проверка ссылок/JSON выполняются перед PR.

## Решение о запуске и остаточные риски

- Технические synthetic fixtures можно продолжать использовать для регрессии.
- Назначения людям и заявление о готовности ограниченного Sales-пилота:
  **BLOCKED** до human methodology review/admission и разрешённого real-provider
  smoke либо явного решения владельца о его статусе.
- Нельзя склеивать разные Cycle, обещать прохождение всего каталога за 120 минут,
  выдавать import/HTTP 200 за оценочную готовность или считать synthetic GC
  независимым экспертным заключением.

## Риски и откат

Конфиг, схема БД, runtime, публичный API, snapshots и права не меняются. Откат
этого результата — revert документа и evidence; исторические Cycles и данные не
затрагиваются. При отзыве пилота новые назначения должны быть остановлены штатным
операционным решением владельца, без массовой очистки БД.

## Стоп-условия EVC

- Предметный смысл/контракт/схема/миграция не меняются — нет.
- Отсутствует обязательный содержательный admission — да, блокирует только запуск
  людей и присвоение `ADMITTED`, не synthetic regression.
- Real-provider требует внешней конфигурации и лимита — `NOT_RUN`, не заменяется mock.
- Pilot/production и внешние адресаты вне поручения — не затрагиваются.

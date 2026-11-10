## Результат

Добавлен отдельный profile `assessment-execution-contour/1`: standalone AC18 остаётся
совместимым, а composite продолжает его owned DB/Cycle/initial AS штатным UI-путём
до готового и явно открытого Report.

## Изменения

- reusable browser completion driver без владения stand;
- `--profile ac18-to-report` в существующем runner;
- versioned terminal receipt и fail-closed offline validation;
- controlled browser regression и негативные validator tests;
- EVC задача, STATE, H1–H12 и prepared paid command/cost boundary.

## Проверки

- `git diff --check` — PASS.
- completion validator — 8 PASS.
- runner/provider/preparation regressions — 76 Python + 65 Node PASS.
- controlled browser profile — PASS (2 AS, один Cycle, Report открыт).
- standalone PATH29 free regression — PASS.
- EXEC-FIX-01/02/03 integration — 40 PASS + 10/10 PASS после корректного
  allowlisted maintenance DB retry.
- real provider — NOT_RUN: требуется отдельный прямой допуск.

## Риски и откат

Controlled PASS не подтверждает семантическое качество. Provider usage может быть
неполным при malformed retry. Откат — удалить новый profile/receipt/validator;
продуктовая схема и опубликованные артефакты не менялись.

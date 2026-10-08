# Task-10-15.2 — итог технической приёмки M4–M8

## Итог

`TECHNICAL_ACCEPTANCE_PASS` в проверенной технической области M4–M8.
Проверенный runtime SHA: `01aee3b19e7d3e385a64fc764222b863553219b0`.
Test-only correction: `52c778c`.

QA orchestration 10.15.1 сохранён. QA catalog/evidence/Cycle остаются `qa`,
обычный `assessment` не принимает QA fixtures. Admission, ownership, organization
и origin guards не ослаблялись. Реальный AI, `PRODUCT_READY`, `SEMANTIC_PASS`, GC
и Reliability не заявляются.

## Закрытые FAIL

1. M5 technical-C54: устарела fixture, а не runtime. Действующий provider contract
   добавляет `thinking` и `response_format`; fixture теперь фиксирует фактически
   переданные kwargs. Identity check и содержательные assertions сохранены.
2. Legacy profile: ordinary seed без внутреннего QA-флага снова независимо проходит;
   адресный прогон двух прежних FAIL — `2 passed in 44.20s`.

Первые ошибки сохранены в `verification-log.json`: неверная maintenance DB 10.15,
sandbox TCP denial, pre-fix `92/2`, а также запрещённый прямой startup migration,
который не обновляет bootstrap fingerprint.

## H8

- новая БД: штатный owned clean bootstrap, owner Report/PDF — PASS;
- обновление: БД и исторические данные созданы точным pre-10.11 commit
  `15f41a229c6cc2b33e8a0b99306433ebb3df8b5d`, затем обновлены штатным current
  `scripts/test_stand.py bootstrap` — PASS;
- исторический Cycle `bbe3b14b-8128-4fe5-aff0-d19b61a5b1ab`, Results
  `bb832a81-c374-4233-813d-442988264262` и Report
  `4031a4a0-c82b-4427-aaaa-e56613116887` сохранили связи;
- owner history/Report/PDF после обновления: HTTP `200/200/200`, PDF `%PDF`;
- `catalog_ref_json` исторического terminal Cycle остался `NULL`: обратной привязки
  к текущему каталогу нет. Terminal calculated Cycle доступен только для чтения;
  новый запуск подчиняется текущему catalog contract.

## Итоговые проверки

- full integration: exit 0, `94 passed, 430 deselected`, 688.50 s;
- backend: exit 0, `380 passed, 144 deselected`, 11.04 s;
- HTTP: exit 0, `46 passed`, 22.71 s;
- C1/C2 ×3: ранее сохранённый exact-runtime прогон `6 passed (8.8m)`, retries=0,
  polling 120 s, timeout 240 s. Повтор не нужен: после него менялись только
  integration fixture и документы, runtime/seed/orchestration/timers/frontend — нет;
- frontend lint/build: не повторялись, frontend не изменён.

## Безопасность и откат

Общая SQL и пользовательские данные не менялись; legacy не очищался. H8 использовал
только owned disposable DB и штатный ownership guard. Откат 10.15.2 — удалить
test-only commit `52c778c` и report/evidence commits; runtime `01aee3b` остаётся.

Архив H8: `artifacts/task10-15-2/task10-15-2-h8-logs-safe.zip`, SHA-256
`f2766807b920e35bb523f638a184545185ea2d64db1748754ddaec092d1095ce`.

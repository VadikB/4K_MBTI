# Task-10-15.1 — техническая приёмка M4–M8

## Результат

В exact candidate `01aee3b19e7d3e385a64fc764222b863553219b0` добавлен server-owned
QA orchestration mode. Он включается только совместным набором признаков isolated
stand, browser test gateway, acceptance scenario, ownership marker, disposable DB
и внутреннего state-флага. Клиентского параметра нет. QA catalog/evidence/Cycle
сохраняют `usage_scope=qa`; Results, C-67 и PDF имеют явную отметку тестового
результата. Обычный `assessment` по-прежнему не принимает QA fixture.

Полный API-путь QA прошёл M4, Cycle/AS, Dialogue, C-45, Evidence, IA, admission,
calculation, Results, C-67 и PDF. C1/C2 выполнены по три раза: `retries=0`, polling
120 s, timeout 240 s; итог `6 passed (8.8m)`. Все шесть стендов удалены guarded
teardown после сохранения evidence.

Статус: `TECHNICAL_ACCEPTANCE_PASS_QA_ORCHESTRATION_SCOPE`. Это не
`PRODUCT_READY`, не `SEMANTIC_PASS`, не GC и не Reliability.

## Проверки

- backend exact SHA: `380 passed, 144 deselected`, exit 0;
- HTTP exact SHA: `46 passed`, exit 0;
- clean bootstrap + owner Report/PDF: `1 passed in 102.09s`, exit 0;
- C1/C2 ×3 exact SHA: `6 passed (8.8m)`, exit 0;
- полный integration: `92 passed, 2 failed`, exit 1. Один FAIL — прежний M5
  technical-C54 fixture с устаревшим `sent.parameters`; второй был legacy profile
  test до разделения ordinary/QA seed и устранён этим разделением. Полный набор
  после последней коррекции не повторён, поэтому H8 остаётся `PARTIAL`, а не PASS.

Первоначальный FAIL 10.15 сохранён: maintenance DB `agent4k_pytest_1015` была
отвергнута ownership allowlist. Текущая sandbox-попытка также сначала получила
`Operation not permitted`; успешные DB-прогоны выполнены затем на localhost PostgreSQL
16 через разрешённую maintenance DB `agent4k_pytest`, без расширения allowlist.

## Границы и откат

Реальный AI, общая SQL, test publication, push/merge/deploy, GC и содержательная
приёмка не выполнялись. Откат runtime — commit `01aee3b`; evidence/report commit
удаляется отдельно. Admission guard, права участника и human-origin policy не менялись.

Безопасный архив: `artifacts/task10-15-1/task10-15-1-traces-safe.zip`, SHA-256
`87bd5221f8e8bcb270d97032ce80d0644e783d1f890409cd6e3daccdb726371d`.

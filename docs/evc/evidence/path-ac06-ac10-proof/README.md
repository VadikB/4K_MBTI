# Первичные доказательства AC06/07/09/10

[Индекс](evidence-index.json) выбирает **окончательные** runs на source commit
`2a868e5f909b0493e1e3b936e5407b07c73e811a`. `CHECK.py` проверяет фактические receipts,
SQL no-write hashes, concurrency/late fault marker, browser/viewport artifacts,
JUnit и owned cleanup без подключения к БД или provider:

```sh
python3 docs/evc/evidence/path-ac06-ac10-proof/CHECK.py
```

Каталоги baseline/run-02/run-03/final-http-pg — сохранённые предыдущие попытки,
не подмена final receipt. В baseline3 FAIL относятся к новым fixtures (обязательное
role_description/API projection/полная confirmation schema), не к продукту.
Остальные browser UUID с неполным events/viewport receipt — ранние попытки нового
test/collector; итоговые пути перечислены только в индексе. Негативная viewport
попытка отдельно component-negative-viewport, без утверждения product root cause.
Raw negative pytest/Playwright context logs сохранены побайтово в `baseline/*.gz`:
`gzip -cd <file.gz>` восстанавливает исходник. Их trailing whitespace не исправляли
в доказательствах; первоначальный pre-commit diff-check отказ зафиксирован, вместо
обхода hook использована обратимая упаковка raw bytes. Положительные JSON/JUnit
и их смысл не менялись.

`verified-sha-http-pg/checks.json`:31 event,25 запрещённых HTTP commands с совпавшими
count+hash20+ domain tables; положительные revision/repeat и реальный PG sequence
показывают late rollback. `pytest.txt` —18 PASS, `cleanup.json` — marker/name-guarded
DROP, сохранение checks произошло до удаления. Full integration.xml —240 PASS,
wrapper child не прибавлять как240+18 независимых outer tests.

`browser-results.json`:2 PASS, retries0/skips0/flaky0. Admin browser: actual main.app
через uvicorn/Chromium/PostgreSQL;1 POST при dblclick, real route.fetch/commit200 и
abort только доставки, затем reload/retry/readback. Fake server success нет.
Числовые refs/counts в events, cookies/tokens в evidence не сохраняются.

`component-final`: **SYNTHETIC plan upstream substitution** для старого static
component; AS checks/time/assignment/SQL реальные, provider disabled. Это проверка
нового read-only viewport collector, не допуск target pilot или real-provider AC18.
Тот же first-AS экран на4 widths без новой AS; после viewport и повторного
assignment counts1/1/1/1. Затем старый component-test штатно отправляет один
synthetic ответ; это не ветка full PATH, которая завершается при0 answers.

Original QA в E10.2 seed — техническая **синтетическая подстановка**. Не считать
origin=human_review с controlled-test actor реальным review. Full published-pilot
использует отдельно byte-pinned1.2 receipt/27 original QA без такой подстановки.

Архив сдачи содержит selected source files, diff от main, incremental Git bundle,
точный handoff SHA/code hashes и checksum manifest/VERIFY. Для восстановления
bundle нужен base3f42bba; первичный offline CHECK самостоятельный и base не требует.
Ни state.json, ни auth trace/passwords/.env в пакет не входят.
Новый CI/push/merge/deploy/публикация/LLM не выполнялись. PREP-DIAG-01 UNKNOWN отдельно.

# AC18-FIX-02 — один real-provider PATH на итоговом SHA

Статус: **опубликован в draft PR #192; быстрый CI запущен, полный CI не выполнялся**. Основание —
`P4K_AC18_FIX_02_Preparation_Start_2026-11-07.zip`, редакция 1.0, и
[план проверки](ac18-fix-02-provider-verification-plan.md). Владелец в текущем
чате 08.11.2026 разрешил **один** платный прогон полной схемы без лимита затрат.
Это разрешение использовано; повторный paid run не входит в результат.

## Результат и границы

**PASS**: один синтетический путь «суперадмин → опубликованная программа →
администратор и участник → реальная подготовка M5 → допуск → явный start →
первая AS» на `main@5eb1250a2341a54b125cf451c13bd5bd9ae32a00`, версии
`2.0.82`. Оценочных ответов — **0**. Проверена работа реального провайдера на
этом SHA для одного положительного сценария; это не содержательная приёмка
методологии, не вся оценка до отчёта и не объяснение исторической операции
`64344f28-e9de-4bcc-9173-27376a33ea0b` или PREP-DIAG-01.

Программа — опубликованная `specialist_pilot@1.2`, id `2`, exact source receipt
SHA-256 `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
Provider contract `deepseek_product_gateway@1.0.0`, checksum
`a9b20456f413a8828ee2cca47356490ae98844542c8ad31c015f937abe951c8c`,
модель `deepseek-flash`; устаревшее значение модели из env игнорировалось.
Продуктовый код, published definitions, prompts, admission/repair policy,
схема и рабочая БД не менялись.

## Источники и решения

Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow/verification
matrix/artifact recipe/task template/review checklist; Product Architecture 1.0,
Registry и маршрут Change 01; пакетные `START_CODEX.txt`, `TASK.txt`,
`SOURCES.md`, `VISUAL_ACCEPTANCE.txt`; план выше, профиль
`assessment-first-case/1.1`, runner `scripts/assessment_first_case.py`, защита
`scripts/test_stand.py` и `playwright.config.mjs`. Применены опубликованный
source receipt 1.2 и существующий `m7_start_readiness/1`; M1 v1.4 остаётся
FROZEN/CURRENT=NO. Новую предметную норму этот прогон не задаёт.

Восемь стоп-условий EVC для исполнения существующего runner не открыты:
смысл/API/схема/данные/источники/контур/права/откат не изменены. Отдельный
платный допуск был дан владельцем; отсутствие денежного лимита — его явное
решение. Провайдерский ответ не является гарантией будущих ответов.

## Проверки и первичные evidence

Execution host: `/home/vadim_bogachev/projects/Agent4K-Test`, tracked checkout и
`origin/main` — один SHA `5eb1250a`; версия `2.0.82`. Исходный receipt побайтово
проверен до чтения env и открытия БД. `--preflight-only` → **READY**:
PostgreSQL connect/CREATEDB, Chromium, порт, provider contract и credentials.
`--check-bootstrap` → **PASS_BOOTSTRAP_ONLY**, без LLM; собственная БД удалена
после marker/ownership-проверки. Один основной вызов
`scripts/assessment_first_case.py` с `--program-source published-pilot` и
полным explicit selector, Playwright `workers=1/retries=0` → **PASS**, один
browser test за 4,1 минуты. После него `--summarize-only` → **PASS**, ошибок
валидации нет. Это повторная offline-проверка сохранённого evidence, не новый
вызов провайдера.

Execution checkout не был полностью пуст по `git status`: runner сохранил в
`code-identity.json` имена существующих untracked env-backup и старых
content-addressed `web/dist` assets. Tracked diff отсутствовал; эти файлы не
менялись и не включаются в evidence/PR. Это ограничение точности среды, а не
доказательство изменения исполняемого кода.

| Факт | Итог одного paid run |
| --- | --- |
| Run / preparation | `e2ad46ce8f0f4663996224981dbf2faa`; операция `completed`, `error_code=null` |
| Конечная генерация | `admission_status=PASS`, `admitted_for_participant=true`, 5 tester batches и 4 challenger batches; blocking/incomplete checks пусты |
| Repair | Не потребовался в этом сценарии; отказные и repair-ветви этим paid run не проверены |
| До явного старта | `can_start=true`, reasons `[]`, Cycle `prepared`, `started_at=null` |
| Start/readback | HTTP `201`, тот же Cycle/AS, Cycle `active`, DOM introduction совпала с предъявленной AS |
| Ответы | `assessment_answers=0`; один profile, Cycle, start и preparation operation |
| Provider | 10 уникальных завершённых запросов; каждый завершён с первой transport-попытки, JSON parse failures `0`. Retained usage: prompt `712763`, completion `39810`, total `752573` tokens; внешний биллинг отдельно не сверялся |
| Cleanup | `owner_verified=true`, собственные DB/state отсутствуют, `force=false`; обе run-записи offline PASS |

Safe allowlisted сводка и хеши первичных файлов — в
[`summary.json`](../evidence/ac18-fix02-real-provider-5eb1250a/summary.json).
Полный первичный evidence остаётся на execution host в
`/home/vadim_bogachev/evidence/ac18-fix02-final-5eb1250a-20261108/`, paid run
directory `c7363f9b-2952-4b56-b7a1-38d430c4d1f8`. Его нельзя целиком переносить
в Git: среди runtime-файлов есть private state/log и потенциально чувствительные
материалы. `first-case-receipt.json` SHA-256 `72017dd2d70613a84b3f9bdff21c7883f237adace167a38cf7c307772b391929`,
`source-to-runtime-receipt.json` SHA-256 `4daec6e85b20c9a50fdc8c22c8de540dc8019d73c1df33c3bb482c2772850b66`;
оба были сохранены до cleanup и повторно проверены offline.

## Непроверенное, риски и передача

Новый платный run не воспроизводил исторический неполный `common.confidentiality`,
ошибки сети, потерю start-ответа или repair; для них остаются адресные
синтетические unit/HTTP/PG/browser-регрессии PR #182–191. Физический телефон,
Safari/Firefox и сессия реального участника на `test` — **NOT_RUN**. Визуальный
комплект PR #183 принят владельцем отдельно; этот прогон не расширяет его статус.

`main@5eb1250a` уже развёрнут на `test`: deploy-test #873 PASS, публичные
frontend и `/users/version` показывают `2.0.82`. Этот docs/evidence diff ничего
не развёртывает и не назначает новую версию. Флаги:
`branch_push=true`, `pr=true (draft #192)`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`, `llm=true` ровно для завершённого
run. Следующий шаг — review безопасной сводки и отдельное решение владельца о
Ready/полном CI и merge; после публикации draft запущен только быстрый CI.

Откат документационного результата — revert только отчёта и safe summary.
Сохранённые оценки/программу/снимки и рабочую БД не удалять. Для тестового
run marker-guarded cleanup уже выполнен и подтверждён; сырые первичные evidence
на сервере сохраняются для аудита.

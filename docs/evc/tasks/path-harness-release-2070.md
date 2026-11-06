# PATH-HARNESS-R1 — кандидат 2.0.70, PR/CI/review

Текущее дополнение: Ready PR175 создан, head1cd972f, первый frontend PASS,
pytest FAIL920/1 из-за отсутствующего origin/main в shallow checkout. Узко
исправлен новый unit (Git metadata fixture только в unit), runtime fail-closed
не меняется и отдельно проверяется;35 targeted и shallow2 PASS/before1 FAIL.
Новый source требует повтор backend/HTTP и CI, review пока NOT_DONE.
Primary и объяснение сохранены отдельно: path-harness-release-2070-ci.
Нижние CI NOT_RUN/активно создать PR относятся к прежним commits, не к текущему
состоянию. Без второго bump; merge/deploy/LLM не разрешены.
Локально922 backend/108 HTTP PASS по bytes source db79007c,35 targeted повторены
на SHA. Сначала source commit, теперь только docs/evidence перед push; новый CI
нужен exact final head/base. Старый full-verification1cd PASS, не новый CI.

## Результат и основание

Владелец ответил «да» на отдельный вопрос о выпуске harness 2.0.70:
назначение версии → push → PR → обязательный CI → человеческое review.
Это не code review нового head, не merge/deploy и не разрешение AC18.
Один результат — бесплатные доказательства AC06/07/09/10 и проверенный collector
будущего AC18: [исходная задача](path-ac06-ac10-proof.md),
[первичный отчёт](../reports/path-ac06-ac10-proof.md).
AUTH/R10 2.0.69 закрыт и повторно не выпускается как отдельная задача.

База main `3f42bba992e1a556e1961ca4abdaa0954a367153` /2.0.69.
Сохранённый handoff `2fa1ed667707c8f146951c844b673b79fecd9e08`, source
`2a868e5f909b0493e1e3b936e5407b07c73e811a`; их пакет и evidence неизменяемы.
Новая release-ветка `codex/path-harness-2070`, отдельный worktree.
Исходная ветка, три чужих untracked документа корня и другие worktrees сохранены.
Preflight без --candidate: ожидаемый exit2, предложен PATCH 2.0.70 без записи.

## Источники и решения

Прочитаны AGENTS.md, workflow/matrix/artifact-recipe/review-checklist,
release-раздел CONTRIBUTING, prepare_ready_release.py/prepare_release.py/
check_release_version.py/release_version.py/package.json, действующие CI workflows,
tests README/browser README и исходные task/report/план AC18.
Неизменённые README, архитектурные context/Registry, Change01/manifest,
M1 v1.4 FROZEN/CURRENT=NO и выбранные контракты переиспользованы из завершённой
разведки AC06–10. Управляющие документы и опубликованные источники не меняются.
Смысл → контракт → actual HTTP/PG → доказательство описаны в первичном отчёте;
выпуск добавляет только согласованную metadata/build и запись передачи.
Противоречий, требующих новой нормы, не выявлено.

Все восемь стоп-условий — нет для этого scope: 1) смысл не меняется;
2) API/PM/схема без изменений; 3) миграций/рабочих данных нет;
4) источники прежние; 5) новый контур не вводится; 6) права/секреты не меняются;
7) откат локальных release commits определён; 8) bump/push/PR/CI разрешены.
Merge/deploy/AC18 остаются за открытым отдельным gate владельца.

## План и проверки

1. Завершено: свежий main, штатный ready:prepare --candidate 2.0.70,
   повтор для проверки идемпотентности, diff/точные asset hashes.
2. Завершено: lint/build,145 frontend,921 backend/108 HTTP,22 release+CI regressions,
   адресный actual HTTP/owned-PG, две затронутые browser проверки и три
   collector-only DOM регрессии.
   Только новый собственный PostgreSQL16, синтетика, provider/mail disabled.
   240 integration исходного source переиспользуются для неизменных Python/Api
   bytes; полный новый integration/browser CI обязателен для release head/base.
3. Активно: локальный commit с отчётом, push, Ready PR, обязательные frontend/pytest/
   full-verification. Сохранить exact head/base/CI без status-only перебора SHA.
4. Ожидает CI: передать точный head человеку для review. Не выполнять merge/deploy.

Первый source выпуска `c972a88af085ea12520aae9380d2564984933054`:
921 backend/108 HTTP/145 frontend/22 release+CI и18 child HTTP/PG PASS;
browser 1 PASS/1 FAIL. Отрицательный result/failure/geometry/PNG/cleanup сохранён.
Collector измерял box до trial scroll и зависел от отдельного IO-based
toBeInViewport: получен ratio0 при box внутри viewport и успешной trial action.
Исторический механизм конкретного IO callback UNKNOWN, не product root cause.
В разрешённом scope исправления harness: текущая геометрия после trial scroll,
пересечение с viewport и clipping каждого ancestor, прежний горизонтальный gate,
visible/active/trial проверки. Негативные offscreen/clipping/overflow сохранены;
два новых actual Chromium DOM теста PASS, не подмена actual HTTP/PG/AS.
Повтор итогового browser набора после этого изменения обязателен. Номер тот же
2.0.70, повторного bump нет. Методология/критерии/admission/repair не меняются.

Source `ef0cc87cf947ad7c6a89ad341144d1f520a30ce8`: component AS/4 widths и две
DOM регрессии PASS, admin collector FAIL — DOM detached при предварительном
scrollIntoViewIfNeeded, во время штатного questionnaire re-render карточки.
У enabled-контролов убран лишний предварительный scroll: trial action сам
повторно находит элемент и прокручивает, не кликает. Добавлена actual DOM
регрессия12 последовательных замен элемента. Для disabled контроль не включается
насильно, прежний отдельный scroll сохраняется. Оба отрицательных run сохранены;
это не новые отказы AS и не причина PREP-DIAG-01.

Финальный source `4510aa4b7ac3db87f44cd422862a549d8c72c9a7`:
5 browser PASS,0 retry/skip/flaky;34 runner/release/CI PASS. Применимость
921 backend/108 HTTP/145 frontend/18 child PG c972a88 — по прежним bytes;
collector проверен заново. Новый offline CHECK:134 evidence files и355 source
hashes PASS, исходный CHECK также PASS. После export всех7 owned runs,
readback0 owned DB/0 connections, проверки ID/label собственный контейнер удалён
без FORCE; рабочая БД не затронута. Итоговый PR head только docs/evidence.

Проверки фиксируются в [отчёте выпуска](../reports/path-harness-release-2070.md).
AC18 NOT_RUN: [план](path-ac18-final-plan.md) сохраняется, окончательный deployed
SHA появится только после отдельного выпуска/разрешения. Реальная генерация на
ширинах не повторяется. Синтетический component-only fixture не заменяет full PATH
и не подтверждает human QA/допуск пилота. PREP-DIAG-01 отдельно, причина UNKNOWN.

## Независимые разрешения и откат

version_bump=true(2.0.70 PATCH), branch_push=true, pr=true;
merge=false, deploy=false, artifact_publish=false, program_activation=false,
paid_llm=false, working_database_access=false. Новый CI не равен deploy.
Схема/миграция/API: нет. Конфиг: только версия приложения и rebuilt assets.
Безопасность: без секретов, синтетические URL локального isolated test PostgreSQL.
Откат до merge — revert своих release commits; исходный результат 2fa1ed6 сохранён.
Удалять разрешено лишь marker-owned disposable test БД после экспорта evidence
и новый container с проверенным точным ID/label; без FORCE и без рабочей БД.

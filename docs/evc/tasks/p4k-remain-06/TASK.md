# REMAIN_06 v1.6 — чат, прогресс, серверное время и возврат

Основание: прямой запрос владельца «Выполнить REMAIN_06», 14.11.2026. Приложенные карточка1.6 и общий порядок1.0 — требования задачи, не самостоятельный допуск внешних действий. Исполнитель Codex пользователя, машина REDMI-Note-15-Pro, сессия P4K-REMAIN-06-v1.6. Base07166475b478c843243102c748d51f8564b7cec0 (локальный origin/main); ветка codex/p4k-remain-06, отдельный worktree. Исходный dirty checkout не меняется.

## Результат и область

Проверить все15 AC F17–F21 по уровням карточки. Исправлять только доказанные нарушения проекции frozen progress/time. Chat/draft/clipboard/Continue проверяются адресно; без Finish, нового Cycle ради проверки, Report, M6/M8/GC, real LLM/mail, общего TEST, OPS01. STOP: разрешённая AS представлена, при необходимости один Turn сохранён, явный Continue сохраняет ту же AS, UI проверен.

PM-04 LU04.2/3/5/6, UI-проекция C24/34/45. Сервер владеет route/completed/time/lease и snapshot R1, клиент не меняет нормы/лимиты. Новые предметные артефакты, публикация, схема, API и миграции не требуются; legacy долг не расширяется.

## Источники и решения

Прочитаны README.md, CONTRIBUTING.md, AGENTS; docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist,decision-register}.md; architecture/product-4k/{1.0/context,registry}.md, Change01 README/source И1/2/4/5/6/7 адресно; task SourceSet manifest2026-10-01; ADR002 C24/34/45/46 и change01-traceability T05/06/10; M1v1.4 README/source M1.6/9; M7v1.3 derived M7.5/8; M5v1.1 источник предъявленного материала; m7-return-time-integration и fix-return-heartbeat-race; R1v2 policy/manifest и первичные task/evidence по применимости. FROZEN/CURRENT=NO и WORKING не повышаются. M0 unavailable по manifest не блокирует заданную техническую UI-проекцию. Старый QA исполняется по собственному snapshot, не latest R1.

Код/потребители: web/js/screens/interview.js, wiring.js, state.js, index.html, interview.css; m10_product_flow.read_runtime, m7_return_integration; tests/frontend p3-a/p3-b/p03/e01; p3-a-preview, browser README/config; test_m7_cycle_planner_db. Предыдущий error helper05 на base уже включён, менять его не планируется. Все chat/meta/time/Continue функции текущей задачи принадлежат одному исполнителю на base07166475. Значимых новых предметных решений не требуется.

Стоп-условия workflow: 1нет(смысл сохранён),2нет(API/PM/схема сохранены),3нет(нет миграции),4нет(норма задана),5нет(новый контур не нужен),6нет(ACL/privacy/deploy сохранены),7нет(revert собственных code/build без потери истории),8нет(локальные controlled проверки в scope). OPS01 без допуска NOT_RUN.

План: разведка → before-регрессия → минимальное исправление → адресные renderer/loader/browser/HTTP/PG + lint/build/diff → review/commit/bundle. Обязательный CI будущего PR и человеческое review отдельно. Все release-флаги false: branch_push/pr/merge/deploy/version_bump/artifact_publish. Локальный commit/bundle входит в передачу. Откат: revert собственного code/test/build commit; immutable определения и БД не меняются.

## Идентичность входов

- ProductArchitecture.Change01 1.0/01: `docs/architecture/product-4k/1.0/updates/2026-10-01/source.pdf` SHA256 `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081` MATCH.
- M1 1.4: `docs/architecture/product-4k/m1/v1.4/source.docx` SHA256 `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975` MATCH.
- M5.Methodology 1.1: `docs/methodology/source-sets/2026-10-01/originals/M5.Methodology-v1.1.docx` SHA256 `dc96f9b48e0711326c0c4239d63f50a2fa1e63176a728f3e9eb4420f9efb77c1` MATCH.
- M7 1.3: `docs/methodology/source-sets/2026-10-01/originals/M7_Assessment_Cycle_v1.3_FROZEN_2026-09-30.docx` SHA256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10` MATCH.
- `/Users/vadim_bogachev/Downloads/P4K_REMAIN_06_v1_6.txt` SHA256 `48ffc23f4a0177727daae29bbb1794a13b7ded2b5c0a6e9e114a4e573fcb25d0`.
- `/Users/vadim_bogachev/Downloads/P4K_REMAIN_Execution_Rules_v1_0.txt` SHA256 `ece5f67dde34f7771e0084789f40617131e99d767ad5d8a57cac320320796c31`.

## Допуск архитектора14.11.2026

Прямое сообщение владельца: «Да, продолжаем как архитектор: подготовь PATCH 2.1.6, отправь ветку и создай PR. Merge и deploy пока не выполнять.» Ранее false для этих действий заменены в этой области: version_bump=true(PATCH2.1.6), branch_push=true(собственная codex/p4k-remain-06), pr=true(создать PR и сопровождать точный head/CI). merge=false, deploy=false, artifact_publish=false. Тот же исполнитель/worktree продолжает как архитектор; bundle повторно импортировать и реализовывать исправленное не требуется. Наблюдение CI в конечном профиле ниже; человеческое review и физические ограничения не присваиваются агентом.

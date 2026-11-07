# AS-PRESENTATION-R1 — кандидат2.0.71, PR/CI/review

## Результат и допуск

Владелец ответил «да» на точный вопрос:2.0.71 PATCH → version bump → branch push →
PR → обязательный CI → человеческое review. Это не принятие ещё не созданного
release head, не merge/deploy и не paid AC18. Одна независимо принимаемая правка:
[AS-PRESENTATION-DIAG-01](as-presentation-fix.md), [отчёт](../reports/as-presentation-fix.md).

Source handoff `6f5681e1dda369a11892865b34cf3fe137f61585`, product source
`36ef230a7205bbbab533b878a44d8d0a37dbfbde`. Исходные ветка, immutable пакет
SHA256 c50022dc7aaff950d752664af64a1e6970305a41b60cb453de6f3f1ade69ef78 и evidence
сохраняются. Новая `codex/as-presentation-2071`, отдельный worktree. Fresh main
e9639edef400e2c36425f0d1c3ca98b646fdb0c2 /2.0.70. Чужая TG-ветка и её текущие
изменения/3 untracked docs не затрагиваются.

## Источники, совместимость и решения

Повторно прочитаны AGENTS, release-раздел CONTRIBUTING, workflow/matrix/task-template/
review-checklist, prepare_ready_release.py/prepare_release.py/release_version.py/
check_release_version.py/package.json, прежний release2070 и новая source-карточка.
README/architecture context/Registry/Change01/manifest/M1v1.4 FROZEN CURRENT=NO,
C-34 и functional participant sources переиспользованы из source task: unchanged
22 hashes/9 Case refs. Новый смысл, методологический допуск и артефакт не вводятся.

Source → контракт → materialization/UI → regression описаны в исходном отчёте;
выпуск добавляет только metadata/build и передачу результата. Все8 stop categories
— нет: смысл/допуск не меняются; public API/PM/schema прежние; миграции/удаления
рабочих данных нет; применимый source есть; нового контура нет; права/секреты не
расширяются; rollback release commits определён; bump/push/PR явно разрешены.
Merge/deploy/paid PATH ожидают отдельного решения, не являются активным шагом.

## План и проверки

1. Завершено: fresh main/clean branch; preflight без candidate подтвердил2.0.70→2.0.71,
   ожидаемый exit2 без записи. Ready:prepare --candidate2.0.71 и повтор PASS,
  4 metadata/45 assets hashes идентичны, второго bump нет.
2. Завершено: новые backend937/HTTP108/frontend145/targeted50/lint/browser4 PASS.
   Новый browser probe concrete public materials/poll/4 widths на rebuilt release.
   Actual PG component6/120 browser исходного source переиспользованы по неизменным
   применимым bytes, не объявлены новым run.
   Никаких real mail/LLM/.env/permanent DB. Новый isolated PG не нужен для одного
   version metadata delta; обязательный integration/browser CI остаётся.
3. Активно: [отчёт](../reports/as-presentation-release-2071.md)/собственное review,
   commit/push/Ready PR. Offline CHECK35 evidence/39 source hashes/5 readback/8
   viewports PASS. Дождаться frontend/pytest/
   full-verification exact head/base. Сбои сохранять, source fix не менять скрытно.
4. После CI — передать человеку точный release head на review. Не выполнять merge.

## Независимые флаги и состояния

version_bump=true(2.0.71 PATCH), branch_push=true, pr=true;
merge=false, deploy=false, artifact_publish=false, program_activation=false,
paid_llm=false, working_database_access=false. CI release head NOT_RUN до PR;
human review NOT_DONE. Main/последний подтверждённый test e9639ed/2.0.70.
New final-SHA/post-deploy AC18 NOT_RUN; historical e963 runner PASS/visual BLOCKED.
PREP-DIAG-01 root UNKNOWN отдельно. AUTH/R10 и выпуск2.0.70 не переоткрываются.

Откат до merge: revert только своих release metadata/build commits. Source6f5681e
и пакет остаются доступны; published artifacts/saved AS не переписываются.
Для будущего выпуска revert штатным новым PR, без миграции БД. Baseline не назначен.

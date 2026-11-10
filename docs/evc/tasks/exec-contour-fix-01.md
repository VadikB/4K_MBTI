# EXEC-CONTOUR-FIX-01 — достоверный итог и безопасное завершение

## Контекст и решения

- Прямое поручение владельца от 10.11.2026: F02–F04, Q01–Q08, отдельный PR,
  обязательные CI/review, разрешённый merge/TEST deploy, без нового paid/provider run.
- Архив `P4K_EXEC_CONTOUR_FIX_01_2026-11-10.zip`, редакция TASK 1.0. Его
  `00_START.txt`, `TASK.txt`, `SOURCES.txt`, `COMMON_WORKFLOW.txt`, evidence и
  probes прочитаны как постановка и диагностические входы. Указание архива о
  другом авторе PR уступает прямому поручению владельца создать PR со своего
  аккаунта.
- База работы `origin/main@48e175da2a5dffd27e0722e0f50588f87a88fdbf`;
  аудиторский срез `8e3fb851f7920d3eee31312932057f035068422a` не откатывался.
  Ветка `codex/exec-contour-fix-01`, отдельный worktree
  `ARCH_WORKTREES/exec-contour-fix-01`, один исполнитель.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, EVC workflow,
  verification matrix, artifact recipe, decision register; Product 4K context,
  Registry, Change 01 README и адресные И-4/5/6, task SourceSet manifest;
  M1 v1.4 §§M1.6–1.10, ADR-002 C-45/C-54/C-46/C-56/C-67,
  M7 clarification/completion contracts, профиль первого Case и исходная
  карточка EXEC-CONTOUR-01/H1–H12. M1 v1.4 FROZEN/CURRENT=NO, M6 v1.8,
  M7 v1.3 и M8 v1.2 FROZEN; это источники смысла, не автоматический runtime-допуск.
- Повторный ASK, календарное закрытие во время ожидания анализа и завершение AS
  из другой вкладки подтверждены browser/PG. Paid full PATH/семантическая приёмка
  остаются NOT_RUN по прямому запрету новых платных прогонов.

## Контракт producer → validator `/2`

`assessment-execution-contour/2` — новая строгая квитанция synthetic technical
пути. `/1` не повышается до общего PASS; standalone `assessment-first-case/1.1`
проверяется прежним validator и исторический receipt не переписывается.

1. `run.json` задаёт owned run/DB, branch/SHA и хеши исходников. `first-case-receipt.json`
   остаётся immutable milestone с исходным Cycle/Session/AS и 0 ответов;
   составной receipt ссылается на его точные байты и hash.
2. Стадии идут как first case → последовательные закрытия AS того же Cycle с
   Session, before/after счётчиками, C-45 final и статусом finalization →
   закрытие сбора с причиной/временем/C-46 → явно открытый owner Report.
   Наличие названия стадии либо PNG само по себе не допускает PASS.
3. Перед cleanup тестовый readback экспортирует только безопасные ID, статусы,
   счётчики, C-45/C-54/C-46, pipeline/Results/Report refs. Он атомарно
   сохраняется и проверяется повторным чтением/hash. Validator сверяет его со
   стадиями, Report revision/audience/owner и completion receipt.
4. При неизвестном исходе после старта исполнения либо ошибке export/readback
   `destroy` не вызывается: `cleanup-deferred` и owned state/DB остаются для
   восстановления. После известного terminal успеха/FAIL и проверенного
   экспорта используется существующий marker-guarded `destroy`. Cleanup error
   фиксируется отдельным failure artifact; PASS исключён.

## Границы и откат

Продуктовый API, схема, предметные prompts/definitions и published snapshots
не изменяются. Test-only endpoint доступен только двум owned browser harnesses.
Новые платные вызовы, рабочие/production данные и расширение legacy исключений
не входят. Откат — revert изменений harness/validator и сохранить уже полученные
evidence; при `cleanup-deferred` сначала выполнить штатное восстановление owned DB
по marker, а не удалять её вслепую.

## Проверки и передача

Фактические результаты, SHA, H1–H12, Q01–Q08, CI/review/merge/deploy и
ограничения фиксируются в `docs/evc/reports/exec-contour-fix-01.md` и STATE.

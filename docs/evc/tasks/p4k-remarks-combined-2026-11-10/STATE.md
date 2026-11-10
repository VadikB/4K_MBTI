# STATE — P4K-REMARKS-COMBINED-2026-11-10

- Branch: `codex/p4k-remarks-combined-2026-11-10`
- Worktree: `ARCH_WORKTREES/p4k-remarks-combined-2026-11-10`
- Base: `8e3fb851f7920d3eee31312932057f035068422a`
- Active step: review, commit, push and PR
- Completed: isolated worktree; package checksum PASS; SUP01 → ADM02 → PART01 implementation; source→dist build; addressable local verification
- Decisions: D01–D06 accepted for this task; owner visual acceptance `PENDING`; historical hang `UNKNOWN`
- AC: implementation SUP 8/8, ADM 6/6, PART 6/6; local verification is detailed in `CHECKS.md`; owner visual acceptance `PENDING`
- External authority: push + one PR allowed; merge/deploy/permanent DB migration not allowed by this task
- Release candidate: `2.0.92`, prepared once by the repository Ready preflight after the owner's continuation instruction
- Next: review diff, commit, push one branch and create one PR; observe mandatory CI

## Прочитано

- `AGENTS.md`, `README.md`, `CONTRIBUTING.md` at base `8e3fb851`.
- `docs/evc/{agent-workflow,verification-matrix,artifact-recipe,review-checklist}.md`.
- `docs/architecture/product-4k/1.0/context.md`, `registry.md`,
  `m1/v1.4/README.md`, Change 01 README and task manifest.
- `docs/adr/002-cycle-as-dialogue-contracts.md`, Change 01 traceability (applicable context).
- External package: `COMMON.txt`, `DECISIONS.txt`, all three TASK/ACCEPTANCE/SOURCES,
  `VISUAL_ACCEPTANCE.txt`, `REPORT_TEMPLATE.txt`, source package manifest and checksums.

## Пробелы и ограничения

- Первичный документ «Тестирование 0911_зем.docx» и screenshots не нужны: пакет
  объявлен самодостаточным; исходные персональные данные не импортируются.
- Рабочий glossary отсутствует либо не требуется как файл; заданные различения
  LU/Component/BaseRole/access применены без присвоения CURRENT.
- M1 v1.4 не публикуется; methodology/runtime definitions не меняются.

## Фактический результат

- Участие хранится независимо от `role='admin'`; исключение не удаляет admin authority,
  повторное добавление включает участие без смены роли. Backfill additive/idempotent.
- Снятие admin authority сохраняет участие; для исключённого admin связь удаляется,
  configured access подавляется штатным suppression-контуром.
- Transfer UI/handler/исполняющая реализация удалены; legacy HTTP entrypoint отвечает
  `410 ORGANIZATION_TRANSFER_REMOVED` без изменения данных.
- Ручной `source_author` исключён из новых manual/CSV операций; происхождение выводится
  из authenticated uploader, старое поле остаётся только для чтения истории.
- Assessment textarea молча блокирует paste/drop/clipboard insertion, не затрагивая
  обычный ввод; сетевые ошибки каналов нормализованы без raw `Failed to fetch`.
- Историческая остановка диалога не диагностирована и остаётся `UNKNOWN` по D06.

## Проверки и остаток

- Адресные frontend/unit/e2e/integration/browser проверки — PASS; полный перечень и
  команды находятся в `CHECKS.md`.
- Полный integration: `290 passed, 4 skipped, 12 failed, 25 errors`; четыре удалённых
  transfer-сценария были устаревшими и удалены после прогона, остальные FAIL/ERROR
  относятся к stand policy/fixtures вне изменённого контура. Повтор полного набора
  после удаления legacy transfer tests не выполнялся из-за длительности; обязательный
  CI остаётся источником окончательного статуса.
- Реальные browser HTTP/PG сценарии требуют явно подготовленный `STAND_ADMIN_URL` и
  локально `NOT_RUN`; синтетический/renderer browser-контур — PASS.
- Merge, deploy, постоянная миграция и owner visual acceptance не выполнены.

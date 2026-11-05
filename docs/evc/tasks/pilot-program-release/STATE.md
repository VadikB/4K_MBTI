# PATH-PILOT-PROGRAM-01 — состояние передачи

- Текущая неизменяемая база runtime: `e63eba67d77fb73f7fb9bb219bc3fe5d3807a909` /2.0.66.
  PR171 принят/merged/deployed; [release closure](https://github.com/VadikB/4K_MBTI/pull/171#issuecomment-6660961795).
- Текущая ветка: `codex/pilot-program-publication`; локальный read-only preflight,
  не продолжение закрытой remote-ветки PR171. Подготовка f211e71 и harness bd2af6d/a60200d сохранены.
- Завершено: offline рецепт1.2/checksum, паспорт выпуска/run, 72 unit PASS,
  оба CLI help exit0, воспроизведение SEED-01 без SQL, найден browser pin1.1.
- Завершена [PATH-PILOT-HARNESS-01](../pilot-program-harness.md): бесплатный fix seed,
  receipt+SHA256+version selector, browser/summary exact refs; backend906, Node66,
  isolated bootstrap3, component browser1 PASS. Подготовка f211e71 сохранена;
  её отрицательный VERIFY остаётся историческим evidence базы3385145.
- R1/2.0.66 завершён: review a60200d, отдельное разрешение merge/test, squash e63eba6;
  точные head/base tree совпали, server/public readback и45 assets PASS.
- Активно: бесплатная подготовка публикации по «идем дальше»; publication/activation/paid PATH
  не разрешены. Working DB прочитана только в двух READ ONLY транзакциях с rollback.
- Свежий preflight 05.11.2026 19:14 МСК:32 таблицы/353 колонки/191 constraints/84 indexes/16 triggers
  совпали; legacy1.1/config/catalog/roles/9 Cases/27 QA и15 artifact checks совпали с источником.
  Версия1.2 свободна; candidate checksum b4e8270f… и snapshot daa715b1… сохранены.
- user_id4 найден как прежний publisher, configured superadmin, not suppressed; это техническая
  проверка, НЕ назначение владельцем издателя нового выпуска. Номер1.2 и publisher4 ждут решения.
- Retirement: переход published→retired и запрет resolution/start есть и проверены CI171;
  готового retire CLI/endpoint нет. Предложен узкий guarded administrative SQL только для новой
  версии без подключений, с quiescence/точным ID/checksum; его free guard regression ещё NOT_RUN.
  Сначала требуется решение об операционной процедуре; тест и его PASS обязательны до публикации.
- Известные источники не менялись: M2=61, план39/22 вне,55 условий,02→03→04→07→05→01→06→08,
  7200/259200, без SPEC.09 fallback; exact P/M checksum883c025c… принят ранее.
- CI неизменённого runtime: PR171 PASS (unit908/HTTP108/Node66/integration220,
  два explicit llm skip, пять browser lanes PASS); deploy42047619768 PASS.
  Новый docs/evidence commit не выдан за новый CI; push/PR здесь не разрешены.
- Main/test:e63eba6 /2.0.66; preflight сверил server SHA/версию заново.
  Нового merge/deploy в подготовке публикации нет.
- Постоянная БД: только READ ONLY metadata/source,0 writes. Provider calls0;
  публикация/активация/новые owned DB в этой подготовке не выполнялись.
- Новое evidence: [readback](../../evidence/pilot-program-publication-preflight/readback.json),
  [операционный проект](../../evidence/pilot-program-publication-preflight/operations-proposal.json).
- PREP-DIAG-01: UNKNOWN, отдельный продуктовый остаток.
- Полная задача: [pilot-program-release-preparation.md](../pilot-program-release-preparation.md).
- Паспорт: [pilot-program-1.2-release-plan.md](../../reports/pilot-program-1.2-release-plan.md).

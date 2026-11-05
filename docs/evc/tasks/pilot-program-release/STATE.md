# PATH-PILOT-PROGRAM-01 — состояние передачи

- Текущая неизменяемая база runtime: `e63eba67d77fb73f7fb9bb219bc3fe5d3807a909` /2.0.66.
  PR171 принят/merged/deployed; [release closure](https://github.com/VadikB/4K_MBTI/pull/171#issuecomment-6660961795).
- Текущая ветка: `codex/pilot-program-publication`; publication/readback/free bootstrap,
  не продолжение закрытой remote-ветки PR171. Подготовка f211e71 и harness bd2af6d/a60200d сохранены.
- Завершено: offline рецепт1.2/checksum, паспорт выпуска/run, 72 unit PASS,
  оба CLI help exit0, воспроизведение SEED-01 без SQL, найден browser pin1.1.
- Завершена [PATH-PILOT-HARNESS-01](../pilot-program-harness.md): бесплатный fix seed,
  receipt+SHA256+version selector, browser/summary exact refs; backend906, Node66,
  isolated bootstrap3, component browser1 PASS. Подготовка f211e71 сохранена;
  её отрицательный VERIFY остаётся историческим evidence базы3385145.
- R1/2.0.66 завершён: review a60200d, отдельное разрешение merge/test, squash e63eba6;
  точные head/base tree совпали, server/public readback и45 assets PASS.
- Завершено по отдельному «идем дальше» владельца:1.2/publisher4, free retirement
  regression и при её PASS/свежем preflight — новая ProgramDefinition и exact export.
  [Решение](../../evidence/pilot-program-publication-execution/owner-decision.json).
- Free owned SQL:17 новых guard +5 lifecycle +7 start/readiness =29 PASS; synthetic,
  provider disabled. Evidence сохранено до marker-guarded cleanup без FORCE;
 0 owned DB/connections, task-контейнер удалён. Постоянная БД не цель cleanup.
- Повторный preflight 05.11.2026 17:40:30 UTC:32 таблицы/353 колонки/191 constraints/
 84 indexes/16 triggers EXACT MATCH; legacy1.1/config/catalog/roles/9 Cases/27 QA/
 15 artifacts без drift;1.2 свободна, publisher4 authorized/configured/not suppressed.
- Один штатный publisher call, exit0: `specialist_pilot@1.2`, **id2**, published,
  checksum `b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718`,
  snapshot `daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce`.
  Новая программа и один role link; старые program/role/source и org connections
  неизменны. У1.2 подключений0. Activation/retirement/LLM/PATH отсутствуют.
- Exact receipt229612 bytes, SHA256
  `09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b`.
  Сервер: `/home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json`.
  [Post-readback](../../evidence/pilot-program-publication-execution/publication-result.json).
- Independent offline CHECK/REGRESSION: actual selector1.2 PASS,8 tamper negatives и
  reject `-O` PASS, network/DB/LLM0. Backend908 PASS/351 deselected; новый CI NOT_RUN.
- Retirement: exact SQL guards/immutability/rollback проверены в owned-БД, но это
  не race-proof и не готовый runtime CLI. Постоянный retirement не выполнялся;
  при необходимости точный id/checksum/no-connections/quiescence и отдельное решение.
- Известные источники не менялись: M2=61, план39/22 вне,55 условий,02→03→04→07→05→01→06→08,
  7200/259200, без SPEC.09 fallback; exact P/M checksum883c025c… принят ранее.
- CI неизменённого runtime: PR171 PASS (unit908/HTTP108/Node66/integration220,
  два explicit llm skip, пять browser lanes PASS); deploy42047619768 PASS.
  Новый docs/evidence commit не выдан за новый CI; push/PR здесь не разрешены.
- Main/test:e63eba6 /2.0.66; pre/post сверили server SHA/версию заново.
  Нового push/PR/merge/deploy нет. Локальная ветка содержит новые tests/docs/evidence,
  runtime/Api/scripts/assessment_definitions неизменны; три чужих файла main сохранены.
- Постоянная БД: публикация только новой1.2 и role link по разрешению; схема неизменна.
  Предварительные PENDING/0-write receipts сохранены как история, не текущий статус.
- Полный [набор evidence](../../evidence/pilot-program-publication-execution/verification.json),
  [исторический preflight](../../evidence/pilot-program-publication-preflight/readback.json),
  [прежний операционный проект](../../evidence/pilot-program-publication-preflight/operations-proposal.json).
- Free bootstrap actual published1.2 завершён: **PASS_BOOTSTRAP_ONLY**, process exit0,
  run `5d4f68db1fae48bf9c82be26b2bee390`, каталог9 Cases/27 original QA;
  users1, organizations/memberships/assignments/profiles/cycles0. Exact receipt bytes
  сохранены до cleanup, completion/provenance hash связаны; после cleanup offline
  summary и независимый CHECK PASS. Owned DB/state отсутствуют, active connections0.
  [Результат](../../evidence/pilot-program-1.2-bootstrap/remote-result.json),
  [cleanup readback](../../evidence/pilot-program-1.2-bootstrap/server-evidence/bootstrap/cleanup-readback.json).
- Первая попытка: ModuleNotFoundError:tests до preflight/БД из-за отсутствия
  PYTHONPATH в моей операционной команде. Сохранены исходный launcher/exit1/диагностика;
  исправлено только окружение команды и описание профиля, не runtime/admission.
- Адресные harness/source/summary/ownership unit110 PASS. Runtime sources e63 неизменны;
  прежние908 backend и29 SQL применимы к тем же файлам, заново не выдаются за новые.
- Server tracked clean/11 runtime file hashes равны e63. Но полный status НЕ clean:
 1203 прежних untracked web/dist assets и1 env-backup path; содержимое backup не читалось,
  файлы не удалялись/перемещались. Bootstrap не использует web/dist. Перед paid PATH —
  отдельный чистый execution checkout того же SHA; не cleanup deploy checkout.
- Следующий шаг требует отдельного разрешения **одного** paid PATH: fresh read-only
  status/preflight, exact1.2 selector, чистый execution checkout e63, новая owned-БД,
  штатные generation/tester/challenger/repair и gate; при допуске start/AS/0 ответов,
  при отказе evidence и остановка без платного повтора. Paid PATH пока NOT_RUN.
- PREP-DIAG-01: UNKNOWN, отдельный продуктовый остаток.
- Полная задача: [pilot-program-release-preparation.md](../pilot-program-release-preparation.md).
- Паспорт: [pilot-program-1.2-release-plan.md](../../reports/pilot-program-1.2-release-plan.md).

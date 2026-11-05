# PATH-PILOT-PROGRAM-01 — состояние передачи

- База runtime: `3385145201d5d365e08e9e8a6a6fb7e12a0aa258` /2.0.65, PR170 merged.
- Ветка: `codex/pilot-program-release-plan`; подготовка docs/evidence сохранена f211e71.
- Завершено: offline рецепт1.2/checksum, паспорт выпуска/run, 72 unit PASS,
  оба CLI help exit0, воспроизведение SEED-01 без SQL, найден browser pin1.1.
- Завершена [PATH-PILOT-HARNESS-01](../pilot-program-harness.md): бесплатный fix seed,
  receipt+SHA256+version selector, browser/summary exact refs; backend906, Node66,
  isolated bootstrap3, component browser1 PASS. Подготовка f211e71 сохранена;
  её отрицательный VERIFY остаётся историческим evidence базы3385145.
- Следующий шаг: отдельный допуск на PR/CI/review harness; новый CI NOT_RUN.
- Публикация/подключение рабочей БД/paid run пока запрещены, не PATH PASS.
- Открыто: номер программы1.2 предложен, не утверждён; свободность в БД UNKNOWN;
  полномочный publisher и проверенная процедура retirement до будущей публикации.
- Известные источники не менялись: M2=61, план39/22 вне,55 условий,02→03→04→07→05→01→06→08,
  7200/259200, без SPEC.09 fallback; exact P/M checksum883c025c… принят ранее.
- CI: новый NOT_RUN (нет push/PR). Последний runtime CI — PASS по PR170.
- Main:3385145, последний test readback2.0.65/3385145 из release closure;
  новое развёртывание/свежий remote readback здесь не выполнялись.
- Постоянная БД:0 connections/writes; provider calls0. Бесплатные SQL — только
  новые owned test/pytest DB, все удалены после evidence; task Docker удалён.
- PREP-DIAG-01: UNKNOWN, отдельный продуктовый остаток.
- Полная задача: [pilot-program-release-preparation.md](../pilot-program-release-preparation.md).
- Паспорт: [pilot-program-1.2-release-plan.md](../../reports/pilot-program-1.2-release-plan.md).

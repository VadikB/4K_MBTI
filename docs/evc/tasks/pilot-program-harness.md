# PATH-PILOT-HARNESS-01 — точный источник и исправление seed

05.11.2026. Основание: пользователь ответил «да» на бесплатное исправление seed,
точной привязки версии и регрессии без публикации/платного прогона.
База: документационный `f211e7184e226b202529e14caf6e2f54478601fa`, runtime
`3385145201d5d365e08e9e8a6a6fb7e12a0aa258` /2.0.65.

## Результат и область

Устранить SEED-01; разрешить явный выбор проверенного source receipt в существующем
published-pilot runner; сверять точные program refs до/после start и в offline summary.
Старый fixture1.1 не изменять, latest не использовать. Изменения только harness/tests
и относящихся docs, не продуктовый admission, repair, prompts или нормативный план.
Постоянная БД, публикация/активация программы, реальные LLM, merge/deploy не входят.

Источники: ранее прочитанные README/CONTRIBUTING/AGENTS, EVC workflow/matrix/recipe,
context/Registry, M1v1.4 FROZEN/CURRENT=NO, Change01/task manifest; повторно применимы
без изменений. Дополнительно прочитаны scripts/assessment_first_case.py,
scripts/test_stand.py, tests/path_start_release_source.py, path_start_release_inputs.py,
path29_browser_inputs.py, browser/path29-participant.spec.mjs и fixtures/preparation-receipt.mjs;
их unit consumers, tests/README.md, integration/test_pilot_start_admission_db.py.
Контракт — pilot-plan-start-admission-contract.md и принятый exact P/M v0.1.
Пробелы: позитив ID reservation отсутствовал; browser/source имели pin1.1.
Новый формат runtime не нужен: source ref — metadata harness, не право старта.

## План

1. Регрессия SEED-01, затем allowlist program table с прежними защитами.
2. Полный явный выбор receipt+SHA256+version до любых DB/provider действий;
   передача/повторная проверка в seed, сохранение точных байтов для summary.
3. Browser и summary сверяют exact selected program до/после start; все проверки
   AS/stages/lineage/start/timing остаются обязательными.
4. Unit/Node, backend минимум и integration bootstrap только новых owned test/pytest
   БД без provider. Синтетическая будущая program metadata обозначается явно,
   исходный human Case QA не подменяется новым review.
5. Локальный коммит, evidence и передача. Отдельного решения по push/PR нет.

## Проверки и критерии

- [x] Позитив reservation и отказы unsafe DB/table/occupied ID.
- [x] Старый1.1 и явно выбранный exact будущий source; incomplete selector,
      неверные bytes/hash/version/program refs — отказ до записи/LLM.
- [x] Сохранённый receipt пригоден для summary после удаления исходного файла;
      повреждение/подмена refs не дают PASS.
- [x] Общий browser validator принимает exact program и отвергает drift до/после start;
      прежние negative stages/admission/AS checks сохранены.
- [x] Бесплатный настоящий owned bootstrap/repeat/cleanup; future metadata —
      SYNTHETIC, не публикация/LLM/PATH.
- [x] Backend, адресные Node, diff и docs checks выполнены; пропуски объяснены.

Стопы: нормы/API/schema/миграции/новый artifact runtime — нет; секреты/постоянная БД
не меняются. Откат — адресный revert harness на базе; новые owned БД удаляются
штатно после evidence, не постоянная БД. Вне scope — публикация, paid PATH и выпуск.
Флаги branch_push/pr/merge/deploy/version_bump/artifact_publish/paid_llm_run/
permanent_database_write=false. PREP-DIAG-01 отдельно UNKNOWN.

## Результат и передача

LOCAL_VERIFIED / AWAITING_SEPARATE_RELEASE_AUTHORIZATION.
Подробный [отчёт](../reports/pilot-program-harness.md), [первичные evidence](../evidence/pilot-program-harness/),
обновлённый [профиль](../assessment-first-case-profile.md).

- `npm run test:backend` — **906 PASS**,334 deselected, exit0; один прежний
  StarletteDeprecationWarning, не регрессия задачи.
- `node --test tests/unit/test_assessment_preparation_receipt.mjs tests/unit/test_assessment_receipt_file.mjs`
  — **66 PASS**, exit0, в том числе все прежние admission/stage/AS negatives.
- `pytest -q --run-integration tests/integration/test_published_release_seed_db.py`
  на собственном localhost PostgreSQL — **3 PASS**; все три новые owned-БД удалены,
  минимум и исходные27 Case QA сверены; future metadata явно SYNTHETIC.
- PATH29 component-only на provider disabled — **1 PASS** для итогового сценария;
  owner cleanup сохранён, это не full PATH и не новое LLM admission.
- Дополнительно95 адресных Python PASS до добавления трёх bootstrap-summary регрессий;
  все98 таких проверок включены в итоговые906, не выданы за отдельный повторный run98.
- Новый offline VERIFY — PASS; loader отдельно проверен в свежих процессах с запретом
  импортов Api.config/Api.database/Api.llm, т.е. без .env/DB/provider side effects.
- `git diff --check`,30 локальных ссылок в6 документах и CLI `--help` — PASS.
  Product/source diff Api/web/assessment_definitions пустой.

Изменения исполнялись в worktree поверх f211e71 и связаны SHA256 исходников
в precommit-probe; точный финальный SHA передаётся Git commit/bundle и readback после
коммита, не притворяется заранее известным полем собственного коммита.
Схема и данные рабочей БД не проверялись заново и не менялись; прошлый schema PASS
не выдаётся за свежий. Затронутые harness SQL проверены новой isolated integration;
общий HTTP108/SQL runtime из PR170 — только baseline неизменённого Api, не новый CI.

Docker-контейнер этой задачи остановлен после проверки0 owned-БД/0 app connections,
AutoRemove подтвердил отсутствие контейнера. Остальные контейнеры не затрагивались.
Новые remote CI/human code review/PR/main/test deploy — NOT_RUN. Следующий шаг:
отдельно разрешить штатную передачу harness в PR/CI/review; при необходимости номера
приложения — получить решение по preflight. Публикация новой программы, постоянная
активация и один paid PATH остаются отдельными разрешениями. PREP-DIAG-01 UNKNOWN.

# PATH-PILOT-HARNESS-R1 — передача кандидата2.0.66 в PR/CI/review

05.11.2026. Основание: «идем дальше» после законченной локальной доработки;
владелец отдельно подтвердил **2.0.66 PATCH только PR/CI/review**, без merge/deploy,
публикации/активации программы и платного PATH.

## Результат и границы

Передать один независимо принимаемый результат — исправленный постоянный harness
с exact published receipt и рабочим seed. Реализация bd2af6dab8079f26e5cb9678dc1e1397ca6f74bb,
подготовка проекта программы f211e7184e226b202529e14caf6e2f54478601fa сохранены.
База main после свежего fetch:3385145201d5d365e08e9e8a6a6fb7e12a0aa258 /2.0.65.
Новая версия **приложения**2.0.66 не публикует предлагаемый ProgramDefinition1.2.

Прочитаны/повторно использованы неизменённые README/CONTRIBUTING/AGENTS, EVC workflow,
matrix/artifact-recipe/review-checklist, context/Registry/M1/Change01/task manifest;
предметный scope прежней карточки не расширен. Для передачи прочитаны release
preflight/checker и PR/CI workflows, их unit-тесты. Stop-условий для PR нет;
merge/deploy/артефакты/LLM/постоянная БД остаются вне разрешения.

## Подключение регрессий к CI

На базе3385145 integration job имел только TEST_DATABASE_URL, поэтому три новых
seed-теста с требованием явного STAND_ADMIN_URL пропускались бы. В job добавляется
явный localhost maintenance URL **того же CI PostgreSQL**, не рабочий `.env`.
Frontend job дополнительно запускает66 адресных Node receipt tests. Две regression
проверяют эти команды/совпадение CI-контура; обязательные jobs, gates и permissions
не ослаблены. Нового runtime/допуска ANY LIMITED не вводится.

## Проверки

- Harness bd2af6d: backend906 PASS, Node66 PASS, isolated seed3 PASS,
  component-only browser1 PASS. Код harness и источники в выпуске не меняются;
  эти результаты применимы по SHA256 из сохранённого probe/пакета.
- Первый `npm run ready:prepare` → exit2: согласованного номера ещё не было;
  main свежий2.0.65, предложен PATCH2.0.66. После ответа владельца используется
  единственный штатный `npm run ready:prepare -- --candidate 2.0.66`.
- Новый CI-конфиг/регрессии, release consistency, frontend lint/tests/build/dist,
  diff/ссылки проверяются до PR. Точные результаты фиксируются при передаче.
- Обязательный удалённый CI нового head/base ожидается; прошлый PASS PR170 его
  не заменяет. Дорогой платный LLM не нужен, не запускается.

Исторические VERIFY.py проектов f211e71/bd2af6d предназначены для **своих точных
checkout**, где product/version diff нулевой. Candidate добавляет отдельно разрешённый
version/frontend build; старый probe не ослабляется ради нового PASS. Для кандидата
версия/assets проверяются release checker и обязательным CI. Api/пакеты/методология
остаются неизменными; source hashes шести файлов harness должны совпасть с bd2af6d.

## Выпуск и откат

`branch_push=true`, `pr=true`, `version_bump=true` (2.0.66 PATCH);
`merge=false`, `deploy=false`, `artifact_publish=false`, `paid_llm_run=false`,
`permanent_database_write=false`. Человеческое review текущего кода ещё не получено.
Только после CI/review возможно отдельное решение main/test; автоматического merge нет.
Откат — revert этого самостоятельного результата, не изменение published1.1/QA/
snapshots. Схема и данные рабочей БД не меняются; cleanup только owned тестовых БД.
PREP-DIAG-01 отдельно UNKNOWN. Проект1.2/publication/retirement/итоговый paid PATH —
дальнейшие отдельные решения.

## Передача состояния

Ветка codex/pilot-program-release-plan. Активно: подготовка2.0.66 и PR/CI.
Main3385145; последний подтверждённый test2.0.65/3385145, новый deploy не запускался.
PR URL/head/CI links и выполненный local minimum дополняются после получения.

Локальный минимум кандидата: штатный ready preflight2.0.66 PASS; адресные release/CI
**22 PASS**, frontend **140 PASS**, lint PASS, diff/ссылки PASS. Первичные stdout —
docs/evc/evidence/pilot-harness-release-2066/. Все6 source SHA256 harness совпадают
с bd2af6d; прошлые906/66/3/1 применимы к неизменённой реализации, не являются новым
полным CI кандидата. Для CI добавлены только2 regression (полный unit ожидается908),
явный STAND_ADMIN_URL и Node step. Main/Api/published sources не менялись.

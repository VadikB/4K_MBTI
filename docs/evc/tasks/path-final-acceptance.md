# PATH-AC-AUDIT-01 — бесплатная сверка оставшихся критериев

## Результат и область

Завершена бесплатная сверка дополнительных AC исходного PATH 1.3 после положительного
run `2ff983f12c67494b990b0f85284b8d70` на runtime e63eba6 /2.0.66.
База этой карточки — `a7d7a9d5522cd96aae92369fc68aaff1e9fa60c7`, ветка
`codex/pilot-1.2-path`. Предыдущий пакет/primary evidence неизменяемы.
Основание — команда владельца «идем дальше»; продолжается только бесплатная
приёмка и исправление подтверждённых ошибок выбранного PATH по исходному заданию.

Включены адресные browser/HTTP регрессии, происхождение шести BaseRoles,
сверка отрицательных ветвей/viewport и локальное исправление установленного AC05.
Не входят новые provider calls, публикация/активация, рабочая БД, merge/deploy,
автоматическая приёмка владельцем или расширение утверждённого пилотного плана.

## Источники, контракт и границы

Прочитаны PATH 1.3/AC01…18, текущие `pilot-1.2-path.md` и STATE, EVC workflow,
матрица, CONTRIBUTING, browser README/config, `auth-r03.spec.mjs` (R10, PATH,
ADM27), frontend connection test, HTTP assignment/role tests, DB program/lineage
tests и потребители `organizations.js`, wiring, `api.js::fetchWithDeadline`.
README/архитектурный context/Registry/M1v1.4(FROZEN/CURRENT=NO)/Change01 и рецепт
из предыдущего неизменённого шага переиспользованы, новой нормы нет.

Прослеживаемость: PATH1.3/AC05 → точная organization+ProgramDefinition связь →
PS-01 UI entry/GET readback → `connectAdminOrganizationProgram` → browser R10.
Подтверждено: command проверял оба ID, но GET сверялся только по program ID;
чужая organization с той же программой ложно подтверждала подключение.
Это отдельная проблема UI-consumer, не PM-03/admission/repair/PREP-DIAG-01.

Все восемь stop categories: **нет** — смысл/PM/API/схема/источники/чувствительные
данные/потери/контур не меняются; откат — отменить только новый UI diff и сборку.
Исправление остаётся локальным, выпуск требует отдельного решения и CI/review.
Предметные артефакты и artifact debt не затрагиваются.

## План

1. Сохранить baseline и выполнить существующие бесплатные browser/HTTP проверки.
2. Воспроизвести foreign readback при успешном и потерянном ответе команды.
3. При подтверждении — узко проверить оба ID в обеих ветвях; покрыть регрессией.
4. Выполнить применимый JS минимум (lint/frontend/build/browser/diff), проверить
   ссылки и оформить точную матрицу доказательств/непроверенного.
5. Сохранить рабочий commit и передать пакет; не переносить прежний paid PASS
   на новый runtime SHA и не объявлять новый CI/deploy.

## Исходные проверки

- Browser selection22: первый запуск — `listen EPERM 127.0.0.1:18764`, до первого
  сценария (1 hook failure/21 not run); после разрешения localhost **22 PASS**,
  25.5s. HTTP synthetic, настоящий entry/dist. Это не новый real-provider PATH.
- HTTP assignment/role selection: **20 PASS**,7.50s, isolated sentinel DB port9,
  без `.env`, ключей и внешних подключений. Existing httpx deprecation — warning.
- Сохранены исходные Playwright JSON: sandbox failure, baseline22 PASS, AC05 before
  2 FAIL, промежуточный99 PASS/1 fixture FAIL и итоговый100 PASS.

## Установленный дефект и исправление

`PATH-AC05-FOREIGN-READBACK`: ожидали отказ/unknown при `organization_id=999`
для запроса организации3, даже если `program_definition_id=11` совпадает.
Получили success и применение чужой connection к своей карточке — после confirmed
PUT и после lost PUT. Две настоящие browser/entry/dist регрессии на e63 получили
`Expected:error / Received:success`; это не основание предполагать выдачу чужих
данных сервером и не доказательство такого события в рабочей БД.

В `web/js/screens/admin/organizations.js` добавлен один технический предикат
`isExactProgramConnection`: пара organization+program проверяется у command,
обычного GET и recovery GET. Чужое чтение не применяется, остаётся error,
кнопка доступна, тот же operation_id сохраняется для безопасного повтора.
Backend/API/схема и предметные правила не менялись. Пересобран `web/dist`.

AC08: прежний browser fixture содержал ненормативное название direction_system_leader.
Расширенная проверка дала отдельный fixture FAIL (99/1), не новый продуктовый баг.
Теперь fixture читает неизменённый `base_roles.json` M3/1.1 и проверяет все6 UI options:
specialist_expert enabled/value92; остальные5 disabled/empty value/объяснение.
Это synthetic availability/ID92, не настоящий published program/role receipt.
Происхождение runtime projection подтверждается неизменённым
`Api/assessment_programs.py::_normative_base_roles/_base_role_capabilities` и
реальным PG тестом `test_program_connect_resolve_and_immutability`, переиспользованным
из CI PR171; новый SQL-прогон здесь не выполнялся. Реальный выбранный role2/программа1.2
доказаны прежним paid run, не этим fixture.

## Итоговые проверки и первичные файлы

| Проверка | Факт / применимость |
| --- | --- |
| Полный `playwright test tests/browser/auth-r03.spec.mjs` |100 PASS,81.126s, retries0; настоящий entry/dist, HTTP synthetic |
| AC05 regression |2 FAIL before →2 PASS after; обычный и lost-command recovery; повтор сохраняет operation_id |
| `npm run lint:js` |PASS,exit0 |
| `node --test tests/frontend/*.test.mjs` |140 PASS; включает существующие deadline/body/abort tests |
| HTTP assignment/role + unit M3 |25 PASS,exit0; sterile env/port9/без `.env` и LLM |
| `npm run build:web` |PASS,повторная сборка побайтово идемпотентна |
| `git diff --check` |PASS |
| Offline `CHECK.py` / `-O` |PASS hashes/recorded results; optimized Python ожидаемо отвергнут |
| Viewports1440/320/390/768 |4 browser assertions/PNG; visual review1440/320: длинные сведения и существенное действие читаются |
| Backend/HTTP108/integration220/PR171 |REUSED только неизменённый backend/источники; не CI нового JS |

Полные локальные stdout, команды, exit codes, sterile environment, hashes исходников
и45 dist assets — [local-checks](../evidence/path-final-acceptance/local-checks.json).
Оператор [RUN_LOCAL_CHECKS.mjs](../evidence/path-final-acceptance/RUN_LOCAL_CHECKS.mjs)
не является новым runtime/harness: выполняет только перечисленный free local minimum.
[Before](../evidence/path-final-acceptance/ac05-before.json),
[after100](../evidence/path-final-acceptance/browser-final-pass.json),
[offline CHECK](../evidence/path-final-acceptance/CHECK.py).
Старые console warnings Node module type/httpx сохранены, не скрыты и не исправлялись
несвязанным рефакторингом. Отрицательные evidence не переименованы в PASS.

## Что именно дополнено к исходным AC

| AC | Дополнение этого шага | Что не следует из него |
| --- | --- | --- |
|02 |Проверен код contract409/unique code; positive org create/reload прежний real run |Отдельная полная browser-регрессия повторного создания org не добавлена/не доказана |
|05 |R10 pending questionnaire/null/lost PUT/reopen/logout22 baseline;2 новые foreign readback; deadline140 frontend |Отдельный end-to-end stall/error GET подключения не предъявлен; технический deadline test не весь AC05 |
|06/07/09/10/11/15 |Адресные HTTP25 и прежний PostgreSQL/CI точных назначений/прав/источников |Synthetic HTTP не новый real DB PATH; полная отрицательная матрица не выводится из одного PASS |
|08 |Все6 UI roles/options из M3 fixture проверены,5 недоступных не назначаются UI |Не реальный новый role admission и не изменение каталога/методологии |
|18 |Свежий auth/admin100,4 widths,логи/code hashes/пакет |Новый обязательный CI и человеческая приёмка ещё отсутствуют |

Для остальных AC действует точная [матрица положительного run](pilot-1.2-path.md#сопоставление-исходных-ac0118-без-расширения-результатов).
Этот шаг не закрывает все18 AC автоматически. Ни недостаток отдельного теста, ни
исторический блокер не объявлены новым продуктовым дефектом без воспроизведения.
Прежний real-provider PASS относится к runtime e63/2.0.66, а не к новому UI candidate;
повторная генерация не запускалась и не требуется для проверки foreign readback.

## Совместимость, риски и откат

Публичный контракт/данные/параметры/права сервера прежние, более строгий UI отвергает
только несовпадающую пару refs. Секреты/реальные пользовательские данные не читались
и не экспортировались. Новых DB/cleanup не было; рабочая БД вообще не использована.
Откат — revert нового JS/test/dist diff, не пересоздание программы или БД.
Все published источники M0–M8, исходный QA и accepted limited plan неизменны.

## Передача состояния

Локальная карточка готова; итоговый SHA/diff/bundle фиксируются в пакете.
Main свежим read-only `ls-remote` подтверждён: e63eba6 /2.0.66. Последний подтверждённый
test/deploy — e63/2.0.66, новый deploy не выполнялся; новую live-проверку test не делали.
CI нового изменения NOT_RUN, PR отсутствует. Предыдущий runtime CI не выдаётся за новый.
Для будущего выпуска предлагается2.0.67 PATCH, но номер **не согласован/не назначен**.
Следующий минимальный шаг — решение владельца о кандидате/PR/CI/review; merge/deploy,
рабочая активация и новый paid PATH в него автоматически не входят.

## Действия выпуска и следующий шаг

branch_push=false, pr=false, merge=false, deploy=false, version_bump=false,
artifact_publish=false, paid_path=false, working_db_writes=false.
Активных проверок/серверных процессов нет. Номер следующего выпуска не назначен.
PREP-DIAG-01 сохраняется отдельно: историческая первопричина UNKNOWN.

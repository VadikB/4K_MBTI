# Case / Cycle R00–R10 — пакет кандидата 2026-10-26

## Идентичность

- Base: `b3bbdc9e78880879e1d4fc930ef8c9cc9f200524` (`main`, приложение `2.0.28`).
- Application candidate: `3506bd54751a6561bb77a4feef3f99380dd863af`, версия `2.0.29`.
- Ветка: `codex/case-cycle-r1`; commits R00–R09 перечислены в `STATE.md`.
- Merge, deploy, публикация предметных артефактов и методологический допуск не выполнялись.

Версии: functional package `0.5`, compiler `0.5.0`, runtime bindings `1.2.0`,
Cycle execution manifest schema `2`, M6 Evidence prompt `1.0.1`, SourceSet
`2026-10-01`. SHA-256 файлов manifest:

| Артефакт | SHA-256 |
| --- | --- |
| functional package `0.5` | `fddb7bbbb036b2054126f65fd034656b52b0178dd33ae6e0615c904607746722` |
| runtime `1.2.0` | `8e2077bf27a87748102951cb6a1a444139134f6aba5901f339b7169ea60d4d56` |
| M6 Evidence `1.0.1` | `a0bb42457fe372abfcf0ff4c3c00a39e6ed78b969ccab70f3193b20667f3bb31` |
| SourceSet | `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8` |

## Проверки кандидата

| Контур | Фактический результат |
| --- | --- |
| release guard / `git diff --check` | PASS |
| backend unit | 592 PASS |
| HTTP contracts | 69 PASS |
| PostgreSQL integration | 167 PASS; 1 SKIP — explicit real-provider |
| frontend lint / content tests / build | PASS / 75 PASS / PASS |
| browser acceptance | 63 PASS, около 10 минут |
| controlled 27-row Case/function compile | PASS для package `0.5`; controlled gateway |
| remote CI exact head / PR review | NOT_RUN: ветка не отправлена, `gh` отсутствует |

Integration и browser использовали отдельные локальные БД с `pytest` в имени.
Стандартные тесты не выполняли реальные LLM-вызовы. Browser evidence находится в
локальном игнорируемом `.test-stand/browser-output/`; там сохранены безопасные
Report JSON, PDF/UI и server logs. Секреты и реальные пользовательские данные туда
не добавлялись.

## Матрица R10

| Набор | Статус | Основание / остаток |
| --- | --- | --- |
| N01 — 27 real preparations | STOPPED_AFTER_PILOT | C01/Sales transport PASS, AS admission FAIL; остальные 26 не запускались |
| N02 — 9 real API→M8 | NOT_RUN_DEPENDENT | Дефектная пилотная AS не предъявлялась; real 9 Case не запускались |
| N03 — 3 real browser функции | NOT_RUN_DEPENDENT | Controlled browser PASS; real-provider browser не запускался после pilot gate |
| N04 — multi-case Cycle | PARTIAL | Pause/reload/resume/additional Session PASS; 3 real generated AS NOT_RUN |
| N05 — различия контекста | PARTIAL | 27 controlled adaptations PASS; real-provider paths NOT_RUN |
| N06 — результаты и recovery | PASS TECH / real NOT_RUN | nonempty partial, insufficiency, no-result, expiry, retry, late fence и M8/PDF проверены controlled |
| N07 — PILOT-120 | PASS TECH / live NOT_RUN | `7200/259200`, 7199/7200/7201, UI и frozen snapshot PASS; общая program revision не публиковалась |
| N08 — upgrade/history | PASS TECH | coexistence и old/new Cycle dependency tests PASS |
| N09 — negative | PASS TECH / method NOT_RUN | deterministic/contract rejects PASS; методологический PASS не присваивался |

Отдельные статусы: technical controlled PASS; tester controlled PASS; real-provider
tester NOT_RUN; methodological acceptance NOT_RUN; Reliability NOT_RUN; publication
NOT_RUN. Недостаточность не преобразуется в ноль, а техническая ошибка — в результат.

## R10 real-provider pilot и ограничение

Credential подключён и без чтения значения подтверждён как доступный. Общая `.env`
содержит legacy alias `deepseek-chat`; запуск точного candidate
`0ead559a36346718f301f849590086e14f1005f0` явно закрепил provider identity контракта:
`deepseek/deepseek-flash`, version `1.0.0`, checksum
`a9b20456f413a8828ee2cca47356490ae98844542c8ad31c015f937abe951c8c`.

Одна синтетическая строка `A06.C01.SALES` выполнила реальные generation, tester,
challenger и одну repair-фазу. Transport всех операций PASS. Исходная deterministic
validation была PASS, но repair-кандидат завершился deterministic FAIL по отсутствующим
`material_refs/event_refs/character_refs/authority_refs/author_mapping` для четырёх
IndicatorID. Tester дополнительно сохранил blocking-находки: в Sales observability
остались имя и предмет авторского примера (`K1.I01`, `K1.I14`), что нарушает полную
профессиональную подстановку и `critical_prohibition:04`. Итог — честный
`AS_ADMISSION_FAIL`; это ожидаемая работа защитного gate, а не infrastructure failure.

Безопасная первичная трасса с operation/request IDs, timestamps, версиями, hashes,
token usage и классификацией сохранена в
`docs/evc/evidence/r10-c01-sales-real-provider-2026-10-26.json`; ключей в ней нет.
Полный синтетический raw trace сохранён в Git как
`docs/evc/evidence/r10-c01-sales-real-provider-attempt-raw-2026-10-26.json`
(SHA-256 `a9af0eee39a25813253ed18df9ac657cfc59243bae9a4aebd2f215c01c6c0530`).
Дефектная AS не была предъявлена, поэтому runtime, Evidence/IA, substantive admission,
M8, 26 остальных preparations, 9 API и 3 browser paths — `NOT_RUN_DEPENDENT`.
Неограниченная регенерация и ослабление tester не выполнялись.

Следующее точное действие — отдельная remediation двух причин, controlled regression
и повтор только C01/Sales на новом candidate SHA. Тест
`tests/llm/test_m10_real_cycle_db.py` по-прежнему не является достаточным R10 proof:
fixture вручную вставляет Turn и не доказывает штатный API путь.

## Откат и ограничения выпуска

Кодовый откат — вернуть R09 candidate commit и приложение `2.0.28`; опубликованные
snapshots, Case packages, AS, Evidence/IA и Results не удалять и не переписывать.
Schema R03 допускает старые и новые package memberships; возврат глобальной uniqueness
требует отдельного retirement/inventory. Merge требует remote CI точного head и
человеческого review. Deploy, pilot promotion, CURRENT/FROZEN и публикация методологии
остаются отдельными решениями.

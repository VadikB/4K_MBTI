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
| N01 — 27 real preparations | COMPLETE WITH OUTCOMES | 19 admission PASS, 5 AS FAIL, 2 INCOMPLETE, C03/IT repair HTTP 502; NOT_RUN 0 |
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

Remediation выполнена в `9f6d958174645754f4744842ca3eb184d1f5b7a7` без
ослабления admission. Повтор C01/Sales прошёл generation/tester/challenger/admission
без repair. Checkpoint расширен до восьми сохранённых preparations: шесть PASS,
C02/IT — содержательный AS FAIL после одной repair, C03/HR — aggregation INCOMPLETE,
C03/IT — повторный `LlmGatewayError` на двух checkpoint-запусках. Оставшиеся 18 строк
не запускались. Полные traces checkpoint сохранены в
`docs/evc/evidence/r10-matrix-9f6d958-checkpoint-2026-10-26.tar.gz` с SHA-256
`cb462afc73dfaf5a5afaa0078ccf2b7e06f31f36447c39caa620c2c4f7e77634`;
safe manifest — одноимённый JSON. API/runtime/M6/M8 и browser пути остаются NOT_RUN.

Safe diagnostic retry на `8eccc60` локализовал C03/IT: provider вернул HTTP 502 на
`generation_repair` через 162943.7 ms. Это environment/provider blocker, не вывод о
содержании AS. Независимо завершены C04 Sales/HR/IT (admission FAIL) и C05/Sales
(PASS); C05/HR прерван до результата и не учитывается как attempt.

Следующий checkpoint добавил C05/HR, C05/IT, C06/HR и C06/IT как admission PASS;
C06/Sales — admission FAIL. Всего завершено 17 preparations: 11 PASS, 5 FAIL и
1 INCOMPLETE; C03/IT остаётся отдельным provider blocker. Начавшийся C07/Sales был
прерван до результата и не учитывается. Актуальный raw archive SHA-256:
`ac53c953fa279d94ba540caa865eb12cff0ff8a65e551d8f26809b4bbd5bb85b`.

CASE.SPEC.07 Sales/HR/IT прошёл admission PASS. Всего завершено 20 preparations:
14 PASS, 5 FAIL, 1 INCOMPLETE; C03/IT остаётся provider blocker. Начавшийся C08/Sales
прерван до результата и не учитывается. Актуальный raw archive SHA-256:
`2bb01332bb873bfc81281e053f86da73011b614b47c4edfbf851a5ac8be21480`.

CASE.SPEC.08 Sales/HR/IT прошёл admission PASS. Всего завершено 23 preparations:
17 PASS, 5 FAIL, 1 INCOMPLETE; C03/IT остаётся provider blocker, C09 — NOT_RUN.
Актуальный raw archive SHA-256:
`c25fdd0cbca13753f9634f23982af1680a5e49f1d46fdcd66249c40101e70dee`.

CASE.SPEC.09 Sales/HR прошёл admission PASS; C09/IT завершился INCOMPLETE. N01
исчерпан: 26 сохранённых AS-результатов (19 PASS, 5 FAIL, 2 INCOMPLETE) и один
диагностированный provider blocker C03/IT; NOT_RUN=0. Актуальный raw archive SHA-256:
`59a286a92933d4ef3fc24de988f51051673e4d8ec7a5bcf10d2a76fdb1e39284`.

## Откат и ограничения выпуска

Кодовый откат — вернуть R09 candidate commit и приложение `2.0.28`; опубликованные
snapshots, Case packages, AS, Evidence/IA и Results не удалять и не переписывать.
Schema R03 допускает старые и новые package memberships; возврат глобальной uniqueness
требует отдельного retirement/inventory. Merge требует remote CI точного head и
человеческого review. Deploy, pilot promotion, CURRENT/FROZEN и публикация методологии
остаются отдельными решениями.

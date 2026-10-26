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
| N01 — 27 real preparations | BLOCKED_ENVIRONMENT | Controlled 27/27 PASS; real-provider gateway не настроен |
| N02 — 9 real API→M8 | BLOCKED_ENVIRONMENT | Полный controlled путь PASS; real 9 Case NOT_RUN |
| N03 — 3 real browser функции | BLOCKED_ENVIRONMENT | Controlled browser PASS; real-provider browser NOT_RUN |
| N04 — multi-case Cycle | PARTIAL | Pause/reload/resume/additional Session PASS; 3 real generated AS NOT_RUN |
| N05 — различия контекста | PARTIAL | 27 controlled adaptations PASS; real-provider paths NOT_RUN |
| N06 — результаты и recovery | PASS TECH / real NOT_RUN | nonempty partial, insufficiency, no-result, expiry, retry, late fence и M8/PDF проверены controlled |
| N07 — PILOT-120 | PASS TECH / live NOT_RUN | `7200/259200`, 7199/7200/7201, UI и frozen snapshot PASS; общая program revision не публиковалась |
| N08 — upgrade/history | PASS TECH | coexistence и old/new Cycle dependency tests PASS |
| N09 — negative | PASS TECH / method NOT_RUN | deterministic/contract rejects PASS; методологический PASS не присваивался |

Отдельные статусы: technical controlled PASS; tester controlled PASS; real-provider
tester NOT_RUN; methodological acceptance NOT_RUN; Reliability NOT_RUN; publication
NOT_RUN. Недостаточность не преобразуется в ноль, а техническая ошибка — в результат.

## R10 readiness и ограничение

Изолированный PostgreSQL-контур готов. Архив фиксирует ранее выданный допуск на
синтетическую real-provider матрицу, однако штатный `DeepSeekGateway` на машине
кандидата сообщает `gateway_enabled=false`. Provider contract: `deepseek`, model
`deepseek-flash`, version `1.0.0`, checksum
`a9b20456f413a8828ee2cca47356490ae98844542c8ad31c015f937abe951c8c`.
Ключи не читались и не выводились. Поэтому R10 остановлен как `BLOCKED_ENVIRONMENT`,
а не FAIL AS; оплачиваемые вызовы, N01/N02/N03 и реальные traces не создавались.

Следующее точное действие владельца контура: подключить штатный credential к
изолированному стенду для этого candidate SHA и подтвердить, что прежний бюджет
покрывает pilot C01/Sales и последующие 27 preparations. После этого сначала выполнить
одну C01/Sales через штатные Profile/API/queue/runtime endpoints; только при её успехе
продолжить checkpoint-матрицу. Тест `tests/llm/test_m10_real_cycle_db.py` не является
достаточным R10 runner, потому что его fixture вручную вставляет Turn; использовать его
как доказательство полного пути запрещено.

## Откат и ограничения выпуска

Кодовый откат — вернуть R09 candidate commit и приложение `2.0.28`; опубликованные
snapshots, Case packages, AS, Evidence/IA и Results не удалять и не переписывать.
Schema R03 допускает старые и новые package memberships; возврат глобальной uniqueness
требует отдельного retirement/inventory. Merge требует remote CI точного head и
человеческого review. Deploy, pilot promotion, CURRENT/FROZEN и публикация методологии
остаются отдельными решениями.

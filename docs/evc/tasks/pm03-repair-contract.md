# PM03-REPAIR-CONTRACT — frozen содержательный контракт во входе repair

## Выпуск 2.0.64 — 04.11.2026

Владелец ответом «да» явно согласовал последовательный выпуск PATCH 2.0.63
из PR #168, затем PATCH 2.0.64 из PR #169 с обязательным CI каждого head и
штатным deploy test. Текущие флаги `branch_push/pr/merge/deploy/version_bump=true`,
`artifact_publish=false`; pilot и реальные LLM-вызовы не входят. Прежние Draft/
false/NOT_RUN ниже — историческая передача, не текущий запрет согласованного выпуска.

PR #168 принят squash commit `2ba7c02a509b050eeeb43d2c6279b6f845e4a6be`, 2.0.63:
fast CI [41903653105](https://github.com/VadikB/4K_MBTI/actions/runs/41903653105)
PASS, [полный CI 41903653030](https://github.com/VadikB/4K_MBTI/actions/runs/41903653030)
PASS (integration/browser5/full-verification). Первый CI FAIL 41902176961 не скрыт:
собственная ST-R1 local-status регрессия исправлена в be7b9b0, auth/admin browser98
и frontend139 PASS; source/admission/prompts не затронуты.

PM03 перенесён `git rebase --onto origin/main 11b2a94…`: ровно четыре собственных
коммита на actual main 2ba7c02, без конфликтов. Backup
`codex/pm03-before-release-3152c5e` сохраняет исходный head
`3152c5e6b2406de6909291abcb439fc031532cd6`. Rebased head до подготовки выпуска —
`86cbff2fe49b6819eb28c738ed2ac3bd9aee8693`; implementation теперь 2ffd968.
`git range-diff` подтверждает те же patches; изменение контекста только в STATE.
Api, unit tests и первичные PM03 evidence побайтово совпадают с 3152c5e. Diff к
новому main содержит только PM03: две строки runtime, tests и docs/evidence.

План: повтор backend/HTTP на новой базе; canonical `npm run ready:prepare --
--candidate 2.0.64`; diff/links и версия/dist; обновление PR #169 с base main;
Ready и весь обязательный CI нового head; squash merge и deploy/readback test.
Перезапись только собственной PM03 remote-ветки выполняется с точным
`--force-with-lease=refs/heads/codex/pm03-repair-contract:3152c5e…`, не main.
Новый main/test не объявляется обновлённым до соответствующего факта.
Откат — штатный smoke rollback deployment, после успешного выпуска отдельный
revert PR, без удаления данных/snapshots. Защита permanent DB не меняется.
Схема/миграции/нормативная публикация N/A; PREP-DIAG-01 UNKNOWN, качество AS и
полный PATH всё ещё не доказаны. Реальный content FAIL не приписывается пропуску
system message без доказательства; платный repeat не производится.

Повтор на actual main + тех же PM03 source/tests: backend `python -m pytest -m
'not integration and not e2e and not llm'` — 763 PASS / 323 deselected, exit 0,
80.83 s; HTTP `python -m pytest -m e2e tests/e2e` — 108 PASS / 12 deselected,
exit 0, 32.09 s. Executable — прежний root `.venv/bin/python` (Python 3.12.13);
новой установки/доступов нет. `ready:prepare --candidate 2.0.64` — PASS; назначен
ровно один PATCH 2.0.63→2.0.64, штатный dist собран. Lint/frontend139/diff PASS.
Frontend dependencies переиспользованы из PATH node_modules с тем же lock SHA
`456b862b3ec25e171be63566091026c97de9c47dad9aa6c2fe1e926fa6f159ce`;
временная локальная ссылка не входит в commit. API/tests/артефакты после rebase
не менялись; синтетические gateway fixtures не доказывают реальную AS.

Предшествующий deploy 2.0.63 [41904412114](https://github.com/VadikB/4K_MBTI/actions/runs/41904412114)
PASS. Read-only permanent test: HEAD 2ba7c02…, tracked clean, service active,
readiness HTTP 200, `/users/version` = 2.0.63 и public_origin = test. Публичный
main.js и серверный файл имеют SHA-256
`4dd6cee55553e6a48ef8e6a380a34f58e076a2a65b437d37d6cb84cf24763905`.
БД не читалась и не очищалась. Развёртывание 2.0.64 до своего merge — NOT_RUN.

## Результат и область

Статус: DRAFT_REVIEW / техническое исправление завершено и передано, не выпущено.
Основание — явный ответ владельца 04.11.2026:
«Да, исправить сборку входа repair». Разрешена отдельная техническая доработка:
передать repair тот же зафиксированный Generation_contract_v0.2 и добавить
регрессии. Нет разрешения на новые prompts, изменение admission/числа repair,
платный LLM-прогон, merge/deploy или публикацию артефактов.

База: `11b2a94e164b97b95a0ef8f9a806ab2becf2b1a9`, `codex/path-start-01`,
draft PR #168. Новая локальная ветка `codex/pm03-repair-contract`, отдельный
worktree. PR #168 и исходный пакет PATH не меняются. Main/test при последней
read-only проверке — `7221671fbd9b16192a86b04b6eec36773f2dbf99` / 2.0.62.
Посторонние пользовательские файлы root checkout сохраняются.

Не входят удаление истории из Case/payload, новый выбор Case, переработка
методологии, repair policy, схемы, права, runtime publication и полный PATH repeat.
Расхождение входов не объявляется причиной пяти FAIL run aa2cbb… или исторического
PREP-DIAG-01 (UNKNOWN). Качество реальной генерации этим изменением не доказано.

## Источники и прослеживаемость

Прочитаны/переиспользованы неизменённые README.md, CONTRIBUTING.md, AGENTS.md,
EVC workflow/matrix/artifact-recipe/review/task-template, context/Registry,
Change01 README и task manifest, ADR-002 C-23/C-34, карта Change01.
M1 v1.4 FROZEN/CURRENT=NO; M5 v1.1 — выбранный источник, не новый runtime допуск.
Историческое отсутствие M6–M8 в раннем README не принимается за нынешний блокер;
в эту узкую сборку они не входят. Полная ревизия методологии не проводится.

Технический маршрут: PM-03 / существующий `repair_candidate` →
`_frozen_file(snapshot, 'generation_contract')` → system message → input checksum/
routing key → существующие provider trace и повторные tester/challenger.
Смысл и C-34 admission не меняются; PM-04 получает AS только по прежнему допуску.

- `Api/m5_functional_generation_service.py`: build_input_snapshot/generate/
  repair_candidate/prepare; отдельный frozen ref контракта уже существует.
- `Api/product_cycle_preparation_queue.py`: Case/profile и refs из exact Cycle;
  `Api/cycle_execution_manifest.py`: зависимости проверяются по frozen manifest.
  Path-only repair ref сам по себе не объявляется отсутствием runtime-защиты.
- `assessment_definitions/cases/competencies_4k/functional-personalization/0.5/`
  `sources/functional-v0.2/07_generation/Generation_contract_v0.2.json`:
  ContractVersion v0.2, WORKING_CONTENT_CONTRACT, файл SHA-256
  `4fc3cd1dd14e9f5a548266179e28706732cb9fd6034493b432fd67cad5718d2b`.
  Уже применяется generate; содержание G01–G13 не меняется и не встраивается в Python.
- Generator instruction v0.2 SHA-256
  `409e81a393ace10d83f35a96d15cb3cbc064266af80eeb71c142563ad5cedebf`;
  repair `m5_functional_repair/1.0.0`, prompt SHA-256
  `d0b424cbff9000dfd3aa55341f89c63f20964c254a0077dc65cf95d90c77ccf0`.
- `tests/unit/test_m5_functional_generation_service.py` — подставной gateway,
  frozen refs, admission и один repair; snapshot composition и HTTP consumers
  проверяются действующим backend/HTTP набором.

Диагностика на базе: 6 существующих адресных тестов PASS; техническая новая
проверка parity входов дала REPAIR_INPUT_CONTRACT_OMITTED. Отсутствовало именно
отдельное system message, не доказана полная потеря смысла: часть G-правил есть в
Case. Новая регрессия не реконструирует удалённый настоящий кандидат/исходные findings.
Размеры исторических полей измерены только на synthetic payload; их оптимизация
исключена из этого исправления.

Стоп-условия EVC 1–8: нет нового смысла, API/PM границ, схемы/миграции, отсутствующего
источника, нового формата артефакта, прав/PII/границы deploy или необратимого отката.
Область точно согласована владельцем. Зависимая реальная генерация/выпуск не разрешены.
Новый artifact debt не создаётся; существующие legacy-исключения не расширяются.

## План и проверки

1. DONE: диагностика и разрешение владельца; новая изолированная ветка от exact base.
2. DONE: новая регрессия до исправления — 5 FAIL/1 PASS; затем две строки сборки
   frozen contract в repair; generation service + snapshot composition — 23 PASS.
3. DONE: полный backend/HTTP, self-review/diff; первичные логи и отчёт сохранены.
   Следующий шаг — человеческое review и отдельный допуск публикации/выпуска либо
   обоснованного real-provider эксперимента, не случайное повторение PATH.

Локальный минимум EVC: backend-логика/сборка LLM-входов — `npm run test:backend`
и контрактные тесты с подставным gateway; дополнительно `npm run test:backend:http`.
Ни БД, ни очереди, ни endpoints не меняются: отдельный integration lifecycle N/A.
Frontend/lint/build N/A — web не меняется. LLM tests/платные вызовы NOT_RUN по области.
При локальной фиксации CI был NOT_RUN. Текущий план передачи ниже включает
push/draft PR; это не готовность к merge.

Критерии: точное одно system message с тем же контрактом, что generate; использование
snapshot ref, не default/current; checksum/missing dependency fail до gateway;
прежние findings/идентичность/trace checksum; не более одного repair и отсутствие
admission/compiled Case после повторного blocking FAIL. Синтетические ответы не
доказывают реальную функциональную эквивалентность AS.

Флаги текущей передачи: `branch_push=true`, `pr=true`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. По продолжению владельца «идем дальше»
04.11.2026 выполняется штатная передача уже согласованного исправления в отдельный
draft PR. Это обычный план передачи по CONTRIBUTING, не разрешение выпуска или LLM.
Откат — адресный revert двух строк сборки
и тестов; данные/сохранённые snapshots не удалять и не переписывать.

## Отчёт

Implementation commit: `d97625d7d6b1dba214890d8165791c3e2a9850b6`.
Последующая запись отчёта/evidence не меняет проверенные Api/tests.
Рабочее дерево на старте итоговых наборов clean. Использован Python существующего
локального test venv `/Users/vadim_bogachev/Developer/4K/.venv/bin/python`; пакеты
или доступы не переустанавливались. Команды ниже эквивалентны backend scripts
package.json, cwd — новый worktree; подстановка `<python>` — указанный executable.

| Проверка | Фактический результат |
| --- | --- |
| `<python> -m pytest -q --tb=short tests/unit/test_m5_functional_generation_service.py -k 'same_frozen_content_contract or contract_from_snapshot_ref or broken_frozen_contract or repeated_blocking_failure'` до fix | 5 FAIL, 1 PASS, 13 deselected, exit 1; отсутствует contract system message и проверки frozen dependency; policy closure уже PASS |
| `<python> -m pytest -q --tb=short tests/unit/test_m5_functional_generation_service.py tests/unit/test_m5_functional_snapshot_composition.py` | 23 PASS, exit 0, 3.32 s; технические gateway fixtures, LLM=0 |
| `<python> -m pytest -m 'not integration and not e2e and not llm'` | 763 PASS, 323 deselected, exit 0, 87.09 s |
| `<python> -m pytest -m e2e tests/e2e` | 108 PASS, 12 deselected, exit 0, 35.94 s |
| `git diff --check 11b2a94..HEAD` и локальные Markdown links | PASS |
| Diff protected paths к базе | `assessment_definitions`, `docs/methodology`, tester/admission, product queue и Cycle dependency resolver побайтово неизменны |
| CI / frontend / integration / реальный LLM | CI NOT_RUN (локальная ветка), frontend и integration N/A по области; real LLM NOT_RUN по прямому ограничению |

Backend/HTTP имеют прежний StarletteDeprecationWarning о httpx adapter; это не
FAIL и не основание расширять задачу обновлением зависимостей.

Первичные evidence: [verification.json](../evidence/pm03-repair-contract-2026-11-04/verification.json)
и четыре `.log.gz` в том же каталоге. SHA-256 распакованных логов и кода/источников
зафиксированы. Before относится к тем же новым tests на неизменённом source базы,
after/backend/HTTP — к implementation d97625d; в before новые 6 параметризованных
проверок не являются нормативным или реальным LLM-прогоном.

Изменённые файлы: две строки `Api/m5_functional_generation_service.py`; шесть новых
unit cases в существующем `tests/unit/test_m5_functional_generation_service.py`;
эта задача, STATE и локальные evidence. Новая абстракция/runtime не создавались.
Файлы методологии, prompts, manifests, source package, web/dist и версия приложения
не менялись. В branch `codex/path-start-01` и PR #168 новых commits нет.

Self-review: считывается именно snapshot ref через прежний fail-closed reader,
один и тот же текст контракта передаётся ровно один раз, checksum/routing key
учитывают новое сообщение; findings/два слоя и прежняя policy admission сохранены.
Это review агента, не человеческая приёмка и не methodological admission.

Совместимость: публичный API/схема/данные/права не меняются; старые traces и AS
не переписываются. Неполный/битый snapshot contract теперь блокирует repair до
gateway, как уже блокировал generation; fallback на current/default не добавлен.
Размер одного repair input увеличивается на существующий текст контракта;
число попыток, max_tokens, temperature, transport и таймауты прежние. Платная
стоимость/качество в этой задаче не измерялись. Данные БД не читались/не изменялись,
test cleanup не запускался, защита постоянной БД не затрагивалась.

Откат — адресный revert implementation и регрессий, без удаления сохранённых
данных/snapshots. На момент локальной фиксации main/test не обновлялись, ветка была
только локальной. Текущая передача push/draft PR описана ниже; CI не заменяется
локальными PASS. Ready/version/обязательный полный CI/merge/deploy остаются отдельно.

Следующая база с исправлением — `codex/pm03-repair-contract`, implementation d97625d
и docs/evidence commit передачи. Для качества AS и полного PATH остаются прежние
пять содержательных FAIL, отсутствие AS/start/оценочных ответов; причинная связь
с добавленным system message NOT_ESTABLISHED. PREP-DIAG-01 остаётся UNKNOWN.

## Штатная передача в draft PR

Создан [draft PR #169](https://github.com/VadikB/4K_MBTI/pull/169), base — ветка
[PR #168](https://github.com/VadikB/4K_MBTI/pull/168). В compare подтверждены только
9 PM03 файлов; runtime diff — две строки. Исходный handoff head b45da9c включает
только docs после проверенного кода d97625d; текущая запись добавляет ссылку на PR,
не меняет Api/tests. Результат fast CI нужно читать для актуального head PR;
срезы NOT_RUN в локальных evidence сохраняются, итог CI фиксируется в комментарии
передачи. Full verification/Ready и merge не заявляются.

Владелец продолжил работу командой «идем дальше» после локальной сдачи 04fcfdc.
Следующий ограниченный шаг: push `codex/pm03-repair-contract` и отдельный draft PR
с base `codex/path-start-01` / PR #168, exact base
`11b2a94e164b97b95a0ef8f9a806ab2becf2b1a9`. Такой stacked diff содержит только
PM03-REPAIR-CONTRACT, а не повторяет весь PATH. Две строки runtime и tests/evidence
после d97625d неизменны; выполненные backend763/HTTP108/targeted23 применимы.
Новый commit передачи меняет только эту запись и STATE; Markdown links/diff/identity
повторно проверяются. Branch push сам по себе CI не запускает; draft PR запустит
fast frontend/pytest, full-verification ожидаемо skipped по draft policy.

Read-only remote refs перед push: main `7221671…`, base PATH `11b2a94…`; удалённая
PM03-ветка ещё отсутствует. PR #168/source branch не меняются, main не переписывается.
Секреты/доступы/PII/state/provider raw messages не передаются. Документальные
CI NOT_RUN в предыдущем срезе verification.json — историческое состояние проверки,
не утверждение о результате будущего CI; текущие checks фиксируются ссылкой в PR.

Зависимость: сначала отдельно принимается PR #168. После его squash merge для
выпуска PM03 синхронизировать ветку с фактическим новым main, перенеся только PM03
изменения, и повторить проверки актуального head/base. Простого retarget старой
ветки при несовпавшей squash ancestry недостаточно. Это не разрешение делать merge
в PATH или main сейчас. Новый номер приложения, Ready/полный CI, deploy и real LLM
не включены; PATH остаётся BLOCKED_PM03, качество AS не объявляется исправленным.

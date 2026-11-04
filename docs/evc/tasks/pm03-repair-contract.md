# PM03-REPAIR-CONTRACT — frozen содержательный контракт во входе repair

## Результат и область

Статус: LOCAL_VERIFIED / техническое исправление завершено, не выпущено.
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
CI NOT_RUN — push/новый PR не разрешались; это не готовность к merge.

Критерии: точное одно system message с тем же контрактом, что generate; использование
snapshot ref, не default/current; checksum/missing dependency fail до gateway;
прежние findings/идентичность/trace checksum; не более одного repair и отсутствие
admission/compiled Case после повторного blocking FAIL. Синтетические ответы не
доказывают реальную функциональную эквивалентность AS.

Флаги: `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. Самостоятельные рабочие commit
допустимы; публикация/выпуск отдельно. Откат — адресный revert двух строк сборки
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
данных/snapshots. Main/test не обновлялись; новая ветка только локальная, CI не
заменяется локальными PASS. Для review/выпуска понадобится отдельный допуск
branch_push/pr и затем Ready/version/обязательный CI/merge/deploy.

Следующая база с исправлением — `codex/pm03-repair-contract`, implementation d97625d
и docs/evidence commit передачи. Для качества AS и полного PATH остаются прежние
пять содержательных FAIL, отсутствие AS/start/оценочных ответов; причинная связь
с добавленным system message NOT_ESTABLISHED. PREP-DIAG-01 остаётся UNKNOWN.

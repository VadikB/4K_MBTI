# EXEC-CONTOUR-FIX-01 — отчёт кандидата

Дата: 10.11.2026. Задача: `docs/evc/tasks/exec-contour-fix-01.md`.
Исполнитель и писатель: один, `codex/exec-contour-fix-01` в
`ARCH_WORKTREES/exec-contour-fix-01`. Основание: `origin/main@48e175da2a5dffd27e0722e0f50588f87a88fdbf`.
Проверенный source candidate: `7da92440` (полный SHA в `STATE.json`).
Документальный follow-up фиксирует mapping в `STATE.json`; release head,
merge и deploy фиксируются по мере появления.
Отдельный [draft PR #205](https://github.com/VadikB/4K_MBTI/pull/205)
опубликован от `VadikB`; быстрый CI для предыдущего HEAD прошёл, полный CI и
human review — до merge. Новый browser/guard follow-up требует CI на новом HEAD.

## Источники и связь

Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`,
`verification-matrix.md`, `artifact-recipe.md`, `decision-register.md`,
`docs/architecture/product-4k/1.0/context.md`, `registry.md`, Change 01
`updates/2026-10-01/README.md` и адресные source-разделы И-1/2/4/5/6/7,
`docs/methodology/source-sets/2026-10-01/manifest.json`
(`f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`),
M1 v1.4 §§M1.6–1.10, ADR-002, M7 clarification/completion contracts,
профиль первого Case и исходные EXEC-CONTOUR-01/H1–H12.
Приложенный архив `P4K_EXEC_CONTOUR_FIX_01_2026-11-10.zip`, TASK 1.0,
прочитан начиная с `00_START.txt`, `TASK.txt`, `SOURCES.txt`; диагностические
evidence/probes использованы только как вход, исторический receipt не переписан.
M1 v1.4 FROZEN/CURRENT=NO. Change 01 задаёт источник смысла, ADR-002 C-45/C-54/C-46
и M7 контракты задают цепочку; реализация здесь — test harness и validator, не
новая предметная норма.

## Изменение и проверяемая цепочка

- F02: `assessment-execution-contour/2` связывает owned `run`, code identity,
  неизменный first-case receipt с нулём ответов, упорядоченные закрытия AS одного
  Cycle/Session, C-45/C-54, C-46 и причину закрытия, terminal DB export,
  Results/Report revision/owner и факт открытия. Validator сверяет значения,
  типы, порядок, хеши, process exit, cleanup и отсутствие failure-artifacts.
  `/1` composite не получает общий PASS; standalone `assessment-first-case/1.1`
  остаётся в прежней области.
- F03: browser driver перечитывает Cycle/AS/фазу перед действиями, обрабатывает
  повторный ASK, `scenario_ended` другого клиента и закрытие во время ожиданий.
  Next ждёт предъявленную active AS; технические ожидания имеют явный timeout.
- F04: test-only endpoint экспортирует безопасные ID/статусы/счётчики/refs.
  Экспорт пишется атомарно, читается повторно и сверяется по SHA-256. После
  старта исполнения неизвестный результат или ошибка экспорта сохраняют owned
  DB/state (`cleanup-deferred`). Известный terminal успех/FAIL допускает только
  штатный marker-guarded `destroy`; ошибка cleanup оставляет failure artifact.

Изменены `scripts/assessment_first_case.py`, test-only gateway/stand fixture,
`tests/assessment_completion_evidence.py`,
`tests/assessment_execution_export.py`, browser completion/receipt/coordinator
и два test-only app, unit/adapter regressions. Продуктовый API, схема,
published methodology/scenario/configuration/prompt и web runtime не изменены.
SHA-256 ключевых файлов: `tests/assessment_completion_evidence.py`
`efe690c814deda0f0854ae210574af806cb8fa76d10d1a104c195d0e0130cdbc`,
`tests/assessment_execution_export.py`
`76ad973927893e67056ed511acc9c3f74a30589594a86b804286b4af7c348d7a`,
`tests/browser/fixtures/assessment-completion-profile.mjs`
`5b9e0b569403c7592c21866da8250b2a3ac87ee86af0c15d2b5bbf1fba17a092`,
`tests/browser/path29-participant.spec.mjs`
`a6f7f30d1488c65aec7a7a8adecd4186bba612acd257c19a3871a6a527c9b5c8`,
test-only gateway `Api/m10_test_gateway.py`
`b4aa4347d18823240e0e7cf66d8cff01d89c758101260f4d8ad13181ed34a05b`.

## Локальные проверки

| Проверка | Результат | Область |
| --- | --- | --- |
| Validator + normalizer unit (`pytest -q tests/unit/test_assessment_completion_evidence.py tests/unit/test_assessment_run_summary.py`) | PASS 61 | После последней правки validator. |
| F02 архивная offline-проба | PASS: valid `/2` принят, 5 semantic mutations и неполный общий normalizer отклонены, historical standalone принят | Хеш отчёта пробы `0930cc3df80f0cb51997c138d871f222201c011c9538d0e80cf05c071a08de41`; fixture синтетический. |
| JS driver/export adapter/cleanup guard | PASS 7 | Second ASK, другая вкладка, календарное закрытие, export write/readback/HTTP faults; реальный coordinator guard не вызывает `destroy` без export. |
| Runner/preparation Node | PASS 66 | Regression. |
| `npm run lint:js`; `npm run build:web` | PASS; PASS | Сборка не изменила `web/dist`. |
| `npm run test:backend` | PASS 1048, 476 deselected, 1 dependency warning | На предыдущем source candidate `a16a413c`; последующий follow-up изменил только JS browser/guard и документацию. |
| `node --test tests/frontend/*.test.mjs` | PASS 226 | Frontend/adapter, включая cleanup guard. |
| Три адресных integration-файла на `product4k_pytest_exec_contour_fix_01_int` | PASS 67, 1 dependency warning | Реальный PostgreSQL, без provider. БД удалена, собственный контейнер остановлен. Первая sandbox-попытка дала setup ERROR из-за недоступного localhost; повтор с доступом PASS. |
| Playwright controlled completion profile | PASS 2 | Owned PostgreSQL/browser, 2 AS того же Cycle; terminal export `calculated`/`ready`, финализация `queued`. Повторный ASK: 3 interim handoffs в первой AS, затем Report. Это test-only technical gateway, не полный AC18 composite. |
| Playwright C2 calendar while analysis pending | PASS 1 | После первого Turn обработка отложена за 30-секундное окно; browser/PG закрыли сбор по `calendar_deadline`, открыли Report, без UI transition/finish. |
| Playwright remote end from second tab | PASS 1 | Другая вкладка завершила первую AS; driver не отправил дублирующий transition для первой AS, дошёл до Report того же Cycle. |
| Playwright standalone PATH29 free | PASS 1 | Component boundary; cleanup owner/database/state подтверждены. Paid published selector не запускался. |
| EXEC03 browser `EXEC03_WITH_FIX01=1` | PASS 3 (C1–C9) | Реальные HTTP/PG/browser, provider disabled; accepted/lost, absent-before-server, reload/two tabs, ASK, replay/conflict, Next/time boundary. |
| `git diff --check` | PASS | До commit. |

Контроль C7–C9: run `44898b6cd1b74cb6adb4a4278f742cab`, fixture
`exec03_r1_technical_gateway/1`, source `48e175da2a5dffd27e0722e0f50588f87a88fdbf`,
284 startup fingerprints. Безопасные локальные файлы в ignored
`.test-stand/exec-contour-fix-01/exec03-evidence/`:
`source-identity.json` SHA `88ce6db64acd72e324a3eba9a09a719ea81dd42a0e5174db6925c5ac83b67fe5`,
`ask-lost-response-recovered.json` SHA `febcfa4dcdaffb645ac553d00c03cd92f88631f6ac52cc2c22d5bcb65ec90450`,
`budget-after-replay-new-write-rejected.json` SHA `520f3af68ff04e606e2d295bb0be9314d2727a4fcf0c1a63c3b9cfbebaea4cc3`,
`cleanup.json` SHA `ae2122ad4e387104d4ac0062d79e4e52410ff0ecde51355c934538009ea5dce5`.
Safe DB readback C7: до потери ответа, после восстановления и после
changed-payload conflict статус `closed`, неизменны 8 Turns, 3 C-45 handoffs,
2 clarifications, 6 operations и 6 events. C9: до сдвига времени статус
`active`, 1 Turn/1 operation; после replay и запрета новой записи статус
`closed`, 1 Turn/1 operation, 1 C-45 handoff, 3 events.
Controlled completion terminal export SHA
`004f77f2a52bc46206824e2e66e112aab9ec41b37f6887c2266edc0ba721047b`;
повторный ASK terminal export SHA
`af9c7fbf7f16398e25453d0bbccadfb6d185a96fe010b16ea17d11a087fae50c`,
cleanup SHA `3ea49bca9bd18db664fba1c50fb8cc4859a2b82057507c54f6a294ffa97ff304`;
calendar terminal export SHA
`21d6a6e710d9073e7562c23991b3cf8ef1080674e2179e5134fe5f5a0fd926aa`,
cleanup SHA `63f2d62af15c0d90f4002919926d33e1c0863c4a7157472768a59c7813379e8f`;
remote-end terminal export SHA
`29cef8f74a949247d5224f363af8bb0973ce16a4f2f5da2cc3f32dca975713c2`,
cleanup SHA `54a56b33e7f225352c8f4e2d0d61a23e406157445ae0e8739edc1511d5a898ea`;
standalone free cleanup SHA после guard refactor
`1d3f84cdb90ed74c0e7d2c1874470525955ccc8e523c0b93787ce756278c8f7`.
Marker, credentials, cookies, raw prompts, production/test working data в отчёт
не включены. Эти ignored evidence остаются локально, в PR идёт manifest.

Ключевые команды: `npm run test:backend`, `node --test tests/frontend/*.test.mjs`,
`npm run lint:js`, `npm run build:web`,
`npx playwright test tests/browser/runtime.spec.mjs --grep 'EXEC-CONTOUR technical profile' --workers=1`,
`npx playwright test tests/browser/runtime.spec.mjs --grep 'EXEC-CONTOUR repeated ASK' --workers=1`,
`npx playwright test tests/browser/runtime.spec.mjs --grep 'EXEC-CONTOUR C2 calendar closes' --workers=1`,
`npx playwright test tests/browser/runtime.spec.mjs --grep 'EXEC-CONTOUR scenario end from another tab' --workers=1`,
`npx playwright test tests/browser/path29-participant.spec.mjs --grep 'PATH29 owned backend' --workers=1`,
`EXEC03_WITH_FIX01=1 npx playwright test --config tests/frontend/exec03-browser.config.mjs exec03-send-recovery.spec.mjs --workers=1`.
Browser runs использовали только `STAND_ADMIN_URL` собственного контейнера на
`127.0.0.1:19622`; его значение и credentials в отчёт не копируются.
Черновой browser-тест другой вкладки сначала дважды дал FAIL из-за неготовой
вкладки/диалога, затем один раз из-за слишком широкого утверждения, включавшего
переход следующей AS; после уточнения первого AS итоговый прогон PASS.

## Q01–Q08

| ID | Состояние | Основание и предел |
| --- | --- | --- |
| Q01 | PARTIAL | Контрпримеры отвергнуты, synthetic valid `/2` и historical standalone приняты; настоящий полный paid owned composite не запускался. |
| Q02 | PASS_CONTROLLED | Second ASK: 3 interim handoffs первой AS; calendar во время ожидающего анализа и remote end другой вкладкой подтверждены отдельными browser/PG прогонами. Полный paid composite исключён. |
| Q03 | PASS_CONTROLLED | Driver Next ждёт active presented AS; controlled browser 2 AS, EXEC03 C7–C9 и integration guards. |
| Q04 | PASS_CONTROLLED_WITH_LIMIT | Fault injection write/readback/HTTP и unknown terminal проверены adapter; тот же cleanup guard, который вызывает coordinator, проверен с `cli` spy: `destroy` не вызван при неподтверждённом export. Обычный owned cleanup подтверждён browser. Unknown после commit в полном paid composite coordinator browser не запускался. |
| Q05 | PARTIAL | `/2` contract и terminal DB export проверены controlled browser; end-to-end paid first-case→Report того же run запрещён и NOT_RUN. |
| Q06 | PASS_CONTROLLED | Standalone free path, historical offline receipt, negative normalizer/process/cleanup/foreign context. Paid AC18 не повторялся. |
| Q07 | PARTIAL | C7–C9 browser/PG PASS; итог H7 ждёт включения EXEC-FIX-04. |
| Q08 | PARTIAL | Матрица, источники, проверки, PR текст и откат подготовлены; release/CI/review/merge/deploy зависят от внешней публикации и FIX04. |

## H1–H12 на текущем основании

| ID | Состояние | Доказательство |
| --- | --- | --- |
| H1 | PASS_CONTROLLED / PAID_NOT_RUN | Standalone PATH29 free PASS, очистка подтверждена; published AC18 receipt исторически сохранён. |
| H2 | PASS_CONTROLLED | Controlled browser 2 AS, один Cycle; `/2` валидирует original first-case link. |
| H3 | PASS_CONTROLLED_WITH_LIMIT | Driver отправляет scripted assessee Turns штатным UI; условные ветви не исчерпаны. |
| H4 | PASS_CONTROLLED | Повторный ASK browser/PG: 3 interim handoffs в первой AS; integration и adapter. |
| H5 | PASS_CONTROLLED | EXEC03 C7 accepted/lost и absent, reload/two tabs; replay/fencing. |
| H6 | PASS_CONTROLLED | C8/C9 и integration не создали новый Cycle/дубль AS; actual DB effects проверены. |
| H7 | PARTIAL_DEPENDENT | Controlled budget/time, calendar browser/PG и C9 replay; итог после включения EXEC-FIX-04, длинный wall-clock NOT_RUN. |
| H8 | PASS_CONTROLLED | Явный Next, ожидание active presented AS, 2 AS controlled; C8/C9. |
| H9 | PASS_CONTROLLED | Закрытие Cycle, C-46, pipeline в controlled browser/PG; M10 integration. |
| H10 | PASS_CONTROLLED | Owner Report открыт и readback `ready`; semantic/provider качество NOT_RUN. |
| H11 | PASS_CONTROLLED | Строгий `/2` validator и отрицательные regressions; полный paid receipt NOT_RUN. |
| H12 | PASS_WITH_LIMIT | Stage/export/checksum/source/substitution и process/cleanup protocol; provider usage остаётся не полностью наблюдаемым. |

## Открытые условия и откат

Свежий `main` перед release должен включить EXEC-FIX-04; затем повторить адресные
H7 checks на точном SHA. До Ready нужны `ready:prepare`, согласованный номер,
обязательный полный CI и human review. TEST deploy только после merge; окно
приёмки не сдвигается. Новые платные/provider прогоны `NOT_RUN` по прямому
запрету. Содержательное качество IA/Results/Report `NOT_RUN`.

Откат: revert этого отдельного PR; published артефакты и исторические receipts
не менять. При `cleanup-deferred` сохранить owned state/DB и восстановить по
marker перед штатным удалением. Merge/deploy SHA и результат TEST readback
записать после фактических действий, не подменяя их локальным PASS.

# UX-PATH29 — проверка кандидата 2.0.35

Дата: 29.10.2026, МСК. Все четыре задания — одна ветка
`codex/ux-path29-participant`, один кандидат, один будущий PR.
Base `a86775ff011a51831f9f86596be3dd776de79d11` / 2.0.34.
Исходный backend и схема — `89f4f267653f567cfcbaac803799b1a61c601701`;
UI/recovery checkpoint — `f0bac1156f05981d53d0ac483cd3ce48f1ac7517`.
Между ними менялись только frontend, browser/frontend tests, dist и отчёт.
После CI найдено адресное pre-existing M7 concurrency-нарушение; ниже выделены
исторические результаты и повторные проверки исправления, они не смешиваются.
Окончательный head и обязательный CI фиксируются в PR; merge/deploy ещё нет.

## Причины, а не только симптомы

1. Исторический P0: шесть отказов 28.10 около 22:40 МСК вызваны отсутствием роли/M4
   до генератора. Доказательство — [read-only incident](incident-2026-10-28.md).
   Исправление: явные tenant-scoped sources и отдельное разрешение подтверждённых
   ответов в M4, без global `len(configs)==1` и без выбора каталога участником.
2. Confirm ранее ожидал подготовку. Теперь 4К показывается сразу после записи
   confirmation; durable operation сохраняется до POST и находится сервером.
3. Новый прямой старт сначала обходил lazy-init чата. Регрессия S10-A установила
   гонку первого ответа; теперь используется штатный `loadInterview`.
4. Reload при открытии знакомства мог вернуть администратора в management:
   navigation intent теперь сохраняется до первого GET.
5. Возврат из dashboard открывал старый prechat, минуя readiness. Кнопки входа
   теперь читают journey, проверяют identity epoch и направляют в canonical экран;
   network error не включает legacy fallback. Во время загрузки предыдущие
   действия скрыты/disabled, при смене аккаунта старый ответ не меняет новый экран.

6. Режим «Как это работает» для уже начатой оценки открывал старую готовность.
   Он теперь показывает объяснение 4К и возвращает по актуальному journey,
   не запускает новую подготовку и не меняет M4/Cycle/started.

Один bootstrap повтор после прерывания завершился timeout после `bootstrap ready`.
Отдельная bounded диагностика на новой owned БД: `BOOTSTRAP_MAIN_RETURNED`, exit 0;
зависание не воспроизведено. В другом логе есть разрыв 24 минуты и PoolTimeout;
его причина не установлена. Таймаут продукта/LLM не увеличивался, эти прогоны
не засчитываются как PASS. Cleanup harness исправлен, чтобы закрытие уже умершего
browser context не скрывало первичную ошибку и не оставляло сервис/БД.

### Диагностика прерванного browser-прогона 29.10

Команда `caffeinate -i npx playwright test tests/browser/path29-participant.spec.mjs
tests/browser/auth-r03.spec.mjs --reporter=list --max-failures=1` остановилась:
56 PASS, E01 timeout после reload, 12 NOT_RUN. Лог
`/private/tmp/path29-review-browser.log`, screenshot в
`.test-stand/path29-review-output/auth-r03-E01-renders-accep-855a1--colors-and-AS-scoped-draft/`.
Падение не удалялось и не засчитывается как PASS.

Read-only `pmset -g log` подтвердил 29.10.2026, МСК:
13:53:03 — `Entering Sleep state due to 'Clamshell Sleep'`, 4056 секунд;
15:00:39 — `Wake from Deep Idle … EC.LidOpen/UserActivity`;
15:00:45 — failure screenshot, 15:00:47 — завершение прогона.
Активный `caffeinate` предотвращал idle sleep, но не предотвратил этот clamshell sleep.
Это объясняет часовую паузу и timeout локального прогона; конкретный порядок
восстановления сетевых запросов после wake из сохранённых данных не устанавливается.
На screenshot остаётся session restoration, это не доказательство потери ответов.
Код, лимиты и таймауты при диагностике не менялись.

Без правок: E01 `--repeat-each=3` — 3 PASS / 9.0s; полный
`tests/browser/auth-r03.spec.mjs` — 68 PASS / 1.0m, exit 0, retries=0.
Локальный прогон требует открытой крышки; CI не зависит от сна этого ноутбука.
Отдельный сквозной тест последнего review-mode изменения также завершился PASS.

## Источник → правило → код → проверка

| Источник / граница | Правило и данные | Фактическая реализация | Доказательство |
| --- | --- | --- | --- |
| M1 1.4 §4, M4 1.0, Change01 И-2/3; PM-02 | Подтверждённые источники и immutable M4, ответы не duties | `assessment_assignment_sources`, `acquaintance`, `participant_profile`, scoped state store | owned participant API, M4 lifecycle, scope history, 2 published configurations |
| TASK01, текущий auth contract | Trusted HTTPS origin, неизменные purpose/TTL/one-use/tenant | `public_origin`, реальные builders, public-only deployment config | controlled sink, malicious Host/forwarded, resend, rollback origin mismatch |
| W01 0.1 + поздние решения TASK03 | Последовательный чат, read-only поля, три canonical вопроса, адресная правка | onboarding HTML/CSS/JS, определения из published M2 | browser 6 viewport, short+zoom200, failed PUT, summary edit |
| M1 §5/9/10, Change01 И-2/3/6; PM-03 → PM-04 | Prepared не запускает время; один snapshot/Cycle/Session/AS | queue semantic dedup/fencing, exact-profile prepare, explicit prepared-cycle start | M10 integration/fencing, два UUID/две вкладки, started=0 до явной кнопки |
| M7 1.3, действующий planning contract | Эффективные time budget/calendar, не сумма длительностей | assigned timing/prepared plan из API, готовность только с admitted AS | parameter-resolution DB tests, R08 browser, preserved deadline/Additional Session |

M1 остаётся FROZEN/CURRENT=NO; источники M/Case/prompt не публиковались и не менялись.
Файлы/версии task SourceSet выбраны manifest от 01.10, это не M0 CURRENT:

- `M1/source.docx` 1.4: `5fa5ab5735dfe57fac6ef3c93aca50d149fbd7abd365edf80d362c10e2d7a975`.
- `M3.RoleProfile` 1.0: `a3c085e4182fe8bc5a82204a8d4679a09b85650ea79e2df24fb1ed8ab6604e06`.
- `M4.Context` 1.0: `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291`.
- `M5.Methodology` 1.1: `dc96f9b48e0711326c0c4239d63f50a2fa1e63176a728f3e9eb4420f9efb77c1`.
- `M7` 1.3: `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`.
- Task manifest: `f95a390f1257f4adbccf61be59bdcb0b99396501ca34cf117eb0efc10b237db8`.
- ADR-002: `4a4e0170bee7faf137301b342fec46b3e8e0209acd26dcb6b2dc7a788c58b25f`.
- Runtime M5 contract: `fb24821848d99d22e402bb9514b102ed6bf312a063539ddc4288ad3fd967ec39`.
- Runtime M7 contract: `8ff9021f5cdfe995c58369e996938ce0927abb2eceab78f4b0c6d7a8ceb182bf`.

Это идентичность выбранных источников и адресное чтение применимых разделов,
не новая полная содержательная ревизия исходных DOCX и не доказательство качества LLM.

## Команды и фактические результаты

Контур: созданный для задачи `path29-pytest`, PostgreSQL 16, loopback port 55449,
`TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55449/path29_pytest`;
`STAND_ADMIN_URL=postgresql://postgres@127.0.0.1:55449/postgres`.
Все browser/owned tests создают собственные `product4k_pytest_*` с marker;
developer/shared test/production БД не используются. Gateway — controlled.

| Проверка | Результат |
| --- | --- |
| `pytest -p no:cacheprovider -m 'not integration and not e2e and not llm'` | 646 PASS / 256 deselected, exit 0 |
| `pytest -p no:cacheprovider -m e2e tests/e2e` | 81 PASS / 12 deselected, exit 0; 12 немаркированных HTTP invitation tests входят в первый набор |
| `pytest --run-integration -p no:cacheprovider -m integration` | 169 PASS / 2 explicit llm SKIP, exit 0, 871.88s |
| `node --test tests/frontend/*.test.mjs` | 85 PASS, exit 0 |
| `npm run lint:js` | PASS, exit 0 |
| `npm run build:web` + повторная сборка и `git diff --exit-code -- web/dist` | PASS, воспроизводимость staged dist подтверждена |
| `check_release_version.py --base-ref origin/main`, shell syntax, diff-check | PASS, exit 0; одна версия 2.0.35 |
| Полный `npm run test:browser -- --max-failures=1` | 84 PASS / 13.6m, exit 0; до последнего изменения только review-mode |
| Полный `tests/browser/auth-r03.spec.mjs` после review-mode изменения | 68 PASS / 1.0m, exit 0; отдельно E01 3 PASS без правок |
| Дополнительный expanded U02 browser | 1 PASS / 48.1s, exit 0 |
| Сквозной PATH29 с возвратом из «Как это работает» при активном Cycle | 1 PASS / 51.9s, exit 0; тот же M4/Cycle, started=1 |
| Real provider / deployed HTTPS smoke | NOT_RUN до CI/review/штатного deploy |

Предыдущие FAIL не скрыты: два минимальных DB fixture не имели revision/считали
plan-only готовностью; они исправлены, полный повтор дал 169 PASS. Старые browser
помощники ожидали второй вход через prechat после нового явного старта; помощник
теперь принимает уже открытый чат, не выполняет повторного старта. Все retries=0.

## U01–U07

### CI checkpoint f0bac11 и исправление

[Run 40872272091](https://github.com/VadikB/4K_MBTI/actions/runs/40872272091),
pytest job `123442080822`: unit/HTTP/integration прошли; browser 83 PASS / 1 FAIL,
S10-A `drain` → `_clarify_interim` → `m7_clarification.present` → UniqueViolation
по (AS, question turn_id). Два обработчика успели прочитать отсутствие delivery
до блокировки; второй не перечитывал состояние после Cycle → AS lock.
Функция идентична base main; это отдельная причина, не sleep и не provider.

Контракт `docs/architecture/m7-clarification-contract.md` v1, draft QA:
SHA-256 `03d5aa51ef63489c75a48b2a0b276a02a054a794ee85e7159f3e30b4f70800c3`.
одна immutable delivery/question Turn в том же Dialogue, без изменения M4/C-54.
Адресное исправление — повторное чтение delivery под прежним lock, не подавление
исключения и не снятие constraint. Нормы, API, схема, snapshots и артефакты не меняются.
Два реальных соединения + barrier: до исправления FAIL с тем же UniqueViolation,
после sequential/concurrent **2 PASS / 12.84s**. Лог до:
`/private/tmp/path29-clarification-before.log`, после:
`/private/tmp/path29-clarification-after.log`.

Три локальных S10-A без изменений дали 2 PASS / 1 FAIL в browser-helper:
его deadline 5s включал фактический POST/start. Искусственная задержка настоящего
commit-ответа на 6s отдельно воспроизвела FAIL (`path29-start-before.log`).
Теперь helper ждёт start ack, затем переход UI; продуктовые таймауты не увеличены.
Новый полный unit — 646 PASS / 83.60s, HTTP — 81 PASS / 33.73s, exit 0;
логи `path29-ci-fix-unit.log`, `path29-ci-fix-http.log` в `/private/tmp`.
S10-A с задержанным настоящим start-ответом — **3 PASS / 4.3m**, exit 0;
лог `/private/tmp/path29-start-after.log`. Полные integration/browser были прерваны
по команде владельца: exit 2 / 84 PASS до KeyboardInterrupt и exit 130 / 73 PASS,
1 interrupted / 10 NOT_RUN соответственно. Они не являются полными PASS.
После следующей команды «продолжаем» запущены заново с начала, логи:
`/private/tmp/path29-resumed-integration.log`, `/private/tmp/path29-resumed-browser.log`.
На момент фиксации рабочего checkpoint они RUNNING; итог и CI точного head —
в [PR #124](https://github.com/VadikB/4K_MBTI/pull/124). До полного успеха проверок
и нового review передача не считается завершённой, merge/deploy заблокированы.

Review f0bac11 принят владельцем в чате и записан в PR comment 6496524820.
Merge/deploy на test после зелёного CI разрешены отдельно; текущее исправление
требует нового review точного head. Merge/deploy не выполнены.

Read-only preflight test: config 1 (`methodology_version=1.0`) и 2 (`1.1`) без catalog ref;
config 3 связан только с `e102-controlled/1.0`, `technical_fixture_only=true`,
organization-scoped, 2 cases. Новых операций и LLM-вызовов нет. Владелец решил:
deploy после gates продолжить, real-provider smoke **NOT_RUN**, каталог согласовать
отдельно. Fixture не считается допуском реальных кейсов, самовольной публикации нет.

| Сценарий | Проверенное | Граница |
| --- | --- | --- |
| U01 | PASS: реальные UI анкеты/участника/назначения/опубликованных refs; HTTPS mail sink; новая регистрация без готового M4; consent/3 answers/edit2/confirm/4К/readiness/start/первая AS и собственный Turn | Не реальное письмо и не real-provider |
| U02 | PASS: reload после ответов1/2, summary, 4К, queued/running/completed; clean auth session; возврат с dashboard в ту же готовность; answers/UUID/M4/Cycle сохранены | Account/tenant/revision scope отдельно DB/HTTP и generation tests |
| U03 | PASS: empty answer, вручную «Не знаю», failed PUT с сохранением ввода, double click; старые role/profile/start API не обходят mandatory gate | Согласие записывает только явный акт |
| U04 | PASS: две configs/одна явная; отсутствие binding → ожидание; после org binding ответы продолжаются; student/чужой tenant запрещены | Реальные источники действующего назначения выбирает ответственный, не агент |
| U05 | PASS controlled: durable identity до POST, lost reply после настоящего commit, две вкладки/одна операция; 403/409/503/network/failed различаются; DB fencing/recovery/повтор/idempotent start | P0 генерации НЕ ЗАКРЫТ до допущенного real-provider smoke |
| U06 | PASS Chromium geometry: 1440/1280/768/390/360/320, short height/zoom200, Onest/palette/back44px/grouped actions; проверены synthetic screenshots | Реальная системная клавиатура и платформенная матрица NOT_RUN |
| U07 | PASS ADM28 isolated: recipients/publication/self-assignment/management + own journey/reload; полный runtime в составе 84 PASS; последняя review-mode ветка — отдельный сквозной PASS | CI точного head обязателен |

U02 artifacts: `.test-stand/path29/adf87b32-b6e4-4c9b-961c-99216fc79ac4/`.
Финальный expanded U02/review-mode:
`.test-stand/path29/bf10f807-4a72-474d-8828-a13617608c9b/`,
лог `/private/tmp/path29-final-review-browser.log`.
Полный browser сохраняет результаты в `.test-stand/browser-results.json`, screenshots
и geometry прикладываются к test attachments. Не публиковать state.json, пароли,
auth query/cookies или raw provider traces; разрешены только synthetic proof files.

Платформы iOS Safari/Яндекс/Chrome; Android Chrome/Яндекс; Windows Chrome/Яндекс;
macOS Safari/Chrome/Яндекс — NOT_RUN как пользовательская матрица. Автоматический
Chromium viewport не подменяет эти PASS. Визуальная приёмка владельца/маркетолога
после deploy NOT_RUN; baseline и полная продуктовая приёмка не заявляются.

## Самопроверка перед передачей

- Источники, границы PM, совместимость и additive rollback указаны в задаче;
  M1 CURRENT не присваивался, опубликованные artifacts и governing docs не менялись.
- Auth/tenant/scope, повторные команды, frozen M4/Cycle, очередь/fencing, история
  назначения и запрет обхода mandatory проверены unit/HTTP/isolated integration.
- Старые unmanaged API сохранены; schema expand и ограничения downgrade описаны.
  Секреты/реальные ответы не читались и не публикуются; тесты используют owned БД.
- Шаблоны env, trusted origin и rollback синхронизированы; нет нового runtime
  fallback или выбора источников агентом. Номер кандидата увеличен один раз.
- Независимое человеческое review, обязательный CI точного head, deployed HTTPS,
  один real-provider smoke и визуальная приёмка остаются отдельными gates.
- Изменённые пути: [changed-paths.txt](changed-paths.txt); это самопроверка агента,
  не человеческая приёмка. Финальная воспроизводимость staged dist — PASS.

## Откат и последующая задача

Revert приложения штатным PR/deploy, сохранить additive bindings/operation journal,
scoped state, ответы/consent/confirmation и immutable M4/Cycle/AS. Public origin config
восстанавливается deploy rollback из backup; secret dotenv не читается/не меняется.
Старое приложение не знает новый organization-bound путь: после downgrade новые
canonical назначения могут быть заблокированы до forward fix; не присваивать им
global role и не переписывать snapshots ради обхода. Старые unmanaged clients
сохраняют свои контракты. Destructive backfill или удаление данных не предусмотрены.

После PR: обязательные frontend/pytest CI точного head/base и новое человеческое
review. Только затем разрешённый выпуск на test. Владелец разрешил ровно один
real-provider smoke на новых synthetic данных после штатного deploy, текущие
модель/лимиты/ключи без изменений, остановка при окончательном отказе. Это не допуск
нового каталога/публикации артефактов, pilot/production или следующих блоков.

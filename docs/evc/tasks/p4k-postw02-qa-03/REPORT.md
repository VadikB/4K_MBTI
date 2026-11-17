# QA-03 — локальный результат, 17.11.2026

Реализовано и проверено локально. Ветка `codex/p4k-postw02-qa-03`, исходный main
`71a9c535cee4aea094d2b49c2b73f39e22f99bbe` / 2.1.28.
**Код, тесты и собранный frontend: `8b3ca49d9398366b42ffea736dfeab885712fa93`.**
Следующий коммит содержит только документы/evidence. Версия приложения сохранена.

## Причина и исправление

Медленный `loadProductRuntime` вытеснялся новым serial каждые 1200 ms. Теперь один
актуальный контекст разделяет всю цепочку return-state/runtime и получает её результат.
Новый пользователь, identity epoch, Cycle, AS, экран, view/poll generation и команда
по-прежнему инвалидируют поздний ответ. Append-only trace и достигнутая фаза AS
не откатываются. Сведения подготовки сравниваются по server read_at одной операции;
реальная повторная постановка worker в queued после running допустима при новом read_at.

Обработчик Next отпускал удалённую кнопку; новая оставалась disabled. Доступность
подключённой кнопки теперь выводится из актуального pending-запроса и server retry.
Запрос привязан также к identity/view generation. Старый обработчик не запускается
после удаления карточки; старый finally не снимает блокировку нового контекста.
Двойной click блокируется. Потерянный POST, timeout и подтверждённый отказ сохраняют
прежнюю операцию. Проверка/восстановление её читают; новый prepare/Next/start не
создаются. Терминальная разрешённая сервером явная retry сохраняет прежний контракт.

При browser-проверке дополнительно подтверждены две технические причины в том же
пути: повторное добавление старых/новых действий при переносе preparation root и
`return undefined` из fast path, превращавший успешный GET в ошибку чтения времени.
Теперь смена состояния одной операции обновляет ту же карточку, сохраняет disclosure,
фокус/прокрутку и возвращает snapshot. При реальной замене текущая кнопка восстанавливается.

Сервер уже открывает authorized_pause после finish и закрывает collecting.
`paused + blocking_system_wait=false` — успешный ответ. UI признаёт paused/interrupted
и подтверждённое blocking wait независимо от достоверности остатка. В промежутке:
«Время на ответы сейчас не расходуется. Общий срок завершения оценки продолжает идти».
Active + false без согласованного контекста не назван паузой. При ошибке GET остаток
очищается, последняя цифра не выдаётся за текущую; неизвестное не превращается в 0.
Числовая позиция содержит компактное «Время недоступно» и пояснение в title, а не абзац.

Runtime-код изменён только в `web/js/screens/interview.js`; `web/dist` пересобран.
Серверная проекция, API, правила расчёта/календаря, схемы, snapshots и сохранённые
операции не менялись. Новые предметные артефакты/правила не вводились.

## Приёмка

| AC | Доказательство | Результат |
| --- | --- | --- |
| R1 | production loader: три последовательных медленных результата при продолжающихся вызовах; Chromium: GET удерживается через несколько poll intervals, результат каждого применяется | PASS |
| R2 | production loader: фоновые/ручные вызовы и явный null generation разделяют одну цепочку, включая медленный return-state; после ошибки новая цепочка; trace/фаза/read_at не откатываются | PASS |
| R3 | production handler: DOM replacement, timeout/network/completed и повтор чтения; browser network и настоящий 30s POST deadline через virtual clock; новая кнопка доступна без F5 | PASS |
| R4 | queued → running → completed, повторный dispatch; browser факты: 1 POST Next, 2 проверки того же operation_id; серверный selected readback, без скрытого prepare/start; failed без server retry остаётся disabled | PASS |
| R5 | owner/identity epoch/Cycle/AS/screen/view/poll; параллельное завершение старого и нового контекста; старый handler/finally не меняет новый | PASS |
| R6 | production renderer и HTTP: paused + false + 123/7200; browser paused + false, timer120:00 и корректная надпись | PASS |
| R7 | active collecting, blocking wait, paused, missing/null/строка/negative/NaN/Infinity, ноль отдельно, failed GET/восстановление; старый совместимый ответ | PASS |
| R8 | новая изолированная PostgreSQL: authorized_pause и blocking wait закрывают collecting; 20min исключённого ожидания не меняют остаток; календарный deadline постоянен, расстояние до него сокращается; существующая frozen Session regression | PASS |
| R9 | Chromium1440/390/320: одна кнопка, границы viewport, timeout/error recovery; same card/details/focus/scroll после обновления, компактный fallback; визуально просмотрены desktop1440/mobile390/320 | PASS |

PASS относится к указанному синтетическому локальному контуру. R8 проверяет реальные
production timing handlers и сохранённые интервалы в новой test-БД; полный Cycle,
реальная генерация/анализ/письма и живой сервер не проверялись.

## Выполненные проверки

| Команда / область | Результат / evidence |
| --- | --- |
| `node --test tests/frontend/qa03-runtime.test.mjs` на исходном `71a9c53` | 27 tests: 8 PASS / 19 FAIL, exit1; [до исправления](evidence/frontend-before.log). Тот же набор входит в итоговые431. До/после запускается настоящий исходник через существующий VM harness, не regex |
| `node --test tests/frontend/*.test.mjs` | **431 PASS**, exit0; [frontend](evidence/frontend-full.log), новые27 QA03 |
| Адресные production loader/commands/harness | PASS; [адресный прогон](evidence/frontend-targeted.log). Устаревшие тестовые предположения о serial/классах обновлены, защиты области сохранены; прежняя regex-норма blocking заменена behavior tests |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 .venv/bin/python -m pytest -q -m e2e tests/e2e/test_postw02_assessment_ui_http.py` | **3 PASS**, exit0; [HTTP](evidence/http.log). Новый случай проходит production HTTP route/projection с controlled storage, без подмены blocking=true |
| `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0 TEST_DATABASE_URL=<owned localhost test DB> .venv/bin/python -m pytest -q --run-integration tests/integration/test_qa03_time_intervals_db.py tests/integration/test_m5_cycle_runtime_db.py::test_cycle_session_membership_freeze_and_collection_boundary` | **3 PASS**, exit0; [DB](evidence/db.log), [cleanup](evidence/db-cleanup.json) |
| `npm run lint:js` | PASS, exit0; [lint](evidence/lint.log) |
| `npm run build:web`, повтор для сравнения байтов | PASS, exit0; [build](evidence/build.log), [45 файлов совпадают](evidence/build-reproducible.json) |
| `POSTW02_EVIDENCE=… npx playwright test tests/browser/qa03-runtime.spec.mjs tests/browser/preparation-status.spec.mjs tests/browser/remain06-chat.spec.mjs tests/browser/p3b-visual.spec.mjs --workers=1 --retries=0 --global-timeout=300000 --timeout=20000` | **12 PASS за30.7s**, exit0; [browser](evidence/browser.log), [факты390](evidence/browser/facts-390.json) |
| `git diff --check`, source/review/согласованность | PASS; API/schema/metadata release не затронуты |

Набор EVC применён по строкам JS behavior и visual; изменение production Python/БД
не делалось, полный backend/integration/browser всей системы не требуется ради
этого локального свойства. HTTP/DB выше — адресное подтверждение существующего
контракта. Штатные обязательные GitHub CI перед merge **NOT_RUN**: локальный этап,
remote ветка/PR/Ready не создавались. Перед будущим merge нужны актуальная база,
согласованный PATCH и все обязательные checks точного кандидата по CONTRIBUTING.

Все controlled runs: 1 worker, retries0, реальные LLM0/mail0. Начальные попытки
localhost были остановлены sandbox EPERM до продукта; штатная эскалация разрешила
локальные слушатели. Результат EPERM не записан как продуктовый FAIL. После каждого
доказанного сбоя исправлена причина, автоматических повторов всего run нет.
Отдельно сохранена [диагностика fast path до исправления](evidence/browser-fastpath-before.log).

## Снимки и ресурсы

- [Разрешённая пауза1440](evidence/browser/paused-1440.png).
- [Восстановленная кнопка390 после deadline](evidence/browser/recovered-button-390.png).
- [Неизвестный остаток320](evidence/browser/unknown-320.png).
- [Ошибка чтения390](evidence/browser/read-error-390.png).
- В `evidence/browser` находятся15 PNG (5 состояний ×3 ширины) и факты каждого viewport.
  Неизменённые compatibility-снимки60 файлов сохранены вне product diff в локальном
  `outputs/p4k-qa03-runtime-20261117/compatibility` родительского workspace.
- [Manifest](evidence/manifest.json) связывает источник задания, SHA кода и хеши проверенных файлов.
- Собственные HTTP fixture servers закрыты в afterAll. PostgreSQL test-БД удалена,
  собственный процесс остановлен, закрытие порта независимо подтверждено в cleanup.
  Рабочие БД, `.env`, реальные пользователи и чужие процессы не затронуты.

## Ограничения, review и откат

Источники/версии/пробелы и полномочия — [TASK](TASK.md). Content review пройден:
serial/context guards сохранены, чтение не создаёт подготовку, разрешённый retry
не подменён, DOM replacement/fast path не оставляют disabled, unknown не ноль,
timing formula/readmodel и исторические данные неизменны. Стоп-условий не выявлено.
Эмпирическая методологическая пригодность, доставка почты, исправление живого TEST,
ETA сервера и готовность пилота **не заявляются**. QA-05 остаётся независимой
read-only диагностикой. QA-04 не запускалась и должна начинаться после интеграции
QA-03 в согласованную базу с одним владельцем общих функций.

Откат: `git revert 8b3ca49d9398366b42ffea736dfeab885712fa93` отменяет UI/tests/dist,
сохраняя все операции и интервалы. При будущем выпуске revert проходит штатные
release/CI gates. Следующий этап — приёмка владельцем и отдельное поручение на
публикацию/PR либо merge; текущие merge/deploy/version_bump/artifact_publish=false.

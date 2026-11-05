# R1 / 2.0.65 — PR и первый полный CI

05.11.2026. PR [#170](https://github.com/VadikB/4K_MBTI/pull/170).
Первый head `b75d155f19a608c7122eaae990935632da00a974`, base
`2dc98c6b5b2637c6c505a90686e82f5e4274e763`, проверенный PR merge ref
`4585ca8273963d51c40be971fddacb5ebcfb39f9`.

- [Quick CI42026768804](https://github.com/VadikB/4K_MBTI/actions/runs/42026768804):
  frontend/pytest PASS; deploy-test штатно SKIPPED для PR.
- [Full verification42026768782](https://github.com/VadikB/4K_MBTI/actions/runs/42026768782):
  integration PASS; fast browser и четыре runtime shard FAIL; общий гейт FAIL.
  Это не успешный обязательный CI и не основание merge.
- Fast:99 PASS/1 FAIL, старый legacy-static PATH29 ожидает готовность, получает
  «Старт оценки пока заблокирован». Runtime1/4:2 PASS/2 FAIL, S10-A/B останавливаются
  на том же шаге знакомства. Локально исходный S10-B воспроизведён FAIL до изменений.
- Причина подтверждённого несоответствия тестовых входов: старый статический
  e102-controlled QA/component-каталог имеет непокрытые цели и не является принятым
  пилотным планом; новая UI-проекция больше не признаёт такой LIMITED готовым.
  Это **не** причина исторического PREP-DIAG-01 (UNKNOWN), не отказ генерации AS
  и не основание ослаблять продуктовый допуск.

Исправление только test harness/fixtures: прежние downstream component-сценарии получают явную
upstream plan-policy подстановку с pinned sources/route targets, ownership и
disabled-provider guards. Тот же main.app, не новый продуктовый runtime;
Api, methodology, schema, published program/Case/QA/prompts/admission/repair не меняются.
Реальная AS admission и остальные start/lineage/time проверки не подменяются.
Аннотация synthetic_upstream, fixture JSON и серверный marker не позволяют
выдать component PASS за допуск пилотной программы. Для real-provider/full-PATH
подключение подстановки запрещено до импорта продукта и подключения к БД.

Новая negative browser-регрессия запускает обычный main.app в assessment scope
**без подстановки**: LIMITED блокируется UI, HTTP409 с
`M7_START_NOT_ADMITTED:PILOT_PLAN_PLANNED_TARGET_GAP`; Cycle остаётся prepared,
calendar_deadline=null, interview скрыт. Прежний QA API-путь имеет другие
component-семантики и не выдаётся за assessment-допуск. Положительный реальный
gate/start остаётся в `test_pilot_start_admission_db.py` (upstream записи там
тоже явно SYNTHETIC, не новый human review/paid PATH).

Адресная проверка:57 Python PASS (27 guards/seed-order +30 start/stage), S10-B PASS,
настоящий negative browser PASS, legacy PATH29 component PASS. Первый локальный
runtime-набор13 PASS/2 FAIL сохранён, не переклассифицирован в PASS. C1/C2 обнаружили
отдельный дефект прежних test inputs: `prepare → revise_prepared_parameters`
оставлял AS/route decision на прежней ревизии. В `scripts/browser_stand.py`
короткий QA-тайминг теперь закрепляется через существующий `create_plan` **до**
`prepare`, без переписывания AS/таймера/исторической ревизии или обхода lineage.
Точная причина C1/C2 из старого server readiness не выгружена; staleness выводится
из порядка вызовов и проверяется неизменным gate после исправления входов.
Адресный повтор C1/C2:2 PASS, реальное фоновое time/calendar closure без нового Turn.
Остальные13 тестов этот helper не меняет. Цельный локальный15 PASS не заявляется;
новый обязательный полный CI проверяет финальный commit заново. Ветка/main/test раздельны,
human review нового PR ещё NOT_DONE. Постоянная БД не используется, LLM0.

Финальный локальный diff: backend862 PASS/331 deselected. HTTP108 PASS/
1080 deselected. Команды: `python -m pytest -q -m 'not integration and not e2e and not llm'`
и `python -m pytest -q -m e2e` (штатный root .venv Python3.12). Единственное warning —
уже имеющаяся Starlette/httpx deprecation. Это не ошибка продукта/CI admission.
HTTP выполнялся до добавления пяти чистых unit guards; HTTP/Api исходники после
него не менялись, его результат применим. Финальные57 адресных guards включают
все новые unit и повторяют start/stage checks. Ready preflight2.0.65 повторён PASS.

Первичные файлы: `ci-first-full-jobs.json`, `backend.log`, `http.log`, `guards.log`,
`runtime-before-timing-fix.log` (намеренно FAIL), `timing-corrected.log`,
`path29-component.log`, `real-limited-denial.json`, `ready-preflight.log` и
`cleanup.json`. Negative receipt извлечён из base64 body одноимённого Playwright
attachment до удаления локального output, без изменения полей; synthetic данные.
После сохранения evidence task-owned контейнер удалён; перед stop owned-БД и
соединений0, после AutoRemove точный ID отсутствует. Рабочая БД/чужие контейнеры
не затронуты. Данные временных БД намеренно невосстановимы; evidence сохранено.

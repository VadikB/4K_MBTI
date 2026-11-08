# AC18-FIX-02 — локальные evidence

Основание: `65c1f4c04466b60d4c6ce4611346fc92c617ed74` + рабочий diff ветки
`codex/ac18-fix02-preparation-start`. Дата: 07.11.2026. Данные синтетические;
реальный provider/LLM не вызывался.

## Матрица

| AC | Сценарий | Статус | Evidence / ограничение | Владелец |
|---|---|---|---|---|
| P2-AC01 | invalid JSON, отсутствующий/неполный/корректный/чужой protected review | PASS | `test_m5_functional_generation_service.py`, `test_assessment_start_readiness.py`; synthetic gateway | не просмотрено |
| P2-AC02 | admission закрыт при INCOMPLETE; AS не стартует | PASS | unit + HTTP + `test_pilot_start_admission_db.py`; первичный provider-инцидент не переписан | не просмотрено |
| P2-AC03 | queued/running/failed/network/service/ready и reload | PASS | frontend 150; browser readiness matrix на main; новый lost-start browser | не просмотрено |
| P2-AC04 | readback/idempotency/concurrent explicit start | PASS | SQL test `test_two_concurrent_explicit_starts_present_once_without_resetting_time`; существующие queue/fencing tests | не просмотрено |
| P2-AC05 | POST start commit + потеря ответа → GET того же runtime, одна AS, исходное время | PASS | новый frontend contract/unit/browser test; SQL concurrent start; 0 ответов в SQL gate suite | не просмотрено |
| P2-AC06 | revoked/stale scope и чужая область fail closed | PASS | `test_pilot_start_admission_db.py`, 7/7 | не просмотрено |
| P2-AC07 | работающий browser: first AS после lost response; 1440/768/390/320; horizontal overflow guard | PASS | `visual/*.png`; Chromium emulator, не физические устройства | не просмотрено |
| P2-AC08 | технический комплект передан; deploy/readback/owner acceptance | PARTIAL | PR #182 создан; CI повторно запущен после release bump; deploy/readback/owner acceptance не выполнены | не просмотрено |

## Кадры

- `visual/ac18-fix02-lost-start-1440.png` — SHA-256 `60449612d1a9f3b992deeac99b66c461a996e3fb3b6ae2a788d4ccb3a67c0b76`.
- `visual/ac18-fix02-lost-start-768.png` — SHA-256 `16baa3aa09fcc7c4722464afd13caf619ebca8925c556be1eea006542a6e41f1`.
- `visual/ac18-fix02-lost-start-390.png` — SHA-256 `4df64108ad9215aeade339d1bf4815c82f9b4543a63a538c8284fdd68d7df6bd`.
- `visual/ac18-fix02-lost-start-320.png` — SHA-256 `9e17c660782cbe3e6491af020f2ca6f09dc396c664a4709325e74307cf4f4d9f`.

Кадры показывают фактический frontend сборки рабочего diff после серверного readback
первой сохранённой AS. «До» не приложено: достоверного пользовательского кадра
исходного состояния в пакете нет; вымышленное состояние не создавалось.

## Команды и результаты

- Backend без integration/e2e/llm: `956 passed`, `354 deselected`, PASS.
- HTTP e2e: `108 passed`, `12 deselected`, PASS.
- SQL/HTTP PostgreSQL: `7 passed`, PASS; отдельный `postgres:16`, БД
  `f22_integration_pytest`, контейнер после теста остановлен.
- Frontend: `150 passed`, PASS.
- Новый browser lost-start: `1 passed`, PASS.
- `npm run lint:js`, `npm run build:web`, `git diff --check`: PASS.
- Release candidate: 2.0.76; первый CI release gate корректно отклонил 2.0.75,
  после штатного patch bump локальные build/lint/frontend 150/diff-check прошли.

Первая попытка SQL была `NOT_RUN_ENV`: sandbox запретил localhost до соединения;
повтор той же команды с разрешённым localhost завершился PASS. Первая попытка browser
была `NOT_RUN_ENV` из-за запрета локального listen; последующая тестовая ошибка strict
locator исправлена без изменения продукта, финальные два прогона PASS.

## Непроверенное

- real-provider M5 на текущем diff — NOT_RUN, отдельного разрешения нет;
- физический телефон и Safari/Firefox — NOT_RUN;
- PR #182 — создан; повторный CI после release bump — IN_PROGRESS;
- merge, test deploy и опубликованный readback — NOT_RUN;
- визуальное решение владельца — не просмотрено.

## Дополнение после merge — визуальный маршрут, 07.11.2026

Основание: `main@58bcfa291d8f49a08f18ecd8cc62113a1f544da4`, версия
`2.0.76`; PR #182 прошёл обязательный CI и был squash-merged. Дополнение не
переписывает результат локального кандидата выше. Источники и границы: Change 01,
`docs/methodology/source-sets/2026-10-01/manifest.json`,
`docs/adr/002-cycle-as-dialogue-contracts.md`,
`docs/evc/change01-traceability.md`, `docs/evc/assessment-first-case-profile.md`;
M1 v1.4 — FROZEN/CURRENT=NO. Предметный runtime, published-артефакты, БД и
провайдер не изменялись. Правило «готовность и явный старт до первой AS» проверено
через существующие `prepared_plan.start_readiness` и participant UI; код продукта
не менялся.

Новый `tests/browser/auth-r03.spec.mjs` проверяет четыре независимых синтетических
состояния `waiting`, `failed`, `unknown` и `ready`: загрузка и reload сохраняют
соответствующий заголовок и доступное по Tab действие; повторный POST подготовки не
отправляется, технический код ошибки не показывается, для отказа и неизвестного
исхода нет бесконечного spinner. Кадры в `visual/ac18-fix02-{waiting,failed,unknown,ready}-{1440,768,390,320}.png`
сняты после прокрутки к действующему блоку; на всех четырёх ширинах проверено
отсутствие горизонтального переполнения. Контрольные SHA-256 для 390px:

| Состояние | SHA-256 |
|---|---|
| waiting | `6ff907b8fd2828da6db1e423a99df1854f937fb77710061a0845cc14743a7eba` |
| failed | `81970d85d99818b96a15f3e6ccc2bf7529fbb3bd199c87cb6876f5df2107d948` |
| unknown | `448cd769297b01657b060eb03dc4bddf3e244edf89d7189c429511ea500288a6` |
| ready | `7fe60ceeee385d1d9916b9465c37013b887a797b6c5841e9ee77318414fdd104` |

Существующий browser-тест подтверждает действие из READY: один явный POST start,
потеря ответа, readback того же Cycle и первая AS на четырёх ширинах (`lost-start-*.png`).
Новый тест не выдаёт четыре независимые fixture за единый реальный переход
`waiting → ready`; фактические polling/HTTP/SQL контракты проверены отдельно
в исходном комплекте. Chromium emulator не заменяет физические устройства,
Safari/Firefox и человеческую оценку текста/компоновки.

Проверки этого дополнения:

- `AC18_FIX02_VISUAL_EVIDENCE=docs/evc/evidence/ac18-fix02-preparation-start/visual npx playwright test tests/browser/auth-r03.spec.mjs -g 'AC18-FIX-02'` — **2 PASS**;
- первая попытка в sandbox — `NOT_RUN_ENV` (`listen EPERM`), разрешённый локальный
  `127.0.0.1` повтор прошёл;
- на момент первичного прогона визуальное решение владельца — **PENDING**;
  последующее решение зафиксировано ниже.

Решение владельца, 07.11.2026: визуальные кадры и сценарии PR #183
**приняты** в текущем чате. Это принятие не меняет границы автоматических
проверок: физический телефон, Safari/Firefox и реальная сессия участника
остаются `NOT_RUN`.

После merge прочитан [CI #836](https://github.com/VadikB/4K_MBTI/actions/runs/42402780395):
`deploy-test` — **PASS**, итоговая строка deploy-лога —
`Test deployment completed: 58bcfa291d8f49a08f18ecd8cc62113a1f544da4`.
Публичный `https://test.4k-assistant.ru/users/version` вернул
`{"version":"2.0.76","public_origin":"https://test.4k-assistant.ru"}`.
Штатный deploy-скрипт сравнивает backend version, public origin и отдаваемый
`web/dist/main.js` с локальной сборкой, иначе откатывает deploy. Это published
SHA/asset readback, но не проверка реальной сессии участника на test.

Откат дополнения: revert коммита с новым browser-тестом и кадрами; merged
продуктовый fix #182 этим не затрагивается. Следующая зависимость: отдельно
разрешённый bounded real-provider прогон; визуальное решение владельца по
PR #183 получено, как указано выше.

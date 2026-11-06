# Q-DRAFT-01: локальное сохранение черновика анкеты

## Результат и разрешение

Владелец ответил «да» на узкую локальную правку сохранения черновика с регрессиями,
без выпуска и платного прогона. Base `d8ecd81d27a0633cbdc5f4d707804c32900e99d5`,
product main/test по последнему readback `61f34aa/2.0.71`.
Реализация зафиксирована локальным commit
`df9bdf8b3a3f86fb77ba4d295da292c5ace9d233`; последующее дополнение передачи — только
документация и сохранение двух дополнительных PNG, исполняемый код не меняется.
Историческая [диагностика](ac18-questionnaire-draft-diagnosis.md) и её43 первичных
файла сохраняются без изменения; это отрицательные результаты старого кода.

Локальная реализация и бесплатные проверки завершены **PASS**. Исправление не означает
выпуск, AC18 PASS или установленную причину исторического timeout.

## Ожидание → факт → причина → исправление

Ожидается: пользовательский ввод переживает поздний GET, а нетронутую форму
заполняет подтверждённая серверная revision. Факт до исправления:3/3 отрицательных
timing variants теряли введённые поля; пустой required author блокировал submit.
Причина воспроизводителя: асинхронная перерисовка восстанавливала старый пустой draft,
не сохраняя актуальный ввод. Причинная идентичность с конкретным старым AC18 не доказана.

В `web/js/screens/admin/organizations.js`:

- текущий ввод захватывается перед обновлением списка/завершением загрузки анкет,
  после действующих identity/generation guards;
- pristine signatures в WeakMap отличают нетронутую форму от пользовательского draft:
  новая пустая форма не создаёт draft поверх поздней confirmed revision;
- при смене assessment baseline формы обновляется после штатного restore;
- поздний `openAdminOrganizations` старой identity не перерисовывает новый аккаунт;
- denied401/403 очищает questionnaire drafts только соответствующей организации
  и не позволяет последующему capture вернуть отозванные данные;503 сохраняет ввод;
- общий renderer и намеренный reset draft при confirm не заменены глобальным capture.

Публичные API, server, БД/схема, published программа/Case QA, методология,
admission/repair и постоянный PATH runner не менялись. Test fixture ИТ-компании
остаётся синтетической, не methodological/human approval.

## Источники и тесты

AGENTS, README, CONTRIBUTING, workflow/matrix/recipe, context/Registry/Change01/
manifest/M1 и профиль — неизменённый ранее прочитанный контекст. Дополнительно:
capture/restore/async/confirm/clear ветки organizations.js, wiring submit/input,
organization-draft-key и существующие ADM28/auth-r03/R10 tests.
Новая норма или новый артефактный контур не вводились, schema migration не нужна.

Новые `questionnaire-draft-preservation.spec.mjs` используют действующий owned stand,
настоящий HTTP/PostgreSQL16 и задержку `route.continue()` реального GET. Без fake
Connection/resolver/response/DOM, без refill. Проверяются3/12 полей до ответа,
контроль после ответа, preview201/confirm200/GET200/SQL/reload и нулевой downstream.
`questionnaire-draft-guards.spec.mjs` — **synthetic HTTP lifecycle** через настоящий
dist: pristine confirmed read, сохранение live draft, разные user/org/assessment,
503/retry и403. Этот компонентный слой не заявляет реальную DB/admission/PATH.

Дополнительно выполняются существующие actual ADM28 и ИТ-анкета/4 viewport,
auth-r03 и R10 browser regressions. Backend/HTTP contract suites отделены от
actual PostgreSQL assertions; подставной успешный resolver их не заменяет.

ADM28/E10.2 seed включает синтетические технические Case QA assertions. Они не
подтверждают реальный human review или допуск целевой пилотной программы.

## Проверки и evidence

- `npm run lint:js` → PASS.
- `npm run build:web` → PASS; rebuilt45 dist assets, версия не назначалась.
- `node --test tests/frontend/*.test.mjs` →145 PASS, exit0.
- `PYTHON_DOTENV_DISABLED=1 /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q -m 'not integration and not e2e and not llm'` →937 PASS,354 deselected, exit0.
- `PYTHON_DOTENV_DISABLED=1 /Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -q -m e2e tests/e2e` →108 PASS,12 deselected, exit0.
- Browser combined140 scenarios →140 PASS, exit0, 746163ms, retries0, unexpected0/flaky0.
- Синтаксис/`git diff --check`, неизменность Api/scripts/assessment_definitions →PASS.
- Исторический offline verifier43 files →PASS с явным `--source-ref d8ecd81d27a0633cbdc5f4d707804c32900e99d5`;
  case-tree hash прежний `f0d742e438b7c642237c25675ec1e523ef3d6c3c2736b7e616fe7da9d480661c`.

Новый verifier `tests/questionnaire_draft_fix_verify.mjs` проверяет новые4 receipts,
однотипные source hashes, связи run/baseline/SQL/HTTP/cleanup и отсутствие refill;
результат **PASS36 primary files /4 actual HTTP/PG scenarios**, без refill,
source hashes совпали. Также проверены140 browser results, дополнительные actual
ADM28/ИТ-анкета и их2 cleanup,4 ширины анкеты1440/320/390/768. Итого6 owner cleanup PASS.
Tree checksum36 core files:
`93e2dc1322537fd5c48df8d3e697592737d149f6c433d879ad594a7abfc82d0d`.

Команда combined browser (с `STAND_ADMIN_URL=postgresql://postgres@127.0.0.1:55438/postgres`,
`BROWSER_PYTHON=/Users/vadim_bogachev/Developer/4K/.venv/bin/python`,
`P4K_EVIDENCE_DIRECTORY=.test-stand/questionnaire-draft-fix-20261106`):

```sh
/Users/vadim_bogachev/Developer/4K/node_modules/.bin/playwright test \
  tests/browser/questionnaire-draft-guards.spec.mjs \
  tests/browser/questionnaire-draft-preservation.spec.mjs \
  tests/browser/questionnaire-it-inputs.spec.mjs \
  tests/browser/adm28-real.spec.mjs tests/browser/auth-r03.spec.mjs \
  tests/browser/program-connection-feedback.spec.mjs --workers=1
node tests/questionnaire_draft_fix_verify.mjs
```

[Безопасные primary receipts/PNG и summary](../evidence/ac18-questionnaire-draft-fix/).
140 результатов разделены:117 synthetic HTTP auth-r03,10 synthetic HTTP R10,
7 новых synthetic HTTP guard tests,4 новых actual HTTP/PG preservation,
1 existing actual ADM28,1 actual ИТ-анкета/viewport. Не все140 являются PostgreSQL checks.

| Новый адресный сценарий | Run ID | Итог |
| --- | --- | --- |
| first-three-1440 | 40a42accc7d04c6ea722e647e83a1be6 | PASS, потеря0, refill0 |
| first-three-390 | 395e97b37ee04f3da2f62ed46b290cf7 | PASS, потеря0, refill0 |
| all-fields-1440 | 9c7d22c61aca4b3a9ef90236cb5454b4 | PASS, потеря0, refill0 |
| read-complete-control | 62b48837ca134658b974c85b54256555 | PASS |

Во всех4 новых прогонах native validity=true, preview201/confirm200/GET200,
SQL revision.confirmed и все12 полей после reload. Ровно1 preview/confirm,
questionnaire revisions0→1; profiles2→2 (исходный E10.2 seed), assignments/preparation/
Cycle/AS/turns0→0. Эти counts не распространяются на existing ADM28 self-assignment,
который намеренно создаёт назначения в своей отдельной owned-БД.

Визуально проверен PNG1440 после позднего GET: все3 ранее терявшихся поля заполнены.
Новый actual case390 и повторная ИТ-анкета на4 ширинах проверены assertions/geometry/PNG.
Общий140 набор дополнительно сохранил прежние recipient/confirmed revision, auth,
negative readiness и viewport regressions. Полная отдельная integration-матрица
не запускалась: schema/server не меняются, адресные actual owned-PG regressions выполнены.

Повторная сборка после browser PASS совпала по всем45 dist hashes с испытаниями;
повторные lint и offline consistency PASS. Следовательно, применимость сохранённых
результатов к финальным исходникам/сборке подтверждается byte hashes, а не номером2.0.71.
Production JS SHA256: `23a8ef4a4db6d4496df4cbe19fb8372a193e8ded07980a9e2c1253249a12081d`.
При экспорте summary были две синтаксические ошибки одноразовой `node -e` команды;
после исправления экспорт проверил все140 PASS. Прогонов или product-кода ради этого
не повторяли, первичные receipts не меняли. Предсуществующие Node MODULE_TYPELESS
и Starlette/httpx deprecation warnings не исправлялись внутри Q-DRAFT-01.

Финальная сверка обнаружила, что existing `auth-r03.spec.mjs:1081,1086` пишет два
status-list PNG прямо в исторические пути. Новые файлы сохранены отдельно как
`existing-status-views/desktop-status-list.png` (SHA256
`3b2dbf8a8ea717746e8a1161adaada588d56d52840f201afe86bfe0480d7a780`) и
`mobile-status-list.png` (SHA256
`1835fe44b38316577c0bba3aaa8bf4623c9748c340ba48dbc863d551b535b343`).
Только эти два сгенерированных текущим тестом файла восстановлены в прежних путях
из d8ecd81d; read-only diff подтвердил исходные bytes. Никакие чужие изменения или
исторические evidence не заменены, PNG текущего прогона не потеряны. Поведение
existing теста не менялось внутри UI-правки.

## Границы, состояния и следующий шаг

Local branch `codex/ac18-questionnaire-it-inputs`; fresh origin/main61f34aa/2.0.71.
Чужая root branch bc63a8ee и три untracked docs не затронуты.
`branch_push/pr/version_bump/merge/deploy/artifact_publish=false`, CI нового кандидата
NOT_RUN. Новый deploy/readback не выполнялся, последняя проверенная test версия2.0.71.
Рабочая БД и подключения программы не менялись. Все6 временных owned-БД/state
удалены после fsync/readback evidence штатным destroy, без FORCE. Независимый
maintenance SQL на отдельном localhost55438 вернул0 test-БД. После проверки task label
остановлен только `4k-questionnaire-fix-pytest-20261106-c681` PostgreSQL16; `--rm`
удалил его ephemeral слой без постоянного тома. Синтетические test-данные не
восстанавливаются, evidence сохранены. Это не cleanup рабочей БД.

AC18 не запускался. Исторический PREP-DIAG-01 отдельно UNKNOWN;
AC18-TIMEOUT-CLEANUP-DIAG-01 отдельно UNKNOWN и этим нормальным cleanup не закрывается.
Причина конкретного исторического AC18 остаётся UNKNOWN, хотя дефект Q-DRAFT-01 воспроизведён.
Fail-fast постоянного runner и его timeout cleanup в разрешённую UI-правку не включены.

После локальной проверки — передача владельцу. Отдельного решения потребуют
кандидат версии, push/PR/CI/review, затем merge/test; платный AC18 — ещё отдельно
на окончательном выпущенном SHA. Текущая локальная версия2.0.71 не является новым выпуском.
Откат — адресный revert JS-правки и соответствующего rebuilt dist, без миграции данных.

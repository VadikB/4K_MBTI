# AC18: бесплатная диагностика потери черновика анкеты

## Результат

**Подтверждён продуктовый дефект Q-DRAFT-01, исправление НЕ выполнялось.**
Позднее завершение начальной загрузки сохранённых анкет заменяет форму и теряет
ввод, сделанный во время GET. Воспроизведено на настоящем UI/dist2.0.71, серверных
маршрутах и PostgreSQL16. Менялась только задержка пропуска настоящего GET:
`route.continue()`, не synthetic response, resolver или fake Connection.

Четыре diagnostic scenarios завершены, exit0, 2.7min. Это успешная **диагностика**:
три `FAIL_DRAFT_LOSS_REPRODUCED` продукта и один положительный контроль,
не четыре продуктовых PASS и не AC18 PASS.

| Ввод относительно GET | Ширина | Фактический результат продукта |
| --- | ---: | --- |
| Первые3 поля до ответа | 1440 | FAIL: потеряны source_author, organization_name, organization_type |
| Первые3 поля до ответа | 390 | FAIL: потеряны те же3 поля |
| Все12 полей до ответа | 1440 | FAIL: потеряны все12 полей |
| Все12 полей после ответа | 1440 | PASS контроля: значения сохранены, штатное подтверждение |

Во всех отрицательных вариантах старый узел формы отсоединён от DOM;
после ответа значения введённых полей пусты. Пустой required `source_author`
даёт native `valueMissing`: нажатие «Сохранить черновик и предпросмотр» не вызывает
submit/POST, preview/кнопки подтверждения нет, SQL counts остаются baseline.
После **явного повторного заполнения** потерянных полей выполняются реальные
preview201 → confirm200 → GET200, SQL revision.confirmed и совпадение HTTP/SQL JSON.
Это workaround для диагностики, не исправление продукта.

## Причина и границы вывода

Точная наблюдённая цепочка текущего воспроизводителя:

1. `requestOrganizations` уже показал карточку; GET `/questionnaire` ещё pending.
2. Переход в «Данные организации» вызывает `selectAdminOrganizationView` и capture
   ещё пустого draft (`web/js/screens/admin/organizations.js:629`).
3. Пользователь вводит данные. Обработчик input в `web/js/wiring.js:1813`
   вызывает `markAdminOrganizationQuestionnairePreviewStale`; при отсутствии preview
   тот сразу возвращается, не обновляя draft (`organizations.js:671`).
4. GET отвечает200. `loadAdminOrganizations` после await вызывает render без capture
   актуального ввода (`organizations.js:528–541`).
5. `renderAdminOrganizations` пересоздаёт DOM, а `restoreFormDraft` возвращает
   ранее захваченные пустые значения (`organizations.js:209–225,1844,2199`).
6. Native required-validation не допускает submit без автора
   (`organizations.js:2172`). Runner затем ждёт кнопку, которой нет
   (`tests/browser/path29-participant.spec.mjs:160–161`).

Подтверждена причина **этого воспроизводимого UI-дефекта**, а не точная хронология
исторического run. В прежнем AC18 `c39097a0e51c475e9798ff363a18d8ca` совпадают
три потерянных поля, отсутствие preview POST и ожидание confirm; но покадрового
trace/input/DOM timeline в старой выгрузке нет. Его причинная связь с Q-DRAFT-01 —
`NOT_PROVEN_NO_HISTORICAL_TIMELINE`; исходный `root_cause=UNKNOWN` не переписывается.
Старый пакет и его manifest не менялись.

`AC18-TIMEOUT-CLEANUP-DIAG-01` отдельно UNKNOWN: эти scenarios не воспроизводят
900000ms timeout или teardown прерванного теста. Их штатный cleanup не доказывает
исправление того инцидента. `PREP-DIAG-01` отдельно исторический UNKNOWN;
связь с QA/покрытием/admission/repair/LLM этим UI-дефектом не устанавливается.

## Первичные evidence и происхождение

[Каталог безопасных первичных файлов](../evidence/ac18-questionnaire-draft-diagnosis/):
по каждому scenario сохранены run/source hashes, SQL baseline, значения до/после
GET, old-node connectivity, validity, blocked SQL readback, confirmed HTTP/SQL,
timeline, diagnostic-result, cleanup и before/after PNG. Нет state, .env,
паролей, cookies/tokens или raw server logs. Поля компании только синтетические.

| Scenario / directory prefix | Run ID |
| --- | --- |
| first-three-1440-c5c34d0c… | 9270fca76db345ec8e1d66fa95be1557 |
| first-three-390-698fe4cb… | 1dc16dda26ce4bd386346e8b8b34d32d |
| all-fields-1440-b7f2c6a8… | f006150645904f758f91410150c81113 |
| read-complete-control-9cffe656… | ae4c56ef662748828c2fcf4a6fd57688 |

Существующие ADM28/E10.2 seed и вымышленная fixture
`questionnaire-it-synthetic@1` используются только в disposable тестах. Synthetic
Case QA в таком seed не является real human review/допуском пилота. Подмены
upstream plan, product admission, готового профиля/AS или start resolver не включались.
M0–M8, исходные Cases, published программа1.2, prompts/admission/repair не менялись.

Проверенные исходники совпадают с исторической выгрузкой61f34aa побайтово:

- `web/js/screens/admin/organizations.js` SHA256 `4eedb61fc1debf9781a1af6abc36634a5d80a0862fcea452066c635fea240f4a`;
- `web/js/wiring.js` SHA256 `996144312622bf38b57360368ea31885af98c4ce29729b4fe9fff8ef65f3dbd6`.

Run receipts содержат также hashes всех45 текущих dist-файлов, diagnostic driver,
config, fixture и SQL helper; offline verifier сверяет их с рабочим деревом.

## Проверки

Из worktree `worktrees/ac18-questionnaire-it-inputs`:

```sh
STAND_ADMIN_URL=postgresql://postgres@127.0.0.1:55438/postgres \
BROWSER_PYTHON=/Users/vadim_bogachev/Developer/4K/.venv/bin/python \
P4K_EVIDENCE_DIRECTORY=.test-stand/questionnaire-draft-loss-20261106 \
/Users/vadim_bogachev/Developer/4K/node_modules/.bin/playwright test \
  --config tests/browser/questionnaire-draft-loss.config.mjs

node tests/questionnaire_draft_diagnostic_verify.mjs
```

Первая команда: **4 diagnostic scenarios completed**, exit0; продуктовые статусы
выше. Отдельный config не включает воспроизводитель в обычный `.spec.mjs` acceptance
и не превращает известный дефект в требование успешной работы продукта.
`node --check` driver/config/verifier и `git diff --check` применимы;
все выполнены **PASS**, exit0. Offline verifier: **PASS43 primary files /4 cases**,
3 product defect reproductions,1 control PASS,4 cleanup PASS, provider operations0,
`product_fixed=false`, `AC18=BLOCKED_NOT_REPEATED`.
SHA256 дерева43 case-files (отсортированные `[relative_path, byte_sha256]`, compact JSON):
`f0d742e438b7c642237c25675ec1e523ef3d6c3c2736b7e616fe7da9d480661c`.
`git diff --exit-code e9330ed6 -- Api web scripts assessment_definitions` → exit0,
продуктовые исходники/runner/предметные источники не изменены.

Проверки8 frontend questionnaire /11 Python questionnaire sources из e9330ed6
переиспользуются для неизменённого продукта/fixture/SQL helper. Это не покрытие новой
диагностики; она проверена отдельными4 actual HTTP/PostgreSQL scenarios.
Полный frontend/backend и CI не запускались: исправления продукта и кандидата
выпуска в этом шаге нет. Линковка/синтаксис/адресная проверка новых tests/docs
не заменяются историческим CI.

В четырёх SQL baseline profiles=2 (предсозданные участники другой synthetic org),
после подтверждения profiles=2. Assignments/preparation/Cycle/AS/turns0→0,
questionnaire revisions0→1. До refill при invalid форме — все counts без изменений.
Provider mode disabled, gateway0, нет prepare/start запросов; LLM0 и внешних писем нет.

## Очистка и состояния

Все4 exact-owned БД штатно удалены через `test_stand.py destroy` после fsync/readback
evidence, owner_verified/database_absent/state_absent=true, force=false.
Независимый maintenance SQL вернул0 test-БД. Затем после проверки task label
остановлен только созданный контейнер
`4k-questionnaire-draft-pytest-20261106-bf72` / PostgreSQL16 / localhost55438;
постоянного тома нет, его ephemeral слой удалён `--rm`. Synthetic test-данные
после cleanup не восстанавливаются, безопасные evidence сохранены.

- Local branch: `codex/ac18-questionnaire-it-inputs`, base main61f34aa, предыдущий
  рабочий commit e9330ed6; текущий diagnostic diff — только tests/docs/evidence.
- Fresh `origin/main`: `61f34aa2151a4f9364eac28bf33895d10f91d50b`, 2.0.71.
- CI текущего diagnostic diff: **NOT_RUN**, push/PR нет. CI выпуска2.0.71 закрыт ранее.
- Deploy: новых действий нет; последняя проверенная версия test —61f34aa/2.0.71,
  сегодня живое deployment readback не повторялось.
- Чужая корневая ветка bc63a8ee и три untracked docs сохранены.

## Предлагаемая узкая правка — требуется отдельный допуск

Сохранять актуальный scoped draft перед асинхронной заменой карточки, не возвращать
устаревший пустой draft поверх живого ввода. Сохранить identity epoch/user/org/
assessment guards, очистку недоступных данных, корректную смену scope и восстановление
confirmed revision. Не добавлять fallback источников, не менять схемы/API/admission.
Существующая простая задержка/повторное fill в runner не устраняет этот UI-дефект.

После допуска: локальная UI-правка, регрессия ожидаемого **сохранения** всех полей
при позднем GET и проверки identity/org/program transitions, обычное подтверждение,
build/dist, lint, frontend и применимые HTTP/PostgreSQL проверки. Дополнительно
можно отдельно согласовать fail-fast runner, чтобы до ожидания confirm сохранялись
значения/validity/preview status вместо ожидания общего timeout.
Никакого платного AC18, version bump, push/PR/merge/deploy без нового прямого разрешения.
Откат diagnostic шага: адресный revert его tests/docs/evidence; схемы/исторические
данные не мигрировались, постоянная БД не затронута.

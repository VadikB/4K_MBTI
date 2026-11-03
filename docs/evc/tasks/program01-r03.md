# PROGRAM01 R03: выпуск программы и исходный путь участника

## Результат и область

Для согласованной immutable ProgramDefinition «Пилот 4К · 9 кейсов» установлен
фактический release/connection state, найден и устранён первый доказанный блокер
исходного маршрута `superadmin → org admin → participant`. Повторная готовность
продолжает маршрут без повторного ввода уже подтверждённых ответов; запуск оценки
остаётся отдельным явным действием участника.

Включено: структурный readback ProgramDefinition, connection, questionnaire,
assignment, binding и readiness; штатный выпуск уже согласованной версии при его
фактическом отсутствии; регрессии карточки участника и знакомства.

Не входят: ослабление M6–M8/start gate, переименование published rows и snapshots,
создание конструктора программ, удаление старых версий, рассылка приглашений,
изменение реальных пользователей без отдельной необходимости, deploy.

## Источники и решения

- Основание: audit package `P4K_PROGRAM01_AUDIT_2.0.47_2026-11-02`,
  `START.txt`, `REMAINING_TASKS.txt` R03 и уточнение M02/M03.
- Исходный base: `main@7d8e2717fb5b0a26394106bfc7d377807c7dfffa` после
  squash merge PR #151. Перед PR ветка перебазирована на актуальный
  `origin/main@eafb0f9` (PR #152–154 включены).
- Прочитано: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, Change 01 README/manifest, ADR-002,
  `docs/evc/change01-traceability.md`, release/binding scripts и применимые
  ProgramDefinition/acquaintance/readiness задачи и тесты.
- Программа, подключение организации и назначение роли участнику — разные действия.
- Published ProgramDefinition и исторические snapshots неизменяемы; merge приложения
  не является публикацией предметного артефакта.
- M1 v1.4 остаётся FROZEN / CURRENT=NO; задача не присваивает новый статус M1–M8.
- Стоп-условие: публикация артефакта, изменение живых данных, приглашение или deploy
  требуют отдельного доказанного основания и соответствующего флага владельца.

## Прослеживаемость

R03 / D03 / PROGRAM01-01/03/04 / AC03/04/07/10/12..16 → immutable
ProgramDefinition + exact organization connection → exact questionnaire revision,
assignment, binding и readiness → participant journey/start gate → structural
readback, PostgreSQL/HTTP/browser acceptance и deployed SHA как отдельный факт.

## План и состояние

- Завершено: чистая ветка и worktree созданы от актуального `main`; источники и
  действующие release/binding entry points прочитаны. Публичный test health
  `ready`, `/users/version` сообщает `2.0.51`; GitHub CI run `#741` подтверждает
  успешный `deploy-test` commit `7d8e271`.
- Завершено: read-only снимок фактического состояния test organization без
  переноса персональных данных, локализация первого неуспешного перехода,
  адресное исправление и регрессия.
- Следующий шаг: PR, обязательный CI и test acceptance после deploy.
- Ветка: `codex/program01-r03`.
- Блокер живого readback: в доступном browser-контексте нет авторизованной test
  session был снят обычным входом владельца. Read-only UI-аудит выполнен в
  superadmin-контексте только по безопасным структурным полям.

### Test readback 2026-11-02

- Контур: health `ready`, версия приложения `2.0.51`, deployed SHA `7d8e271`.
- Published ProgramDefinition `«Пилот 4К · 9 кейсов» · 1.1` присутствует в
  штатном списке подключения; форма принимает точный definition id и допускает
  команду подключения. Старое определение `1.0` сохранено отдельно.
- Выбранная тестовая организация не имеет current ProgramDefinition connection.
  Это первый неуспешный переход цепочки; роль в exact scope поэтому недоступна.
- В текущем legacy scope анкета не подтверждена. Отдельная readiness-проекция
  показывает ранние сведения и контекст готовыми, участников — требующими
  заполнения, подготовку — не запущенной. Сохранённого confirmation/preview в
  открытом разделе нет.
- ProgramDefinition `1.1` была выбрана только локально для сверки и возвращена в
  исходное placeholder-состояние; `Подключить` не нажималась, серверные данные не
  изменялись.

### Подключение после решения владельца

- Владелец явно подтвердил подключение ProgramDefinition `1.1` к выбранной test
  organization. Штатная UI-команда выполнена один раз.
- Command result: `Опубликованная версия программы подключена к организации`.
  Точный readback после reload: программа `Пилот 4К · 9 кейсов · 1.1`, роль
  `Специалист / эксперт`, assignment ref `specialist-pilot`.
- Письма, назначения, подготовка и запуск оценки не выполнялись.
- Следующий первый блокер: в exact scope `specialist-pilot` нет подтверждённой
  questionnaire revision. Форма видит сохранённое описание прежней карточки и
  предлагает его перенести без повторного ввода, но обязательная атрибуция
  `source_author` отсутствует. Значение источника нельзя угадывать; требуется
  решение владельца до preview/confirmation.
- После решения владельца `source_author` установлен как `Руководитель проектов
  в области внедрения корпоративного ПО`, прежнее описание перенесено штатной
  кнопкой и создан draft preview revision `26` в точном scope `specialist-pilot`.
- Сервер вернул `Нужно исправить анкету`; confirm-action отсутствует, поэтому
  публикация не выполнялась. По действующему `EARLY_REQUIRED` отсутствуют
  обязательные предметные сведения: название/тип/отрасль организации, цель и
  использование результатов, организатор и ответственный контакт, уровень
  реалистичности кейсов и правила использования названия. Эти значения нельзя
  выводить из ProgramDefinition или придумывать; требуется ввод владельца.
- Владелец явно разрешил заполнить анкету test organization согласованными
  синтетическими данными без реальных персональных данных и указал источник
  `Синтетические тестовые данные`.
- Создан новый preview revision `27` в exact scope `specialist-pilot`.
  Server preview: `Готово к подтверждению`; confirm-action доступен, participant
  projection содержит девять ожидаемых полей. Получатели перед confirm:
  обязательный `participant=true`, `organization_admin=false`.
- Revision `27` подтверждена штатной UI-командой. Readback: ProgramDefinition
  `Пилот 4К · 9 кейсов · 1.1`, роль `Специалист / эксперт`, анкета
  `подтверждена`; UI сообщает `Можно назначать`. Письма, назначение, подготовка и
  запуск оценки не выполнялись.
- После команды владельца выбран один существующий test participant и выполнено
  точное batch assignment без отправки приглашения. Роль формы —
  `Специалист / эксперт`, assignment ref — `specialist-pilot`.
- Command result: `Назначена: 1. Уже была назначена: 0. Не назначена: 0.`
  После полного reload программа и scope сохранены, participant stage —
  `Оценка назначена`, штатная cancel-action присутствует. Подготовка отключена до
  выполнения participant readiness; письмо и start не выполнялись.
- Следующий шаг требует отдельной participant session: текущая активная session
  принадлежит superadmin-контексту и не доказывает исходный participant journey.

### Смена границы 2026-11-03

- Владелец явно остановил дальнейшую проверку организации `lidum_pro`.
- Созданные ранее immutable/current связи, questionnaire revision `27` и
  assignments не удаляются и не изменяются; письма и start не выполняются.
- Новая ссылка с отдельным `cycle_id` перенаправилась на `auth-complete` со
  стадией подготовки и относится к иному наблюдаемому административному
  контексту (`e102_synthetic`, ProgramDefinition `1.0`). Она не засчитывается как
  participant acceptance `lidum_pro` и должна рассматриваться отдельной задачей
  либо новым целевым контекстом после решения владельца.
- Владелец выбрал новым целевым контекстом test organization `test8`.
- Read-only superadmin readback: ProgramDefinition `Пилот 4К · 9 кейсов · 1.1`,
  assignment ref `specialist-pilot`, роль `Специалист / эксперт`, questionnaire
  `подтверждена`. Для указанного test participant административная проекция
  показывает активный Cycle / стадию `Проходит оценку`.
- Присланный interview URL был открыт в управляемой superadmin session и
  перенаправился на `auth-complete`. Адресный GET `/users/22/journey-state`
  вернул `Нет доступа к состоянию другого пользователя`, доказав, что эта
  browser session не принадлежит целевому participant. Поэтому redirect не
  считается participant acceptance и не доказывает дефект проекций.
- Для продолжения требуется доступная агенту вкладка, авторизованная именно как
  целевой test participant; секреты/пароль не запрашиваются и не читаются.
- Владелец выполнил вход целевым test participant. Read-only
  `/users/22/journey-state` в той же cookie-session подтвердил: профиль и
  onboarding завершены, exact scope `specialist-pilot` готов, Cycle активен,
  `next_action=resume_assessment`. Персональные поля и ответы в отчёт не
  переносятся.
- Публичный test уже сообщает версию приложения `2.0.54`; deployed SHA этой
  версии в рамках текущего readback ещё не зафиксирован.
- Воспроизведён первый дефект participant route: после успешного входа и после
  reload UI возвращается к email form с общей ошибкой актуального этапа. Причина
  локализована адресным read-only GET: Cycle runtime отвечает `409` /
  `M7_RETURN_EXPLICIT_CONTINUE_REQUIRED`, как и требует P03 после признанного
  отсутствия. `main.js` и fresh-login path в `wiring.js` выполняют лишний
  runtime preflight до открытия interview; из-за этого штатная return-card с
  явной кнопкой `Продолжить` не успевает загрузиться.
- Решение: удалить только дублирующий preflight. `openInterview()` уже вызывает
  `loadProductRuntime()`, который по контракту сначала читает `return-state`,
  показывает return-card и не читает AS runtime до явного Continue. Таймер и
  оценка автоматически не возобновляются; API и серверные данные не меняются.

## Действия выпуска

- `branch_push=true`
- `pr=true`
- `merge=false`
- `deploy=false`
- `version_bump=false`
- `artifact_publish=false`

Флаги меняются только явно после локальной проверки. В частности, публикация
ProgramDefinition не следует из merge кода.

## Ограничения и риски

- Публичный API и существующие данные должны сохраняться.
- В отчёт, fixtures и логи не копируются email, ФИО, токены, ответы и иные данные
  исходного участника; используются только безопасные ID/status/version/checksum.
- Реальные письма и LLM-вызовы не выполняются.
- Нельзя объявлять роль единственной причиной до сопоставления всей цепочки.

## Критерии приёмки

- [ ] Зафиксирован structural readback ProgramDefinition, connection, questionnaire,
  assignment, binding и readiness без персональных данных.
- [ ] Найден первый неуспешный переход и конкретная первичная причина.
- [ ] Согласованная версия программы опубликована штатно или доказано, что она уже
  опубликована; старые версии и snapshots не изменены.
- [ ] Org admin назначает специалиста в точный scope; readback сохраняется после reload.
- [ ] Карточка участника и знакомство показывают один этап; подтверждённые ответы
  повторно не запрашиваются.
- [ ] Таймер/прохождение запускаются только явным штатным действием участника.
- [ ] M6–M8, admission, context и start gate не ослаблены.

## План проверки

- Python compile и адресные unit/frontend tests затронутого слоя.
- HTTP + изолированная PostgreSQL для exact scope, сохранения/reload и start gate.
- Browser: `superadmin → org admin → participant`, retry readiness, reload и явный start.
- Полные backend/frontend, lint/build, соответствие `web/dist`, `git diff --check`.
- GitHub CI перед merge; deployed SHA и footer version фиксируются раздельно.

### Выполнено для participant return fix

- `node --test tests/frontend/p03-return-presence.test.mjs tests/frontend/auth-ux.test.mjs`
  — PASS, 9/9.
- `npm run build:web` — PASS; обновлён tracked `web/dist/main.js`.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "P03 (return card|fresh login)" --workers=1`
  — PASS, 2/2.
- `npx playwright test tests/browser/auth-r03.spec.mjs --workers=1` — PASS,
  80/80 до rebase и 80/80 после rebase на `origin/main@eafb0f9`.
- `git diff --check` — PASS.
- Test acceptance исправления — NOT_RUN до merge/deploy; текущий deployed
  `2.0.54` закономерно сохраняет воспроизведённый дефект.
- Draft PR: `#155`. Первый CI event был создан GitHub как Open до немедленного
  перевода в Draft, поэтому release guard корректно потребовал новую версию.
  Повтор job сохранил исходный event payload и повторил тот же результат;
  следующий `synchronize` запускается уже с `draft=true`, где REL-VERSION-02
  откладывает version bump до Ready for review.

## Откат

Код откатывается revert PR. Опубликованные ProgramDefinition, connection,
assignments и snapshots не удаляются и не переписываются; операционный откат
переключает организацию на ранее допустимую immutable версию только штатной
операцией с отдельным решением владельца.

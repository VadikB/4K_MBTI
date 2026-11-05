# PATH-PILOT-02 — отчёт локальной реализации T1

05.11.2026. Задача: [PATH-PILOT-02](../tasks/path-pilot-start-admission.md).
Это локальная реализация и бесплатные проверки, **не выпуск и не PATH PASS**.
Проверенный кандидат реализации: `199e7c351a2d985c0173f845574c4de5dc80775a`
(основной код679cc2f + исправление ревью). После него меняются только STATE/docs/evidence;
код, тесты, артефакт и web/dist побайтово прежние. Точный handoff SHA — HEAD
документальной передачи, отдельно указан в Handoff.json доступного пакета.

## Результат и прослеживаемость

| Требование | Реализация | Проверка / ограничение |
| --- | --- | --- |
| Сохранить диагностику относительно de3b831 | Неизменяемые commits до2a9ef94; старый review и ZIP сохранены | Git diff подтверждает неизменность исторических source/Case/prompt/QA и M0–M8 |
| Различать полный M2 и пилот | draft `specialist_pilot_admission/0.1`, exact proposal и отдельная P/M запись | snapshot mutations; 61 полный /39 план /22 вне /55 условий |
| Не считать любой LIMITED допуском | Новый ProgramDefinition opt-in; frozen plan binding; shared server start readiness | Реальный SQL predicate, отказ legacy LIMITED, mutations sources/lineage/time/admission |
| Одинаковые server/UI/admin/runner условия | `m7_start_readiness/1`, повтор в start transaction, безопасные причины | HTTP401/409/201; browser готовность/ожидание/ошибки; receipt regressions |
| Допущенная конечная AS | PM-03 правила не меняются; candidate/Case/profile/operation/Session/AS связи и стадии проверяются | PASS_WITH_WARNINGS + admitted=true допускается; FAIL/INCOMPLETE/false запрещены |
| Явный старт, время и отсутствие ответов | Существующий PM-04 start; scoped7200/259200, тот же AS, idempotency | SQL READ ONLY; two concurrent starts; 0 ответов, один collecting interval |
| Не раскрывать скрытые условия | Participant plan projection; public program refs, не полный snapshot | Unit/HTTP privacy, проверка не изменяет internal snapshot |
| Не менять рабочую БД / не расходовать LLM | Только owned loopback PostgreSQL16 и подставные stage records | Новый provider calls=0; реальные ключи/`.env` не использовались |

Точная связь источников и PM/контрактов: [технический контракт](../../architecture/pilot-plan-start-admission-contract.md).
M1v1.4 FROZEN/CURRENT=NO; Change01 и выбранный SourceSet не переприсвоены.
P1–P3/M1–M4 приняты владельцем по exact v0.1; T1 принят последующим «принимаем идем дальше».
Историческое PENDING/NONE в исходном review не переписывается и не служит runtime допуском.

## Артефакт и границы включения

Источник: `assessment_definitions/planning/specialist_pilot_admission/v0.1/manifest.json`.
Raw SHA `c76b118e605d7479f85671f52695f2a189537d03dcc6c69443bfb2f9d1392d66`;
offline snapshot `daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce`.
Принятый proposal payload `883c025cfa0ea43ad17922bc4818f05a0aaaa62bf02817690a3d07f171cfec06`.
Raw owner receipt `3e1293c6978fc042b2461d301cfc78f3b7995445a83599bc583f5f4cf808a04b`;
его canonical content checksum `3553c7c41f411201742ec6b4d53967ab5c2f114c0d70bb5bdfff395d996e693c`.
Разные хеши — разные объекты/канонизации, не требование их равенства.

Manifest — draft offline source; только будущая новая immutable опубликованная
ProgramDefinition может включить snapshot. `specialist_pilot@1.1`, catalog1.0 и
все девять Case/QA источников не изменены. Текущий published-pilot fixture1.1
сохранён: без нового independently checked source receipt новый допуск не получает.
Новых таблиц/колонок/миграции нет. Предметные значения в JSON/принятом proposal,
не в Python/JS; новых скрытых defaults/артефактного долга не введено.

## Проверки и их применимость

На199e7c3: backend835 PASS/331deselected, HTTP108 PASS/12deselected,
**полный integration217 PASS/949deselected**, browser98 PASS. Адресные SQL18 PASS.
Frontend140 PASS, receipt46 PASS, persistence1 PASS, lint/build/dist equality PASS
переиспользуются с679cc2f: соответствующие consumer files и web tree не менялись,
проверено Git diff. Известные предупреждения Starlette/httpx и Node не скрыты.
Полный integration на промежуточном679cc2f:215PASS/1FAIL — legacy10.5/M4 fixture ожидал start неподтверждённого LIMITED.
Реальный409 сохранён как отдельный assert; два M4 component старта теперь явно
SYNTHETIC upstream permission.
Команды/параметры: [verification.json](../evidence/path-pilot-start-admission/verification.json).
Первичные логи/JUnit, server readback и export/cleanup receipts сохранены рядом
и входят в handoff package. Результаты проверены не по наличию файла, а по exit0,
числу tests и нулю failures/errors/skips, точным AS/checksum refs и нулю ответов.
На ревью исправлен воспроизведённый lock timeout на DROP TRIGGER в connect при
открытом readback: normal connection больше не запускает schema DDL, порядок
connection→timing общий со start. Новая регрессия: первичный FAIL воспроизведён,
исправленный адресный и полный наборы PASS на199e7c3.

Неудачные попытки не скрыты: первая full backend832PASS/3FAIL из-за ошибочно
подставленного `DEEPSEEK_BASE_URL=loopback/disabled`, несовместимого с frozen
provider contract даже для fake Gateway. Повтор с пустыми ключами и стандартным
endpoint835PASS; продуктовый provider contract не менялся. Первый integration
прерван с exit2:61PASS/8FAIL из-за отсутствующего maintenance URL и того же
endpoint override. Параметры запуска исправлены, защитные проверки не ослаблены.
Raw failed traceback с repr окружения не включается в выдаваемый пакет; сохраняются
безопасное описание причины и результаты корректного повтора.

Старые S10 и10.5/M4 component fixtures явно подставляют upstream start permission; они не
доказывают admission. Новый SQL suite восстанавливает реальный predicate. Принятие
плана и LLM generation/tester/challenger в нём — **SYNTHETIC boundary fixtures**,
не human review и не результат платного PATH. Исходное QA девяти Cases переиспользуется,
новое human review не выдумывается. PREP-DIAG-01 отдельно UNKNOWN; ни ошибки harness,
ни LIMITED, ни новый отказ AS не объявлены его причиной.

## Состояние и следующий шаг

| Контур | Состояние |
| --- | --- |
| Рабочая ветка | codex/path-pilot-start-admission, локальная; base2a9ef94, tested code199e7c3, docs/evidence handoff отдельно |
| Диагностическая ветка | codex/path-plan-diagnostics сохранена на2a9ef94 |
| CI | NOT_RUN для нового кандидата; обязательные checks перед merge сохраняются |
| main / origin-main | Локальные refs2dc98c6/2.0.64; свежая удалённая проверка не выполнялась |
| Развёртывание test | Последний известный2dc98c6/2.0.64; новый deploy не выполнялся, свежий readback NOT_RUN |
| Постоянная БД | Не читалась/не изменялась; очистка только owned test data |

Сверка **схемы** с серверным `/home/vadim_bogachev/projects/Agent4K-Test/.env`
разрешена только read-only. По последнему указанию владельца она отложена до
стабилизации всех изменений, перед возможным main. Проверять metadata tables/
columns/types/constraints/indexes/triggers без bootstrap/ensure/import/seed и без
чтения ответов/секретов. Несоответствие требует точного плана, не скрытой миграции.
Активация программы не разрешена.

Выпуск R1 требует отдельного разрешения push/PR, согласованного нового номера app,
обязательного CI/review, публикации новой ProgramDefinition/точных org/actor refs,
scoped timing/readback, нового source receipt и совместимого recovery для v2 Cycles.
Новый платный PATH требует отдельного разрешения после этого; сейчас не запускался.
Main автоматически не получает изменения профиля/runner/новый gate из этой ветки.
Следующая задача должна брать точный handoff commit, не просто текущий main.

## Безопасность и откат

Все stop-условия для локального T1 закрыты принятым решением либо неприменимы:
новые нормы/PM-владение не вводятся; additive API/JSON описаны; destructive migration,
передача чувствительных данных и смена rollout boundary отсутствуют. Для R1 допуск
пока отсутствует, зависимые действия не исполняются. Управляющие документы не менялись.

До публикации откат — возврат исходного кода/черновика без изменения БД. После
будущей активации отключить новые opt-in назначения, но сохранить совместимый
reader и начатые snapshots; слепой downgrade к2.0.64 не заявляется безопасным.
Подробности в контракте. Все release flags=false; paid_llm_run=false;
permanent_database_write=false. Baseline и человеческая приёмка этой реализации
самоотчётом агента не объявляются.

Owned контейнер33e6f86… штатно остановлен/AutoRemove; tmpfs synthetic SQL данные
удалены и не восстанавливаются (воспроизводятся fixtures). Перед удалением сохранены
достаточные readbacks/проверки и отрицательная диагностика; их SHA совпадают после
cleanup. [Cleanup receipt](../evidence/path-pilot-start-admission/cleanup.json).
Временная собственная .venv-ссылка удалена, общий root .venv сохранён. Другие БД,
исторические screenshots и пользовательские файлы не удалялись.

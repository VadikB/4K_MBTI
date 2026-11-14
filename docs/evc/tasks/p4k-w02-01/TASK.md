# P4K-W02-01 — знакомство и действия участника

Основание: прямое поручение Дмитрия 14.11.2026 «задание на исполнение. Запускай»
с двумя приложенными файлами редакции 1.0 (побайтовые копии в gzip рядом, SHA-256 в evidence/input-sha256.json). Файлы задают требования;
полномочие исполнения происходит от сообщения владельца. Исполнитель — Codex.

Результат: путь знакомства W02, единая форма трёх ответов до подтверждения,
сообщение о неточности на сведениях и сводке, read-only история. Один PR.
Архитектурный адрес: UI пути участника → PM-02 / LU контекста; контракты consent,
answers и issues прежние. Контекст не Evidence; источник вопросов — briefing,
`participant-context-corporate@1.0`, stable keys и answer_1–3 не меняются.
Не входят: подготовка/старт следующей карточки, смена роли, организационная анкета,
профилирование, API/БД/миграции, опубликованные артефакты и snapshots.

База: fresh origin/main `07166475b478c843243102c748d51f8564b7cec0`, 2.1.5.
Worktree `p4k-w02-01`, ветка `codex/p4k-w02-01`. Исходный checkout
`codex/remain-02` и его untracked docs сохранены. PR #220 другой задачи не включён.

Прочитаны: AGENTS, README, CONTRIBUTING; EVC workflow, verification-matrix,
review-checklist, artifact-recipe, task-template, decision-register; architecture
1.0/context, registry, Change01 README, SourceSet manifest; M1 v1.4 §M1.4,
M4.Context v1.0 §§M4.2–4 (оригинал DOCX); UX-CTX01 task, соответствующие
Api/acquaintance.py, questionnaire_sources.py, onboarding UI и tests.
Применимость: Product Architecture v1.0 + Change01 WORKING, M1 v1.4 FROZEN /
CURRENT=NO, M4 Context v1.0 FROZEN. Глоссарий W011–16 применяется в достаточном
изложении входа; повторная загрузка не нужна. PILOT-120/ARCH-A05 проверены по
первичной карточке arch-a05-coverage-pilot.md; числовые демонстрации не переносятся.
ADR-003 просмотрен: назначенная immutable роль сохраняется. Исторические полномочия
CODEX-WORKFLOW-02/PATH/F02 к этой задаче не относятся.

Стоп-условия (все нет): новый предметный смысл, публичный контракт, миграция,
конфликт источников, новый артефактный контур, права/чувствительные данные,
неопределённый откат, выход за scope. Изменяются UI и адресные fixtures.
Принятые тексты W02 — UI-пояснения, не новые нормы оценки. Старые briefing
с произвольными вопросами сохраняют исходные подписи. Динамические сведения,
роль и серверный текст/версия согласия сохраняют свои источники.

Флаги этапа по прямому запуску приложенного задания владельцем:
branch_push=true, pr=true, version_bump=true (PATCH от актуального main);
merge=false, deploy=false, artifact_publish=false. Разрешены собственные commits,
push ветки, один Ready PR, связанные fixes, наблюдение обязательного CI.
Граница окончания: готовый PR с CI точного head, затем остановка. Human review
отдельно; TEST не разворачивается этой задачей. Номер вычисляется штатно перед
`npm run ready:prepare -- --candidate X.Y.Z`.

План: 1) разведка (завершена); 2) UI/общие формы (активен); 3) адресные browser
и frontend, проверка layout 1440×1024/390×844/320; 4) PATCH + локальный минимум;
5) commit/push/PR/обязательный CI, evidence и передача.
AC01–05 соответствуют исходной карточке, результаты — CHECKS.md.
Проверки: diff-check/lint/build/frontend; browser с реальным frontend и controlled
contract responses, один worker/retries=0, общий deadline 600s/no-progress90s.
Новые регрессии только для общей формы/ошибок/scope; существующие late-readback
и scoped-draft переиспользуются. Backend не изменяется; права issues подтверждены
существующими HTTP/integration регрессиями в mandatory CI. LLM=0, письма=0.

Риски: только UI/совместимость fixtures; CSS ограничен onboarding-panel. Общие
стили проверяются computed styles. Откат: revert собственного PR, данные и snapshots
сохраняются. Сайт прототипа недоступен (web open и DNS curl); локальный HTML не
найден. Используется достаточный текстовый эталон, пиксельная сверка HTML ограничена.

После созданияPR221 main продвинулся до b0bf7a4 (PR220/2.1.6).
Финальный состав основан на этом свежемmain, PATCH-кандидат2.1.7 подготовлен тем же
штатным ready:prepare; повторный bump выпущенной версии не выполнялся. Чужой
REMAIN06 сохранён целиком; локальный frontend теперь324PASS, browser11PASS.


## ADD01 — визуальная доводка, 14.11.2026

Основание исполнения: прямое сообщение владельца «посмотри замечания и возьми
в работу». ADD01 rev1.0 — источник требований; его байтовая копия и SHA256 рядом.
Продолжается прежний результат/PR221/ветка, candidate2.1.7 сохраняется.
Флаги branch_push/pr=true по продолжающемуся разрешённому этапу;
merge/deploy/artifact_publish=false. Новый bump не требуется при прежней базе.
Исходный HEAD47d11f72a9c54c9a8a302fb96ba474a7a632f708;
fresh origin/main/PRbase b0bf7a4e8e4f0fe70c400525a373b9822229dfdc.
Источники: ADD01 пункты1–8, W02_REFERENCE rev1.0/v5, действующие AGENTS,
CONTRIBUTING, EVC workflow/matrix/review, decision-register, context/Change01.
Методологический контекст основной карточки переиспользован без изменения области.
Восемь стоп-условий — нет: только представление, API/смысл/данные прежние.
Пробел: опубликованный HTML вновь недоступен через web.open, автономного HTML
в архитектурном каталоге нет. Численные значения берутся из ADD01/REFERENCE;
на телефоне composer принят в колонку с полем и кнопкой полной ширины, как
адаптивные действия W02. Точное сравнение с HTML не заявляется.
План: восемь визуальных исправлений → локальный минимум и затронутые fixtures →
один снимок summary1440×1024 → тот же PR/обязательный CI точного нового head.
Новых тестов ради CSS и полной повторной матрицы не добавляется. Existing W02
сценарий запускается только1440px; REMAIN05 имеет новый доступный текст кнопки;
PATH29 имеет новые ожидания composer/отсутствия стрелки. Реальные LLM/письма=0.
Приёмка: по принятому дополнению ручная проверка длинного ответа, формы и телефона
отложена до main/TEST; человеческое review и самостоятельный допуск merge сохраняются.
Откат — revert собственных ADD01-коммитов/PR штатным процессом.


### Уточнение после доступа к HTML W02 v5

Владелец прямо разрешил повторный вход в ChatGPT и затем Google sign-in.
IAB открыл эталон; прежний пробел доступа закрыт. Sitesread подтверждаетversion5,
DOM/computed styles сводки просмотрены адресно1440/390 (не новая матрица).
Первичное чтение — evidence/add01/reference-dom-styles.json. Встроенные шрифты,
секреты и учётные данные не копировались. СкачиваниеHTML превысилоtimeout;
дальше использован уже доступный DOM, повтор скачивания не выполнялся.
Дельта относительно43d16e2:mobilecomposer padding/gap12, label14/21,
textarea padding11/12, textaction44px/padding10, dot7desktop/5mobile,
mobile section12/16/actionsgap12. Это уточнение тех же8пунктов, без API/JSfix.
Кнопки48px сохранены по явному текстовому REFERENCE; HTML secondary50px включает
border, его механическое копирование нарушило бы явную высоту48px.
Перед controlledrun `w02-add01-html-final` — своих PID/containers/DB нет;
исходные foreignlisteners прежние. Тот же finiteprofile600s/90s/1worker/0retries,
noLLM/noletters и прежний runner/commands; W02only1440px +REMAIN05.
Перед адреснымPATH29 — новыйcluster `.test-stand/w02-pg-add01-html`,
PG55493/backend18859, рольstand_owner, синтетическая product4k_pytest DB.
Старт python3 /tmp/p4k-w02-add01-html-path.py; status/stop с новымclusterpath
штатные, ownedgroups иPID до использования фиксируются в evidence/add01/path-run.json.
Повтор обусловлен полученным новым исходным HTML и конкретной CSSдельтой.
Текущий CI43d16e2 относится к прежнемуCSS; послеpush новыйhead проходит весьCI.

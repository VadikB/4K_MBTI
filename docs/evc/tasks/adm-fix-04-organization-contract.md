# ADM-FIX-04 — единое подтверждение данных организации

## Результат и область

Рабочая ветка `codex/adm-fix-04-organization-contract` первоначально от `6645859935d099b352e3cf2f57fc23237c70efde` (`main`, 2.1.44), затем перенесена на `4f037ba5ee04d9187b64e4a354785b951e13cd39` (`main`, 2.1.45) и актуальный `052a9be5f1704fcc67d01cf0f6f7063cd638a52f` (ASUX-04). Обычный администратор больше не меняет код/имя закреплённой организации через старый POST/PATCH. Суперадминистратор по-прежнему создаёт организацию, а остальные поля PATCH остаются доступны по прежним правам. Имя обычного администратора меняется транзакционным подтверждением анкеты Admin 02 вместе с новой версией OrganizationContext. Два поля C17 проверяются сервером при CSV, `product_form` и `external_form`; неизвестное значение сохраняется в недействительном черновике, но не публикуется. Подтверждение старого черновика заново применяет текущую политику.

Не входят: удаление импорта 0.1, перенос `organizations.profile`, миграция опубликованных контекстов, выпуск на TEST, изменение CURRENT/методологии или исторических снимков. Один PR представляет один результат. Визуальную приёмку проводит владелец.

## Источники, решения и границы

- ТЗ: `/Users/vadim_bogachev/Downloads/P4K_ADM_FIX_04_Organization_Contract_2026-11-20.md`, SHA256 `389c231bf2f92ac36f8f7982848c6a29b74c56880a93bbb83d60ec139886d2c1`. Блок «Промпт запуска» — требование к результату, не прямой допуск публикации.
- Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `task-template.md`, `review-checklist.md`, архитектурные `context.md` / `registry.md`, Change 01 README и task manifest, ADR-002 C-23/24, `change01-traceability.md`, Admin 02, M4.Context v1.0 §§4.1/4.4–4.5 (зеркало `m4_context_source.md`, SHA256 `9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1`), связанные код/тесты. M4 FROZEN / CURRENT=NO; Change 01 WORKING, публикация методологии не выполняется.
- M4 задаёт обязательность уровня реальности и правил имени, но не закрытый список значений. Утверждённые варианты Admin 02 находятся в `assessment_definitions/contexts/competencies_4k/1.1/admin_context_choices.json` v1.0, SHA256 `b76cb4b804de2916b074f4070858f7e4fb53e87328ad03191c2b21ace7feaf8a`.
- Исторические «обобщённый» и «не использовать название организации» встречались только в `example.synthetic.csv`; fixture не является runtime-политикой. Владелец **прямо подтвердил оба эквивалента в чате 20.11.2026** для отдельного версионированного артефакта. Добавлен `assessment_definitions/contexts/competencies_4k/admin_choice_compatibility/1.0/choices.json` v1.0, статус `approved_for_admin_confirmation`, SHA256 `84e7f8f3e44626d5783d325b426dc7e7f92be043d651d986a085cb1f04e5dad0`, с собственным manifest и ссылкой на утверждённые варианты 1.0. Старый пакет не изменён.
- Правило M4/Admin 02 → PM-02, LU-02.1/02.4/02.7 → `questionnaire_response_revisions` и `assessment_organization_context_versions.source_manifest_json` → `Api/questionnaire_sources.py`/`Api/routes.py`/админский UI → unit, owned-HTTP/PostgreSQL, browser. Подтверждение и новый контекст транзакционны; прежний OrganizationContext, checksum и ранее закреплённый профиль не переписываются.
- Стоп-условия: на старые значения/новый артефакт было «да», снято прямым решением владельца. Публичный API расширен только причинами ошибок/метаданными сохранённого черновика, существующие команды и данные совместимы. Миграции/удаления/новой передачи чувствительных данных нет. Rollback определён ниже. Других зависимых открытых решений нет.

## Воспроизведение на базе и реализация

На базе `66458599` неизвестное C17 значение дало `ready_for_confirmation`; тест `test_org_admin_initial_setup_updates_only_the_single_attached_card` подтвердил HTTP 200 и отдельный UPDATE имени/кода. Admin 02 уже обеспечивал атомарное подтверждение имени/контекста, повтор, конфликт и откат; переиспользовано без переписывания.

Изменены `Api/routes.py`, `Api/questionnaire_sources.py`, `web/js/screens/admin/organizations.js`, адресные тесты unit/e2e/integration/browser, `web/dist`, инвентарь артефактов. POST оставлен только суперадминистратору; обычный PATCH запрещает `name`/`code`, включая смешанный запрос, и сохраняет прочие поля. Загрузчик проверяет SHA256, identity, версию, статус и соответствие каждой исторической пары действующим утверждённым значениям. Для каждого нового preview в `validation_json` фиксируется применённый набор правил; при подтверждении та же фактически проверенная версия/checksum попадает в `source_manifest_json` вместе с каналом/шаблоном. Значения C17 сохраняются дословно. Опубликованные редакции читаются без повторной проверки новой политики.

## Проверки

Кодовые коммиты после переноса на актуальный `main` — `5b58770d17a1d68bde0bc962dc84e6f7e0e05e9b` и `6101fb43170e25fe8bce300827fcc0e19a5ac9e4`. Локальный контур: PostgreSQL 15 UTF8 на `127.0.0.1:55504`, отдельные синтетические базы `agent4k_pytest_adm04` и `agent4k_pytest`, maintenance `postgres`; `PYTHON_DOTENV_DISABLED=1`. Одноразовый сервер после проверок остановлен. Реальные LLM, почта, рабочая БД и TEST не используются.

- Адресные unit/HTTP (`test_questionnaire_sources.py`, `test_ux_fix20_04_admin_readiness_http.py`, `test_adm28_confirmation_http.py`): **36 PASS** после переноса правил в артефакт.
- Адресные owned PostgreSQL/HTTP (`tests/integration/test_questionnaire_sources_db.py`, `--run-integration`): **6 PASS**. В том числе оба поля/канала, неизвестное значение и старый черновик, отсутствие публикации и переименования, source manifest, повтор и конфликт.
- `node --test tests/frontend/*.test.mjs`: **476 PASS** на обновлённой базе.
- `npm run lint:js`: **PASS** на обновлённой базе после последней UI-правки.
- `npx playwright test tests/browser/questionnaire-draft-guards.spec.mjs`: **10 PASS** на обновлённой базе; синтетический HTTP/UI, включая ошибку при уже опубликованной версии и недоступной политике.
- `npx playwright test tests/browser/questionnaire-it-inputs.spec.mjs`: **1 PASS** на настоящих UI/HTTP/изолированной PostgreSQL; preview → confirm → reload/readback, без реального LLM. Последующая UI-правка затронула только сообщение об ошибке черновика, проверенное отдельным browser-набором.
- `npm run test:backend:http`: **229 PASS**, 15 deselected на обновлённой базе.
- `npm run test:backend`: **1315 PASS**, 723 deselected на обновлённой базе при разрешённом локальном `ps`. Первый sandbox-прогон на старой базе дал 1304 PASS/9 FAIL из-за `PermissionError: ps`; эта причина устранена повтором.
- Первый полный `npm run test:backend:integration` без `STAND_ADMIN_URL`: **445 PASS / 9 SKIP / 11 FAIL / 25 ERROR**. Большинство отказов вызвано отсутствием обязательного URL; две связанные FAIL выявили ошибку аргумента проекции суперадминского POST, исправленную и перепроверенную адресно (**8 PASS** с `test_path_ac02_organization_create_db.py`). Один сбой наблюдения idle transaction не повторился во втором прогоне.
- Второй полный integration-прогон с maintenance URL, но с нестандартным именем `agent4k_pytest_adm04`: **463 PASS / 2 SKIP / 25 ERROR**. Все ERROR пришлись на EXEC-FIX-02 fixture, который принимает только точное имя `agent4k_pytest` (подтверждено адресным повтором **10 PASS**).
- Финальный полный `PYTHON_DOTENV_DISABLED=1 STAND_ADMIN_URL=…/postgres TEST_DATABASE_URL=…/agent4k_pytest npm run test:backend:integration` после rebase: **488 PASS, 2 SKIP, 1548 deselected**, 925,27 с. SKIP — два явно маркированных реальных LLM-вызова. После старта полного набора добавлено только дополнительное утверждение о неизменности старого checksum/source manifest в адресный тест; этот файл отдельно повторён на `agent4k_pytest_adm04`: **6 PASS**. Серверный код в течение полного прогона не менялся.
- После переноса на `052a9be5`: HTTP **229 PASS**, frontend **472 PASS**, browser `questionnaire-draft-guards.spec.mjs` **10 PASS**, `npm run lint:js`, `npm run build:web`, `git diff origin/main --check` **PASS**. Полный PostgreSQL integration-прогон после этого переноса не повторялся; изменение `main` относится к ASUX-04, общий `Api/routes.py` совместился без ручного конфликта и покрыт повторным HTTP-набором.
- Draft PR [#266](https://github.com/VadikB/4K_MBTI/pull/266), HEAD `6101fb43`: CI / frontend и CI / pytest **PASS**; Full verification / browser, integration и full-verification **SKIPPED** по draft-условию; deploy-test **SKIPPED**. Человеческое review и полный CI перед merge открыты.

## Полномочия, риски и откат

Пользователь отдельно разрешил push ветки в `VadikB/4K_MBTI` и создание одного draft PR: `branch_push=true`, `pr=true` (draft). `version_bump=false`, `merge=false`, `deploy=false`, `artifact_publish=false`; вложенное ТЗ не меняет эти флаги. Локальные проверки используют только маркерную синтетическую БД. Технический артефакт совместимости подготовлен в ветке по прямому решению владельца, его публикация происходит только в согласованном выпуске.

Откат к 2.1.45: вернуть код и bundle прежнего релиза; новые черновики/публикации и контексты не удалять, старый пакет и данные остаются. До отката остановить новые подтверждения: прежний код вновь разрешает обходное переименование и неизвестные C17. Для продолжения подтверждений безопаснее совместимый исправленный релиз с сохранёнными проверками C17 и прав; down migration не нужна.

## Следующий шаг и открытое

Передать [draft PR #266](https://github.com/VadikB/4K_MBTI/pull/266) на человеческое review и визуальную приёмку. После их принятия владелец отдельно решает вопрос о выпуске на TEST: PATCH, Ready, полный CI, merge и deploy по `CONTRIBUTING.md`. До такого решения эти действия не выполняются.

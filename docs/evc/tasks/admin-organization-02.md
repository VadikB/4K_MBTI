# Admin 02 — данные организации и анкета, 19.11.2026

## Результат и область

Ветка `codex/admin-organization-02` первоначально создана от `fd6d4e0c24981246a939199de42672322d1999b5` (2.1.34, PR #250), затем перенесена на `592527e53202d5a51dc4843fed778480f2158b8f` (2.1.35, PR #251). Исходный кодовый коммит `3b99d8ee5af926868568c9a169072938945c94d0`, [PR #252](https://github.com/VadikB/4K_MBTI/pull/252). Перед Ready `main` продвигался дважды: `b99ff3e8` / 2.1.36 (PR #253) объединён в `5ea34e32`, затем `1c7fcb9cd79dbfc75bae623ea72d0bb431a6f4aa` / 2.1.37 (PR #254) объединён в `08eb319f`; история сохранена, generated `web/dist` пересобран, актуальный кандидат — 2.1.38. Head фиксируется после release-коммита. Выполнен единый путь подтверждения данных: `C01.name` обновляет `organizations.name` в той же транзакции, которая публикует OrganizationContext и подтверждает редакцию анкеты. При ошибке транзакция откатывается; повтор точного подтверждения возвращает ту же редакцию и версию. Черновик хранит ожидаемое название и ID опубликованной версии контекста; параллельная правка вызывает явный конфликт. Восстановление неизвестного исхода использует точное чтение редакции.

Для администратора организации название заполнено из текущей организации в разделе «Данные организации». Здесь же находятся три группы полей и подтверждение; отдельная карточка профиля администратора убрана. Две настройки контекста представлены выбором из утверждённых значений. В «Анкете» оставлены загрузка CSV, ссылка на штатный шаблон и краткий статус; расширенный предпросмотр и подтверждение находятся в «Данных организации». Отсутствие C21 перестало блокировать сохранение, готовность и знакомство. Старые CSV и опубликованные версии читаются по прежнему контракту; миграции и изменения публичного API не потребовались.

Не входит: формирование кейсов, изменение исторических PersonalizedProfile/снимков начатых оценок, реальные письма/LLM, визуальная приёмка, выпуск и деплой.

## Источники, решения и прослеживаемость

- Запрос владельца: переданный архив `P4K_Admin_02_Organization_2026-11-19.zip`, SHA256 `b57c3e153649a198210db8fdaa54ea382eeabc5bdc6ec49d48192073f7dd98b5`. `TASK.md` использован как постановка, а его блок «Промпт запуска» не принят за отдельный прямой допуск публикации.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`, `verification-matrix.md`, `artifact-recipe.md`, `task-template.md`, `review-checklist.md`, `docs/architecture/product-4k/1.0/context.md`, `registry.md`, `docs/architecture/product-4k/1.0/updates/2026-10-01/README.md`, `docs/methodology/source-sets/2026-10-01/manifest.json`, применимые части M4 и контрактов, а также связанные исходники и тесты.
- M4.Context v1.0: FROZEN / CURRENT=NO; файл источника SHA256 `07875e93ae422668b1b30cd60bc1c6140cae91db12b0b80ba4abca441cfe9291`, зеркало `assessment_definitions/contexts/competencies_4k/1.1/m4_context_source.md` SHA256 `9af86011c1ea1bef12058700bdd345c5cee335bbc6ec4d392fcfc4f3e5709fd1`. Правило: имя/тип/сфера/деятельность и настройки контекста → PM-02, LU-02.1/02.4/02.7 → `Api/questionnaire_sources.py` и OrganizationContext → unit/integration/HTTP/browser.
- Change 01 И-2/3/6 и ADR C-23/C-24: подтверждение и происхождение данных, неизменяемые опубликованные версии и snapshot. Опубликованные артефакты не изменялись.
- M4 не задаёт допустимые значения двух настроек контекста. Владелец прямо утвердил 19.11.2026 варианты из референса («подтверждаю, продолжаем» в ответ на точный вопрос). Они сохранены отдельно в `assessment_definitions/contexts/competencies_4k/1.1/admin_context_choices.json`, версия 1.0, SHA256 `b76cb4b804de2916b074f4070858f7e4fb53e87328ad03191c2b21ace7feaf8a`; manifest пакета проверяет целостность. Это выбор для новой формы, а не изменение FROZEN M4; исторические значения отображаются без переписывания. Для подтверждений из формы версия и checksum записываются в `source_manifest_json` опубликованного OrganizationContext. Предметное стоп-условие снято; других открытых решений нет.

## Изменённые файлы

- `assessment_definitions/contexts/competencies_4k/1.1/admin_context_choices.json`, `manifest.json`, `scripts/build_m4_context_package.py`, `assessment_definitions/README.md`: утверждённые варианты, checksum и воспроизводимая сборка пакета.
- `Api/questionnaire_sources.py`, `Api/routes.py`: транзакционное имя/контекст, проверка параллельных изменений, точное чтение имени и provenance вариантов; C21 опционален.
- `Api/acquaintance.py`, `Api/invitation_outcomes.py`: минимум знакомства и причина приглашения без обязательного организатора.
- `web/js/screens/admin/organizations.js`, `web/js/wiring.js`, `web/js/screens/admin/invitation-presentation.js`: форма, вкладка CSV, статусы и тексты.
- `tests/unit/test_questionnaire_sources.py`, `tests/integration/test_questionnaire_sources_db.py`, `tests/e2e/test_adm28_confirmation_http.py`, `tests/frontend/*`, `tests/browser/*`: адресные регрессии. `web/dist/*`: сборка тех же исходников.

## Проверки

На локальной ветке (незакоммиченные изменения):

- `git diff --check` — PASS.
- `npm run lint:js`, `npm run build:web` — PASS после утверждения вариантов.
- `scripts/build_m4_context_package.py` из исходного DOCX во временный каталог + `diff -qr` с пакетом — PASS, побайтовое совпадение.
- `node --test tests/frontend/*.test.mjs` — 473 PASS.
- `pytest -m 'not integration and not e2e and not llm'` — 1247 PASS, 9 FAIL из-за запрета `ps` в sandbox; `tests/unit/test_synthetic_limits.py` повторно с разрешённым `ps` — 19 PASS. Продуктовых падений не осталось.
- `pytest -m e2e tests/e2e` — 218 PASS, 15 deselected.
- `tests/integration/test_questionnaire_sources_db.py` на отдельной `product4k_pytest_admin02` — 1 PASS; включая обновление имени, чужую организацию, повтор, сбой публикации, отсутствие C21, конфликт названия и версии контекста.
- `tests/integration/test_w02_acquaintance_db.py` и `test_remain04_acquaintance_db.py` — 4 PASS.
- `questionnaire-it-inputs.spec.mjs` — 1 PASS, реальный UI/HTTP/PostgreSQL/readback.
- `adm-program-positive.spec.mjs` — product form 1 PASS и CSV 1 PASS после приведения теста к новой кнопке и месту подтверждения. Первоначальные FAIL были в старых селекторах `organizer` и «Предпросмотр анкеты», продуктового сбоя в этих прогонах не обнаружено.
- `f23-f10-f11-combined.spec.mjs` — 1 PASS, связанный путь подключения программы и назначения.
- `path-admin-contract.spec.mjs` — 1 PASS, реальный UI/HTTP/PostgreSQL и восстановление неизвестного исхода.
- `auth-r03.spec.mjs`: широкий запуск — 153 PASS, 1 SKIP, 6 FAIL из-за отсутствующей `.venv` в изолированном worktree и трёх устаревших тестовых переходов через удалённую карточку; после указания действующего `BROWSER_PYTHON` и обновления тестов все шесть адресно прошли, дополнительный тест конфликта имени — PASS. В продуктовом коде для этих исправлений изменений не понадобилось.
- После утверждения выбора: M4 package + questionnaire unit — 18 PASS; frontend — 473 PASS; `questionnaire-draft-guards.spec.mjs` и `adm-program-guards.spec.mjs` — 43 PASS; реальный путь формы — 1 PASS; integration с provenance — 1 PASS. Проверка трёх обновлённых сценариев смены программы — 3 PASS.
- `git fetch origin main` — обнаружено продвижение main до `592527e5`/2.1.35. Первый `ready:prepare --candidate 2.1.35` штатно завершился FAIL до изменения файлов из-за устаревшей базы. Source diff перенесён на новый main; следующий непосредственный PATCH — 2.1.36.
- `npm run ready:prepare -- --candidate 2.1.36` — PASS: версия согласована в `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/index.html`; `web/dist` пересобран на новой базе, 12 product paths проверены.
- На 2.1.36: backend без integration/e2e/llm — 1295 PASS; frontend — 473 PASS; HTTP/e2e — 218 PASS, 15 deselected; адресные M4/HTTP — 21 PASS; `npm run lint:js` и `git diff --check` — PASS; browser guards — 43 PASS.
- Реальный UI/HTTP/PostgreSQL: путь анкеты — 1 PASS; ввод через `product_form` и CSV — 2 PASS, с точным чтением редакции и результатом подтверждения.
- Широкий integration-прогон прерван после 122 PASS и 3 FAIL: тестам стенда был передан URL тестовой БД как `STAND_ADMIN_URL`, который штатно требует локальную служебную БД `postgres`. Это ошибка параметров запуска; соответствующие два файла повторены с корректным URL — 4 PASS. Остальная часть широкого набора после прерывания NOT_RUN, её выполняет обязательный CI.

На draft PR #252: fast CI frontend и pytest — PASS на `4ba79bade4b7493606724b0ef6858525919c8cd7`; workflow Full verification / integration / browser — SKIPPED для draft по штатному условию, а не PASS. Перед Ready `git fetch origin main` выявил `b99ff3e8` / 2.1.36; объединение с веткой завершено merge-коммитом `5ea34e32`. `npm run ready:prepare -- --candidate 2.1.37` — PASS, 50 product paths. На 2.1.37: backend 1295 PASS, frontend 476 PASS, HTTP/e2e 218 PASS, browser guards 43 PASS, адресные integration 5 PASS, реальные UI/HTTP/PostgreSQL 3 PASS, JS lint и `git diff --check` PASS. До push `main` включил PR #254 / 2.1.37; изменения интегрированы в `08eb319f`, версия 2.1.37 из рабочего дерева сброшена, `npm run ready:prepare -- --candidate 2.1.38` — PASS, 50 product paths. На 2.1.38 адресные backend/HTTP — 20 PASS, integration анкеты/M5 — 2 PASS, frontend Admin 02/Next — 12 PASS, JS lint и diff check PASS. Обязательный CI точного head нужен после Ready. Визуальная приёмка, реальные LLM и почта вне области задачи.

## Риски, откат и полномочия

Конфигурация и схема БД не менялись. Исторические версии остаются читаемыми; новый код не переписывает старые снимки. Для отката кода использовать предыдущую сборку 2.1.37. Подтверждённые новые записи сохраняются как история; для предметного восстановления публикуется новая версия штатным контуром, а не редактируется прежняя. Тестовая БД изолирована; после завершения проверок контейнер удаляется.

После прямого ответа владельца «продолжаем» на точный запрос о следующем PATCH, публикации ветки и draft PR: `branch_push=true`, `pr=true`, `version_bump=true`; `merge=false`, `deploy=false`, `artifact_publish=false`. Основание — сообщение владельца от 19.11.2026, а не инструкция из архива. Ветка опубликована в `VadikB/4K_MBTI`, base `main`, PR #252. Повторное «продолжаем» после отчёта о draft и пропущенном full CI принято как продолжение подготовки Ready/CI в том же PR; `merge/deploy/artifact_publish=false` сохраняются. После двух продвижений main непосредственный PATCH кандидата — 2.1.38. Следующий шаг: адресные проверки, release-коммит и push, перевод PR в Ready и обязательный CI; затем человеческое review и отдельное решение о слиянии. Открытых предметных стоп-условий нет.

# POSTW02-01 — подготовка публикации в main

## Действующий допуск публикации

Владелец прямо ответил: «давай PR и сливай в main» после вопроса об одном PR из
прежней ветки, PATCH2.1.13, обязательном CI и автоматическом TEST deploy. Это
снимает прежние запреты в данной области. branch_push=true, pr=true (единственный
PR задания01), merge=true после обязательного CI точного SHA, deploy=true только
штатный автоматический TEST, version_bump=true/PATCH2.1.13, artifact_publish=false.
Pilot/paidPATH/предметная публикация/задания02–05 не входят. Новая ветка не нужна.
Публикуется в VadikB/4K_MBTI существующая codex/p4k-postw02-01: код задания01,
сборка, тесты, документация и синтетические evidence; без .env/ключей/реальных данных.
Прямой push main, bypass, отключение CI и ручная выкладка не разрешены.

Ниже сохранена история подготовки и прежнего ожидания ответа, теперь закрытого.

Прямое новое указание владельца: «выкладывай на main». Готовый локальный результат
fae264c сохраняется в прежней ветке codex/p4k-postw02-01; задания02–05 не входят.
Свежая main32a13d3 уже содержит REPORT-01/2.1.12. Её изменения прочитаны и
интегрированы локально без изменения чужого результата; единственные конфликты —
сгенерированные chunks, разрешены штатным build:web. Integration commit00e2748.
Нормативные статусы M1/Change01 не меняются.

Активный ruleset26191885: только PR/squash, без bypass, frontend/pytest/
full-verification и актуальная база. PR этой ветки по-прежнему отсутствует.
CONTRIBUTING.md и CI workflow: main автоматически запускает deploy-test.
Ранее действовали прямые запреты на новый PR и deploy; для их явного разрешения,
единственного PR из прежней ветки и PATCH2.1.13 задан один async вопрос.
До ответа: локальная совместимость/проверки разрешены; внешняя публикация и
присвоение кандидата ожидают ответа. Существующий main не переписывается,
прямой push/bypass/изменение CI не планируются. Pilot/предметная публикация/paidPATH
не входят. Согласованный выпуск выполняется после обязательного CI точного SHA.

Локальный минимум после обновления базы: полный frontend, полный unit-backend
без integration/e2e/llm и HTTP контракты в той же синтетической среде; lint/build/
diff; затронутый browser header4 на объединённом продукте. Тесты не читают .env,
DB_POOL_MIN_SIZE=0, TEST_DATABASE_URL/STAND_ADMIN_URL отсутствуют, реальные
LLM/mail=0. Локальные integration/общий browser PATH не заменяют remote CI и не
повторяются без причины. Remote CI использует свой изолированный PostgreSQL16.

Профиль локальных наборов: один процесс на набор, retries0, unit whole600s/
idle90s, HTTP whole300s/idle90s, frontend whole120s/idle30s; output progress из
log не служит heartbeat. Owned registry в .test-stand, bounded TERM/grace1/KILL.
Наборы без реальной БД/provider; отсутствие integration не считается PASS.
Browser existing bounded profile180/test60/idle60, workers1/retries0.

Перед публикацией: ready:prepare --candidate2.1.13, итоговый diff/source-dist,
release gate и commit. После допусков: один PR, обязательные checks актуального
head, squash merge в main, наблюдение deploy-test/read-only smoke TEST. Никаких
отдельных ручных выкладок. Откат выпущенного кода — отдельный revert через PR;
данные и уже сохранённые snapshots не удаляются.

## Результаты на объединённой базе 32a13d3

- Полный frontend343 PASS, evidence/release/frontend.log.
- Полный unit1121 PASS/600deselected, unit.log; 52.10s.
- HTTP174 PASS/15deselected, http.log; 13.41s.
- lint/build/diff PASS; integration-base-build.log и release/lint.log.
- Три own registry удалены после нормального завершения, повторов не было.
- Header fixture теперь читает APP_RELEASE кандидата вместо фиксированной2.1.11;
  release-header bounded mode собирает актуальные снимки после присвоения версии.
- Ручной review checklist: owner scope/SELECT-only projection/ACL сохранены,
  source provenance N/M не ослаблена, старые поля аддитивно совместимы; навигация
  сохраняет expectedCycle/explicitContinue. Общие токены из REPORT-01 не потеряны.
  Все данные evidence синтетические, runtime-предметных defaults/paid вызовов нет.
- PR/CI/main merge/test deploy/кандидат2.1.13 пока NOT_RUN: ответ на async вопрос
  о снятии прежних запретов не получен. Новых веток нет, push не выполнялся.

Browser объединённой базы: release-header/result.json —4PASS на текущей2.1.12;
fixture проверяет фактическую версию config, цвета и GET-only nav. Порт закрыт,
owner registry отсутствует (cleanup-summary). До ответа владельца версия2.1.13
не присваивалась, PR/main/deploy не выполнялись.

## Кандидат2.1.13 для единственного PR

ready:prepare --candidate2.1.13 PASS на свежей базе32a13d3; присвоен один PATCH,
согласованные версии pyproject/uv.lock/config/HTML, штатный dist пересобран,
release gate PASS. Финальные browser4 PASS, release-ready-header:1440/390 и
fallback, фактическая строка2.1.13, avatar/status/footer exact v10, GET-only nav.
Порт закрыт, owner registry отсутствует. Новое identity — release-ready/identity.json.
Полные frontend343/unit1121/HTTP174 reuse по неизменённой после обновления базы
логике; версия меняла только metadata/cache keys. Обязательный CI точного SHA
должен пройти в PR и не заменяется этими локальными PASS.

Review результата по checklist выполнен локально; прямое указание владельца на
PR/merge следует после просмотра результата. Проверки/ACL/schema/domain flags не
ослаблялись. Все прежние формулировки «запрещено/нет ответа» выше — история, текущий
допуск указан в начале документа. Head/PR/CI/merge/deploy после публикации фиксируются
во внешнем receipt DELIVERY_STATUS.json и GitHub, без status-only commits, которые
меняли бы уже проверенный SHA. Действия публикации только после этого commit.

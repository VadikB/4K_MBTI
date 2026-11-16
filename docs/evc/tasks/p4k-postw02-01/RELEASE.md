# POSTW02-01 — подготовка публикации в main

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

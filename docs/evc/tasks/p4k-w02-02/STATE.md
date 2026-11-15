# STATE P4K-W02-02

15.11.2026; base68a52a7c21bfe7759d2522a644ad194f7d111f4e, codex/p4k-w02-02,2.1.7.
Разведка завершена; активна реализация UI18состояний и read-onlyrefresh.
W02-01/PR221 merged; чужие изменения сохранены. Новых процессов/контейнеров/БД пока нет.
Локальные node_modules/.venv — ignored ссылки на зависимости worktree01.
Следующий шаг — адресные проверки; до stand дополнить ресурсную квитанцию.

Перед run w02-02-browser01: ownerCodex/P4K-W02-02. Исходные чужие listeners:
PostgreSQL1163:55432, rapportd752:49152,AdGuard783:49210,ControlCenter807:5000/7000,
logi1159:59869,Google1211:7679; не используются/не останавливаются.
Свой staticfixture ephemeral127.0.0.1 и REMAIN04:18784/auth-r03:18764;
PID/ports до использования — evidence/browser01/runner.json и resources.jsonl.
БД/контейнеры/LLM/письма0. Старт W02_RUN_EVIDENCE=docs/evc/tasks/p4k-w02-02/evidence/browser01
W02_RUN_FILES='w02-readiness.spec.mjs remain05-first-start.spec.mjs exec-fix02-preparation.spec.mjs remain04-waiting.spec.mjs'
W02_RUN_GREP='W02-02|REMAIN05|first preparation|REMAIN04' python3 docs/evc/tasks/p4k-w02-01/run-browser.py.
Штатный runner1worker/retries0/global600s/no-progress90s; start_new_session,
finallySIGTERM→5sSIGKILL только своейгруппы, без autorestart; statusps/recordedports,
stopkill-ownPGID. На любом исходе groupabsent/portsclosed подтвердить. Preview replay тойжекомандой.
Browser01 NOT_RUN_ENV: sandbox listenEPERM; ни один сценарий не исполнялся.
Ownedgroupabsent=true; повтор browser02 с разрешениемlocalhost, тот же scope/лимиты,
новые receipts evidence/browser02. Исправлен только afterAll guard для неоткрытогоserver.
Для фактического названия воспроизведён отсутствующий displayfield в read_state:
добавлена assessment_name из точно bound assessment_configurations.name. Нет новой нормы,
схемы или изменения команд; regression в existing REMAIN04HTTP/SQL. Нужен backendminimum.
Browser02:2PASS firstpreparation, затем no-progress92.7s, ownedgroupSIGKILL отправлен;
REMAIN04 сохранил locator старого названия «Проверить назначение» после переходаnetwork,
где кнопка «Повторить проверку». Исправлен устойчивый locator поid; никаких guards не ослабляли.
Browser03 — теже scope/лимиты/ownership, evidence/browser03, testtimeout60000.

Перед PG/HTTP run w02-02-pg01: ownerCodex/P4K-W02-02; исходныйPG1163:55432 чужой,
не используется. Свой новыйcluster .test-stand/w02-02-pg, port55503, role stand_owner,
DBagent4k_pytest (только синтетика), trust127.0.0.1, без autorestart/контейнеров.
Старт .venv/bin/python .test-stand/run-w02-02-pg.py; runnerPID/PGID/postmasterPID
пишутся доtest в evidence/pg01/resources.json. Statuspg_ctl-Dclusterstatus/lsof55503.
Stopвfinally: boundedtestSIGTERM→5sSIGKILLownPGID; pg_ctl-Dcluster-mfaststop,
проверкаportclosed/pgstatus. Max600s/no-progress90s, LLM/mail0, штатныйpytestконтур.
Выбор: REMAIN04actualHTTP+nameprojection; pilotstartadmission sameAS/0answers,
concurrent/lostreceipt/revocation; HTTPpreparationretry; неизменные queueguards
исторически REMAIN05#219, новыеядроочереди/полныйпутьReportне запускаются.
Browser03:29PASS/1FAIL18.7s, groupabsent=true. FAILtestсразупослеgoto включилfailRead
до первоначальногоGET; добавлено явное ожидание исходногоfailedэкрана. Productне менялся
ради этогоrace. Code-review: readbackcause403/409 теперьперечитываетназначение,
сохраняетотказ; name перемещено сразу подзаголовком поREFERENCE. Это конкретнаядельта
для следующего browser04. Fullfrontend325PASS; backend1093PASS; PG/HTTP9PASS/11.16s,
cleanupstop0/port55503closed/postmasterabsent. ПроверкиCI ещёNOT_RUN.
Перед browser04: прежние ownership/ports/deadlines/stop, своих активных процессов нет.
Расширение только изменёнными auth-r03 waiting/readiness/firststart fixtures иW02-01
сохранённым path1440;1worker/retries0,600s/90s. Evidence/browser04; старт прежнимrunner
с W02_RUN_FILES='w02-readiness.spec.mjs w02-acquaintance.spec.mjs remain05-first-start.spec.mjs
exec-fix02-preparation.spec.mjs remain04-waiting.spec.mjs auth-r03.spec.mjs',
grep в runner.json. Own port18764/auth-r03 и18784/remain04 плюсephemeral;LLM/mail0.
Browser04:40PASS/5FAIL55.4s/groupabsent. Все5FAIL — конкретные устаревшие copy/DOMoracles:
oldnetwork/service/orgtitles и nameожидалосьвfeature-list, теперьоноточноподheading.
Поправленыожиданиябезослабленияповедения. Добавленcurrentguardдоdeferredprepare,
чтобыlogoutдоmicrotaskнемоготправитьresolveподдругимвладельцем;UI/commandsконтрактпрежний.
Browser05 повторяетфинальныйизменённыйнабор46tests, теже600s/90s/1worker/retries0,
ownedresources/stopкакbrowser04;receiptsbrowser05. Это продуктивныеисправления,
не повторыодногоFAILбезпричины. Следом source/testedhashes+кандидат2.1.8/PR/CI.
Browser05:45PASS/1FAIL29.9s/groupabsent. ЕдинственныйновыйincompletecaseнеждалasyncGET
послеclick; заменён немедленныйcount наexpect.poll плюс buttonenabled и0commands.
Повтор browser06 толькоэтогосценария,прежниересурсы/лимиты/stop;остальные45PASSсохраняются.
ДляAC05добавленаадреснаяреальнаяHTTP/SQLветка unstartedreadback→samekeyexplicitstart:
новыйownedcluster .test-stand/w02-02-pg02,port55503/agent4k_pytest/stand_owner,
start .venv/bin/python .test-stand/run-w02-02-pg02.py; теже600s/90s/stopfinally,
новыеevidence/pg02resources.json/cleanup.json. ЧужойPG55432неиспользуется.
Browser06:1PASS/1.5s, groupabsent=true. PG02actualHTTPunstartedreadback1PASS/2.41s,
cleanupstop0/portclosed/postmasterabsent. Frontend325PASS/1.36s; lint/diff-checkPASS.
Найдена ещё одна историческаяcopyoracle вpath29-participant: изменена только строка
согласованногоnetworkзаголовка. Browser07 только3visualсценария сохраняет6PNGвevidence,
посколькуPlaywrightочищаетoutputDirприкаждомrun;runtimeнеизменён. Прежниеownership,
600s/90s/1worker/retries0/teardown/LLM0/mail0. Ресурсы browser07/runner/resources.

## Локальный кандидат готов

15.11.2026: реализация и AC01–06 технически завершены. Кандидат 2.1.8.
Итог: frontend325 PASS, backend1093 PASS, actual HTTP/SQL9+1 PASS,
controlled browser45 PASS плюс адресный исправленный incomplete1 PASS;
visual3 PASS, шесть PNG просмотрены Codex. Lint/build/release/diff-check PASS.
Проверенные байты сохранены в evidence/checked-content.json, подробности — CHECKS.md.

Все свои группы процессов завершены, порты закрыты; повторная сверка после reap
закрыла первоначальный group_absent=false browser02. Первичный итог —
evidence/cleanup-final.json. Два собственных PG остановлены; чужой PG55432 сохранён.
Preview воспроизводится командой browser07 с записанными конечными лимитами.

Активный шаг: свой commit → push codex/p4k-w02-02 в origin VadikB/4K_MBTI → один
Ready PR → mandatory CI точного head. Следующее изменение STATE не требуется:
immutable SHA, PR/CI и окончательный статус сохраняются в локальном RELEASE_STATUS.json
после CI, без изменения проверенного head. Human review/visual TEST PENDING;
merge/deploy/artifact_publish=false. После готового PR/CI — остановка, новая карточка
не запускается. Настроенная Git identity: VadikB <bvv.fructus@gmail.com>.

## CI #222: связанный дефект выполнения подготовки

Head2d9649b: frontend/pytest/runtime2 PASS; runtime4 FAIL Recovery до первогоAS.
Primary GitHub job132737883662/run43689814212: ProductCycle preparation deadlock
в m7_parameter_resolution.ensure_schema, DROPTRIGGER vs CREATEORREPLACEFUNCTION.
GET/acquaintance resolve_display_timing и worker create_plan одновременно вызывают
resolve→ensure_schema. Это воспроизведённый серверный дефект принятого действия;
исправление допускается границей W02-02. Контракт/схема/параметры не меняются.
Дополнительные старые copy-oracles найдены в runtime blocked и auth-r03 R08 budget.

До PG03 before: новый ownedcluster .test-stand/w02-02-pg03/port55503/agent4k_pytest,
теже владелецCodex, исходныйPG55432чужой,600s/90s/stopfinally; старт
.venv/bin/python .test-stand/run-w02-02-pg03.py, evidence/pg03/resources/cleanup.
Тест детерминированно запускает одновременно display/prepare resolver в READONLY:
старыйDDL должен датьFAIL. После — убрать только DDLизresolve, bootstrapсохранить.
PG03 before:1FAIL ReadOnlySqlTransaction (CREATE TABLE из resolve),2resolverпараллельно.
RootcauseсовпадаетCIstack. Удалёнensure_schemaтолькоизresolve; bootstrap database.ensure_m5_runtime_schema
и explicit save_revision сохраняются. Нет миграции/изменения параметров/guards.
PG04 after: новыйownedcluster .test-stand/w02-02-pg04:55503, теже lifecycle/limits,
start .venv/bin/python .test-stand/run-w02-02-pg04.py; весь M7parameters + pilotadmission,
evidence/pg04. База/пользователь/исходныечужиересурсы и stopкакPG03.
PG04 after25PASS/23.87s, stop0/portclosed/postmasterabsent; backend1093PASS/41.77s.
До actual-browser PG05: новыйownedcluster .test-stand/w02-02-pg05:55503/stand_owner,
maintenancepostgres толькодлясозданиясвоей test DB штатным test_stand; backend18830
(runtimeblocked) и18859(PATH29), собственныеstateвignored.test-stand.
Start .venv/bin/python .test-stand/run-w02-02-pg05.py; statuspgctl/lsof55503/18830/18859;
stopштатныйtestfinally+ownPGIDTERM/KILL+pg_ctlfaststop. PIDдоиспользованиявpg05/resources.
ВыборстрогоUnapprovedLIMITED/путьдопервойAS,0оценочныхответов, providersdisabled,
P4K_FULL_PATH/REAL_PROVIDER/CONTROLLED_PROVIDER/COMPLETION_PROFILE=0, LLM/mail0.
Global600s/no-progress90s/1worker/retries0. ЧужойPG55432нетронут.
PG05actualbrowser: blocked1PASS; PATH29FAILстароеизвлечениеoperationIDизвидимоготекста
preparing, которыйW02эталоннепоказывает. Исправленoracle: savedAcquaintanceHTTPчитает
прежнийoperation_idдо/послерeload;0extraoperationsпроверяетсяпопрежнему.
FastCIдополнительнообнаружилпотерюточнойпричиныmissingposition: waitingPresentation
сохраняетknownparticipant_fields/organizationreasonsвбезопасномтексте безcontact.
PG-R1 теперьтакжепроверяетотсутствиепредложенияобратитьсякadmin.
PG06: actualPATH29onlyповтор,новыйownedcluster .test-stand/w02-02-pg06:55503,
теже18859/noLLM/noletters/600s/90s/oneworker/stopfinally/startscript-pg06/evidencepg06.
Browser09 послеPG06: толькоPG-R1/R08 плюс3visual;прежнийfixtureprofile/runner/teardown.
Browser08R08PASS1/1.3s. Это последнийпродуктивныйциклпоисправленнымконкретнымпричинам.
PG06PATH29FAILnextoldoracle: summaryискаласьнаstandaloneReady. Добавленыявные
«Посмотреть знакомство»→проверкатехже3ответов→«Вернутьсякготовности».
Операция/profile/Cycle/AS/countsпроверкисохранены. PG07повтортолькопути,
новыйownedcluster .test-stand/w02-02-pg07:55503/18859, прежниеowner/stand/limits/stop,
start .venv/bin/python .test-stand/run-w02-02-pg07.py; evidencepg07.
PG07actualPATH29PASS1/21.6s: invitation→assignedsources→3answers→lostpreparereply→reload→
explicitreadiness/history→firstAS,0assessmentanswers. Bootstrap/resolveraftercorrect.
Beforebrowser09: PG07остановлен, тольконовыеstaticfixtures(18764/ephemeral),
теже1worker/retries0/600s/90s/stopfinally; scopePG-R1,R08и3W02visual,
evidence/browser09, старыйфактическийPG55432сохраняется. Replayштатнымrun-browser.py.
УточнениеграницыPG07: штатныйdefaultPATH29послепредъявленияASотправляет1synthetic
assessmentanswer. PG07PASS нельзявыдаватьзаитог0answers; этоошибкавыборапрофиля,
зафиксированнаяотдельно. РеальныхLLM/писемнет. Добавленtest-onlyopt-in
P4K_STOP_AFTER_FIRST_AS=1 (default0сохраняетCI), ранняяостановкапередTurn/assignmentreplay
сactualSQLreceipt0answers/sameCycle/assignment/profile/AS/Session.
PG08короткийповторсэтимфлагом: .test-stand/w02-02-pg08:55503/18859, прежниелимиты,
owner/stopfinally/отсутствиеautorestart; старт .venv/bin/python .test-stand/run-w02-02-pg08.py,
evidencepg08. ОстальныеPGstopped/portsfree, исходныйPG55432чужой.

## Повторный кандидат после CI-исправлений

PG08 PASS 1 / 22.3 s: окончательная граница — первая AS открыта, оценочных ответов 0.
SQL receipt и штатный stand cleanup перенесены в evidence/pg08 без credentials.
Browser09 PASS 5 / 4.6 s, backend 1093 PASS, frontend 325 PASS;
M7/admission SQL/HTTP 25 PASS. Готовность того же PATCH 2.1.8 повторно проверена
штатным ready:prepare от свежего main. Обновлены checked-content hashes.

Активно: второй собственный commit и push в тот же PR222, новый mandatory CI.
Первый CI остаётся историческим FAIL и описан в CHECKS. Не менялись управляющие
документы, schema, frozen artifacts, методология и полномочия merge/deploy.

Второй CI head4c9af2e: frontend/pytest/fast/все4runtime PASS; integration1FAIL/
414PASS/2SKIP. ЕдинственныйFAILновогоconcurrencyтеста:db.info.dsnнамеренноневыдаёт
пароль, второйconnectionнеавторизованвCIpasswordконтуре. Локальныйtrustэтоомаскировал.
Исправленtest-onlyисточникурла: штатныйtest_database_urlfixture, credentialsнепечатаются.
Product/runtimeнеизменён. PG09addressedtest: новыйownedcluster .test-stand/w02-02-pg09,
55503/agent4k_pytest, прежниевладелец/limits/stopfinally; startscriptpg09, evidencepg09.
ПослеPASSтолькоtest/docscommit→тотжеPR222→mandatoryCIновогоhead.
PG09PASS1/0.64s,cleanupstop0/portclosed/postmasterabsent. Product/runtime hashes
неизменны; изменены только2строкиtestDSN и документы/evidence. НовыйCIhead обязателен.

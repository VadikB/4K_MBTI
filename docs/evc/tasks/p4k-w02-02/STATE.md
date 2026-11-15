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

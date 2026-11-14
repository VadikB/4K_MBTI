# REMAIN_02 — проверки и AC

Base `20add5cb1806afde0f5dd052973802b079811f63`; кодовый commit `95edcfa8`; финальный HEAD после документального checkpoint указан в передаче. Финальный набор выполняется на его точном SHA. Во всех строках ниже среда — локальный worktree и синтетические данные. TEST/Prod не изменялись.

| AC | Результат на рабочем diff | Доказательство / граница |
| --- | --- | --- |
| F13-AC01 | PASS локально | unit для 0.2/старого 0.1 CSV/черновика; PostgreSQL manual/new CSV/old CSV/возобновление draft и readiness; actor HTTP/PG подтвердил повтор POST без второго контекста; browser lost-response exact GET. Стоп до подтверждённой редакции и готовности. |
| F13-AC02 | PASS локально | actor HTTP/PG: A внёс, B подтвердил; серверное авторство, чужая область 403/404, сохранённые снимки неизменны; UI автора в browser. Исторические 54 HTTP и четыре снимка используются только для неизменённого происхождения, старые C04/contact ожидания не засчитаны. |
| F13-AC03 | PASS локально в изменённой области | DB: N остаётся effective при N+1 и readiness без C04/contact; browser exact scope и late GET. Не выполнялись назначение/оценка. |
| F14-AC01 | PASS локально | один сохранённый synthetic Report, реальная PostgreSQL SQL + TestClient list/open/PDF для админов A/B/нового C/чужого; customer projection не раскрывает raw trace. Отдельный собственный маршрут участника покрыт существующей HTTP/integration регрессией. |
| F14-AC02 | PASS локально | DB: новый admin получает право сразу, отозванный теряет; прежний Report без access snapshot доступен текущему admin; старые записи не обновлялись. |
| F14-AC03 | PASS локально | template 0.2 и UI не содержат C04/contact/picker; legacy IDs игнорируются; browser DOM/keyboard, 320/390/1440 и текст 200%; системное объяснение доступа в preview/briefing. |

## Команды и фактический итог

- `git diff --check` → PASS (до коммита).
- `npm run lint:js` → PASS.
- `node --test tests/frontend/*.test.mjs` → 272 PASS.
- `npm run build:web` → PASS, `web/dist` пересобран.
- `npm run test:backend` → 1090 PASS / 559 deselected на рабочем diff; после финального коммита повторить на SHA.
- `npm run test:backend:http` → 153 PASS / 13 deselected.
- `TEST_DATABASE_URL=<owned agent4k_pytest> npm run test:backend:integration -- --quiet` → 393 PASS / 9 SKIP / 1247 deselected. Первый запуск с URL через UNIX socket дал 8 FAIL/25 ERROR из-за ограничения `test_stand` на host/name; контрольные тесты и повторный полный запуск с `127.0.0.1`/`agent4k_pytest` прошли. Девять SKIP включают owned stand без `STAND_ADMIN_URL` и real-provider; относящийся к F13 actor owned stand запущен отдельно и PASS.
- `STAND_ADMIN_URL=<owned postgres maintenance> .venv/bin/python -m pytest --run-integration -q tests/integration/test_remarks_questionnaire_actor_owned_stand.py` → PASS, marker-owned DB удалена тестом.
- `TEST_DATABASE_URL=<owned agent4k_pytest> .venv/bin/python -m pytest --run-integration -q tests/integration/test_questionnaire_sources_db.py tests/integration/test_m8_report_access_db.py` → 3 PASS после последних правок.
- Browser: `adm-program-guards` + `questionnaire-draft-guards` → 30 PASS; `auth-r03` адресный набор → 17 PASS; `adm-program-visual` admin confirmed → 1 PASS; `AC18-ADM-1A` keyboard/widths → 1 PASS. Первую попытку browser без escalated окружение отклонило `listen EPERM`; повтор в разрешённом локальном контуре прошёл.
- CI/PR head, TEST backend SHA, visual owner acceptance, Prod → NOT_RUN: нет PR/внешнего выпуска в области этой передачи. Реальные LLM/mail → NOT_RUN по задаче.

## Ограничения и ресурсы

Полный fast browser CI и runtime shard выполняются CI перед merge; локально адресные browser-проверки закрыли затронутый путь. Синтетическая PostgreSQL 15.16 на `127.0.0.1:55432` принадлежит RUN_ID из STATE; её остановка и подтверждение освобождения порта обязательны перед передачей. Никакой общей или пользовательской БД не изменено.

# PATH-START-01 — от новой организации до первого Case

## Результат, основание и область

Статус: IN_PROGRESS. Исполнение начато прямой командой владельца «делаем» с
приложенным заданием редакции 1.3 от 04.11.2026. Файл задаёт требования, а не
самостоятельные полномочия: исторические разрешения/результаты сверяются с Git,
доступными решениями и фактической средой перед зависимым действием.

Вход: `P4K_PATH_START_01_Assignment_to_First_Case_2026-11-04.txt`, SHA-256
`29ada88402576a5cb36a89df12039f1a45bcfc58c41385a733ffef3c7b933749`.
Область: PS-01…05 и AC01…18 — настоящие UI/entry/API/PostgreSQL, новая owned-БД,
точная утверждённая программа, реальные LLM generation/tester/challenger, штатный
admission и первый явный start/предъявление AS при 0 оценочных ответов.
Не входят дальнейшее решение/оценивание/Results, общие purge/transfer/cancel races,
новые методологические нормы, DB-PERSIST-01 и новый выпуск кода без отдельного допуска.

## База и источники

- Новая ветка `codex/path-start-01`, base/fetched main
  `7221671fbd9b16192a86b04b6eec36773f2dbf99`, приложение 2.0.62, PR #167 merged.
  Root checkout имеет три посторонних untracked документа; они не меняются.
- Профиль `assessment-first-case/1.1` и `scripts/assessment_first_case.py` уже в main.
  Принятый 2f0a5a0/ZIP, 49 Python/27 Node, ложный PASS и PASS_WITH_WARNINGS не
  реализуются заново. Однокейсовая synthetic QA fixture не становится источником PATH.
- Переиспользованы неизменённые README/CONTRIBUTING/AGENTS, EVC workflow/matrix/
  artifact recipe/review; прочитаны task-template, ADR-002 C-23/24/34, ADR-003,
  context/Registry/Change01/SourceSet и существующий профиль/runner/seed.
- M1 v1.4 FROZEN/CURRENT=NO, M3/M4 v1.0, M5 v1.1; M7 v1.3 §§2.4/5.1 и начало
  §5.3 прочитаны в `docs/methodology/source-sets/2026-10-01/derived/M7-v1.3.md`.
  План/профиль/два эффективных времени фиксируются до первого старта; календарное
  окно начинается первой Session. M6/M8 — только границы, не новая реализация.
- Прочитаны ARCH30-ADD01 (решение состава от 30.10.2026), PROGRAM01/R03,
  `scripts/plan_specialist_program_release.py`, текущие PATH29 inputs и места
  questionnaire load/readiness/operations/actions/assignment lineage.
- PM-02: роли/контекст/PersonalizedProfile; PM-03: источник/генерация/допуск AS;
  PM-04: план/маршрут/время/start. Фактические LU и изменённые потребители уточняются
  по найденному разрыву, а не назначаются будущей модели заранее.

## Первая разведка и зависимости

В root обнаружены отдельные пользовательские документы публикации
`docs/evc/tasks/program01-test-recovery-2026-11-04.md` и safe receipt рядом в
`docs/evc/evidence/`. Они сообщают о выполненной публикации, а не NOT_RUN:
`specialist_pilot@1.1`, program DB ID 1,
checksum `07576484b6c6467fd5fc7047cb1686a2f952532a893660375984373bab87f58c`;
configuration `specialist_pilot_v1` ID 11; catalog `specialist-pilot@1.0` ID 2,
checksum `0008d020cbeb8b06ef5d38ad1eaf136fab8dc42728d98c2d5ec275476a6c25a0`;
`specialist_expert@1` ID 2, checksum
`c5c2234f9fdd237e14024ea6939e3bc5561fd27bf4fac416a52196dec79cbe8f`.
Это пока входное свидетельство отдельной операции, не новый PATH readback.
Повторная публикация запрещена до сверки существующего результата; неизвестные
текущие IDs/target/QA не угадываются. UI readback постоянного test пока не доказан.

Исторический PREP-DIAG-01 сохраняется UNKNOWN. Новый run не реконструирует его
checks. Сначала сохраняется исходный разрыв целевого пути, затем исправления и
отдельный полный повтор на конечном SHA. Published определения не переписываются.

## План и состояние

1. Активно: read-only сверка test/публикации/QA/release refs и DB target/ownership;
   обновление текущего handoff/STATE. Не создавать конкурирующую программу.
2. Адаптация существующего runner/seed/assertions к exact nine-case release;
   минимальный bootstrap, безопасные terminal export/completion/cleanup. Без готовых
   org/admin/member/questionnaire/assignment/profile/AS/start в начальной загрузке.
3. Исходная диагностика PS-01…05 и отрицательные UI/HTTP/DB проверки: сохранить первый
   разрыв до исправления соответствующего продукта; независимые части не блокировать.
4. Адресные исправления PG-R1/R2/R3, ST-R1/R3/R4 и связанных замечаний только при
   подтверждённом текущем поведении; регрессии; не переделывать R01/R02/R03/R10.
5. Полный итоговый run на новых owned-данных, уровни проверок/evidence/остаток в
   таблице ниже; draft PR после локального минимума. Deployed acceptance отдельно.

## Флаги, стоп-условия, безопасность и откат

`branch_push=true` после локальных проверок, `pr=true` для одного результата;
`merge=false`, `deploy=false`, `version_bump=false`, `artifact_publish=false`
для PATH. Прежняя публикация целевой программы — отдельное основание; её готовый
результат переиспользуется, не производится новая нормативная публикация.

Восемь стоп-условий EVC: (1) новый смысл — нет; (2) несовместимый API/схема —
пока нет, при необходимости анализ/решение до реализации; (3) миграция/чужое
удаление — нет; (4) источник — зависит от точного readback, запрещает только
зависимый seed/run при mismatch; (5) новый контур — нет; (6) новые права/передача
PII — нет, запрещены; (7) отсутствие отката — нет; (8) выход за область — нет.
Новый методологический конфликт не решается prompt/fallback/смягчением admission.

Не читать/выгружать секреты и пользовательскую историю. Только служебный release
metadata readback постоянной БД; все автотесты/прогоны — owned test/pytest DB.
Перед записью проверяются фактические target/marker; cleanup только своей БД,
без FORCE и после terminal fsync/readback. Running/ошибка export сохраняют DB/state.
Откат: адресный revert кода без потери bindings/snapshots; disposable cleanup отдельно.

## Проверки

Применимый минимум: backend/unit + HTTP; настоящая isolated PostgreSQL для
атомарности/повторов/assignment lineage; frontend regressions/lint/build/dist при
изменении frontend; browser 1440/320/390/768 и ровно обоснованные real-provider runs.
Обязательный CI относится к новому окончательному head. Платный прогон не повторяется
на каждой ширине или ради случайного PASS. Нормы retry/repair не расширяются.

## Единая матрица AC01…18

До фактических проверок статусы не заимствуются из SYN/PR #167.

| AC / PS и источник PATH 1.3 | Реализация/путь/SHA | Проверка/run/подмены | Evidence | Статус / остаток / владелец |
| --- | --- | --- | --- | --- |
| AC01 / все: minimal bootstrap, ownership | Existing stand/seed, target delta pending | NOT_RUN | — | NOT_RUN; точный source seed, архитектор |
| AC02 / PS-01: org create/reload/repeat | UI/entry/API, 7221671 | NOT_RUN | — | NOT_RUN; основной run |
| AC03 / PS-01: approved program/catalog/roles | Existing release receipt; current readback pending | NOT_RUN | Root publication receipt (не PATH) | NOT_RUN; проверить exact refs/QA |
| AC04 / PS-01: exact connection GET/reload | R10 существующий, 7221671 | NOT_RUN | — | NOT_RUN; не переделывать без дефекта |
| AC05 / PS-01: slow/error/null/foreign/lost reply | Entry/dist + HTTP | NOT_RUN | — | NOT_RUN; отрицательные сценарии |
| AC06 / PS-01: admin own scope/auth | Existing auth/routes | NOT_RUN | — | NOT_RUN; browser + HTTP |
| AC07 / PS-02: confirmed scope/revision/read states | questionnaire sources + renderer | NOT_RUN | — | NOT_RUN; PG-R2 |
| AC08 / PS-03: member/job/BaseRoles | Existing R01/source capabilities | NOT_RUN | — | NOT_RUN; 6 ролей/пилот |
| AC09 / PS-03: atomic assignment/idempotency | Existing assignment/bindings | NOT_RUN | — | NOT_RUN; HTTP/DB |
| AC10 / PS-03/04: exact denial/rollback | Readiness/binding routes | NOT_RUN | — | NOT_RUN; PG-R1 |
| AC11 / PS-04: participant-owned identity | Existing auth/ownership | NOT_RUN | — | NOT_RUN; browser/HTTP |
| AC12 / PS-04: acquaintance persistence/reasons | Existing auto-trigger/R03 | NOT_RUN | — | NOT_RUN; не подставлять ответы |
| AC13 / PS-04: frozen profile/provenance/no PII | PM-02 → C-23/24 | NOT_RUN | — | NOT_RUN; DB/trace |
| AC14 / PS-04: real LLM/admission/UI; PREP-DIAG | PM-03 → C-34; strict validator retained | NOT_RUN | Historical PREP remains UNKNOWN | NOT_RUN; новая адресная диагностика |
| AC15 / PS-03/04: assignment/job lineage | Admin projection + participant path | NOT_RUN; technical negative fixture planned | — | NOT_RUN; ST-R3 |
| AC16 / PS-04/05: plan/time before explicit start | M7 §§2.4/5.1, start gate | NOT_RUN | — | NOT_RUN; no calendar window yet |
| AC17 / PS-05: start/same AS/zero answers/repeat | Cycle/Session/AS + browser | NOT_RUN | — | NOT_RUN; full final run |
| AC18 / все: final SHA/full run/viewport/evidence | Existing runner, adapted source selection | NOT_RUN | — | NOT_RUN; code/main/CI/deploy отдельно |

## Checkpoint источников и runner (до изменения продукта)

Read-only текущего test подтвердил описанные program/config/catalog IDs/checksums,
SHA 7221671, target `agent4k_test` через host port 55432 (внутри PostgreSQL 5432).
Receipt `tests/browser/fixtures/path-start-release.json` содержит девять Cases,
27 оригинальных QA JSON/checksum, owner decision, runtime refs; не содержит users
или историю. Независимая проверка JSON и воспроизведение admitted package совпали.
Новая публикация не выполнялась. `tests/path_start_release_source.py` выполняет
только SELECT в READ ONLY transaction; проверка identity/checksum fail-closed.

Existing runner получил `--program-source published-pilot`; legacy diagnostic default
сохранён. Target seed импортирует exact approved package и неизменённые QA origins,
сверяет IDs/checksums и только затем создаёт техническое mirror ProgramDefinition.
Это не новый human review/методологическое согласование. Минимальность дополнительно
проверяется в owned bootstrap. Продуктовые Api/web на этом checkpoint неизменны.

Локальный минимум: backend 743 PASS / 318 deselected; HTTP 106 PASS / 12 deselected;
Node receipts 27 PASS; frontend 131 PASS; lint/build/diff PASS. Первый запуск backend
имел 9 ошибок из-за неверного пути новой fixture; путь исправлен, адресный повтор
9 PASS и весь набор 743 PASS. К продукту/историческому INCOMPLETE это не относится.

Следующий шаг — owned bootstrap и исходный UI run: негативный GET уже подтверждённой
анкеты проверяется до LLM. Это ещё не PATH PASS и не итоговый кандидат.

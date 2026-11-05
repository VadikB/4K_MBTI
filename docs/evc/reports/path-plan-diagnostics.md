# PATH-PLAN-01 — результат бесплатной диагностики

05.11.2026. **Доработка диагностики проверена; полный PATH не PASS.**
Продукт, validator READY-only, методология, опубликованные пакеты, admission,
repair и постоянная БД не изменены. Новых LLM-вызовов — 0.

Возобновление05.11 после остановки: направление ограниченного пилота на девяти
Cases, полный M2 остаётся61; расширение каталога исключено. Дополнительный поиск
нашёл прежние ARCH-A05/PILOT-120 и ARCH30-ADD01, поэтому раннее NOT_FOUND ниже
относится к тогда просмотренному комплекту, а не к отсутствию любого основания.
Применимость и конкретный **неутверждённый** проект —
[PATH-PILOT-01](path-pilot-admission-proposal.md). Исторический run не переигрывается.

## Реализация и идентичность

Runtime/main base `2dc98c6b5b2637c6c505a90686e82f5e4274e763` / 2.0.64.
Отдельная ветка `codex/path-plan-diagnostics` от отчётного
`b5b7ba34c66f8bb2fff97d78730bb81661549e9a`. Implementation commit
**`1bc9d36834262ee9ad4591227d5ec876fea8e648`**; последующие изменения —
только отчёт, наблюдение/evidence и их offline verifier, не исполняемый collector.
Старые ветка/ZIP/receipts не переписаны. Root main с тремя чужими untracked
документами сохранён. Diff `Api/`, `web/`, `assessment_definitions/`, `scripts/`
и обоих browser persistence/admission validators относительно main пуст.

Изменения tests-only:

- `tests/assessment_first_case_evidence.py`: чтение saved latest revision; отдельный
  allowlist целей/пробелов/route/catalog eligibility/reasons/времени/source refs.
- `tests/path29_browser_app.py`: настоящий handler делегирует чтение этому helper.
- `tests/unit/test_assessment_plan_receipt.py`: десять checks статусов, ссылок,
  hashes, исключения неизвестных полей, UNKNOWN/PARTIAL и durable persistence.
- `tests/integration/test_m7_cycle_planner_db.py`: настоящий PostgreSQL readback
  второй revision, включая exact source hash и file persistence через общий Node helper.
- Профиль и tests/README: описание нового evidence и сохранённых ограничений.
- `RUN_FREE.py`: воспроизводитель проверки через существующий test_stand,
  не новый runtime подготовки. `OBSERVE_READINESS.py`: только наблюдение проекций.

`content_checksum` сравнивается только с hash исходного saved content;
`diagnostics_checksum` — с hash экспортированной проекции. Разные объекты не
обязаны иметь одинаковый hash. Полный raw snapshot не выдаётся за экспортированный:
`snapshot_export=ALLOWLISTED_DIAGNOSTIC_PROJECTION`. UserContext/ответы/контакты,
сырые prompts/responses/ключи и произвольные новые поля в него не копируются.
Отсутствие исходника или обязательных диагностических полей явно UNKNOWN/PARTIAL.

## Что установлено по READY / LIMITED

Источники и стоп-условия — в [задаче](../tasks/path-plan-diagnostics.md).
Использованы M7 v1.3 §§2.2/4.1–4.6/5.1, M1 v1.4 FROZEN/CURRENT=NO,
Change 01, ADR-002 C-24/C-34/C-46, M7 Cycle Planning v1 (draft QA), исходная PATH 1.3,
exact published-pilot fixture и действующий код main. Хеши просмотренных реализаций
и источника сохранены в `readiness-observation.json`.

| Слой | READY | LIMITED | NO_ROUTE |
| --- | --- | --- | --- |
| Планировщик | Нет uncovered IDs | Есть маршрут и uncovered IDs | Маршрута нет |
| Admin projection, prepared/admitted AS | ready_to_start | start_blocked | start_blocked |
| Participant preparationView, positive times | ready | ready при непустом route | plan_missing при пустом route |
| PATH validator с lineage | При остальных checks допускает | PLAN_NOT_READY | PLAN_NOT_READY |

Матрица UI/admin проверена вызовом настоящих чистых функций на синтетических
входах, не скриншотом действующего участника. Исторический receipt снова отклонён
неизменённым validator с PLAN_NOT_READY. В `start_prepared` и `present` нет отдельного
запрета по строке LIMITED; остаются owner/assignment/profile/revision/AS admission/time
проверки. Это статическое наблюдение, **не** фактический отказ или успех HTTP start
для исторического run. Новый HTTP start того run не выполнялся.

M7 не задаёт буквальные enum READY/LIMITED; требует допустимый начальный маршрут,
состав M2 и предварительное обоснование сокращённого состава. Известные ограничения
условных ветвей не равны автоматическому разрешению любого неполного маршрута.
Явного решения о таком составе specialist_pilot@1.1 в просмотренных материалах
не найдено. Case QA/решение о допуске отдельных Cases не заменяет это решение.
Поэтому нельзя выбрать удобное поведение UI/сервера как норму или объявить READY
ошибкой harness без дальнейшего основания. Старт/гейт не изменялись.

Статический аудит exact девяти Cases: full M2 targets61, union39, как минимум22
пробела. Это не реконструкция удалённого frozen plan. Его точные прежние
route/catalog reasons/uncovered IDs остались UNKNOWN; новый synthetic receipt
не приписывается прошлому платному запуску.

## Реальный SQL, сохранение и cleanup

На clean detached **1bc9d36** существующим private test venv выполнено:

```sh
python docs/evc/evidence/path-plan-diagnostics/RUN_FREE.py --directory <new-private-directory>
```

`STAND_ADMIN_URL` передаётся защищённым процессом в памяти, только localhost
maintenance postgres:55432; секрет не печатается. Из дочернего окружения исключены
все provider keys и рабочая DB-конфигурация. Обычный test_stand create/destroy,
`gateway=0`, `provider=disabled`, новая пустая БД с точным owner marker.

Run **43d5ca0ac39e4b098ef5e7ea4d8829bc**, БД
`product4k_pytest_43d5ca0ac39e4b098ef5e7ea4d8829bc`. Сохранены:
run, regression-result, export-before-cleanup, plan-receipt, cleanup, pytest.log.
Revision2 / LIMITED с сохранёнными targets/gaps/catalog reasons прочитана actual SQL;
Node persistence сделал fsync/readback. До destroy проверено существование owned-БД;
после — database_absent/state_absent=true и тот же файл побайтно. Без FORCE.
SHA-256 receipt:
`98a0531241a715d5692f68946d76e039676ee7afcb79db4052cc4e5e95603d6e`.

Все 43 selected integration tests PASS: весь M7 planner, parameter resolution,
существующий product explicit-start test и прежняя actual collector negative export
regression. В последней свой отдельный owned lifecycle, также без LLM.
QA evidence/FROZEN Cases этих fixtures — **синтетические тестовые подстановки**,
не human review, методологическое согласование или допуск целевого пилота.

## Проверки и применимость

| Команда / область | Результат | Основание |
| --- | --- | --- |
| pytest -m 'not integration and not e2e and not llm' -q | 773 PASS / 324 deselected | implementation1bc9d36, backend.log |
| pytest -m e2e tests/e2e -q | 108 PASS / 12 deselected | тот же code, http.log |
| Три адресных harness Python suites | 48 PASS | targeted-python.log |
| Node receipt persistence + preparation validator | 38 PASS | node.log, сам validator неизменён |
| RUN_FREE.py, real PostgreSQL | 43 PASS, exit0 | free-sql/pytest.log и primary JSON |
| OBSERVE_READINESS.py | PASS после исправления fixture assignment_id | readiness-observation.json, start/LLM0 |
| Старый VERIFY.mjs в неизменённом b5b7ba3 worktree | PASS_OFFLINE_EVIDENCE_AUDIT | Старый PATH остаётся FAIL_PLAN_NOT_READY |
| Diff / self-review / локальные ссылки | PASS | Нормы/продукт не менялись |

Первоначальные 7 unit FAIL до helper — TDD отсутствующей возможности экспорта,
не доказательство причины старого INCOMPLETE. После добавления дополнительных
checks текущих новых unit10. Известный FastAPI/httpx deprecation warning сохранён.
Попытки local initdb (libpq без postgres) и Docker socket не дали test-БД и не
заявлены integration PASS. Неверная проба внутреннего health-порта вернула curl7;
она не доказательство сбоя сервиса: public test readiness успешно ready.
Browser/новый платный PATH NOT_RUN: поведение UI/продукта не менялось; затратный
прогон не нужен для этой доработки и не разрешён. CI новой ветки NOT_RUN, PR нет.

## Состояния, передача, ограничения

| Объект | Состояние |
| --- | --- |
| Ветка | Local-only codex/path-plan-diagnostics, implementation1bc9d36 + docs/evidence |
| Новый CI | NOT_RUN; локальные проверки не заменяют CI перед будущим merge |
| Main | 2dc98c6 / 2.0.64; новый collector автоматически не получил |
| Развёртывание test | Тот же SHA, tracked clean, service active, public readiness ready; нового deploy нет |

Предыдущие выпускные [fast CI](https://github.com/VadikB/4K_MBTI/actions/runs/41905225749),
[full CI](https://github.com/VadikB/4K_MBTI/actions/runs/41905225698) и
[deploy](https://github.com/VadikB/4K_MBTI/actions/runs/41906112154) относятся к 2.0.64,
не к этой ветке. Все новые release flags false. Откат — revert tests-only изменения;
схема/данные/история не мигрировали, permanent cleanup guard сохранён.

Новая база с усиленной диагностикой — implementation1bc9d36 этой ветки, а не
автоматически main. Исходный профиль/runner уже есть в main2dc98c6, но не это
дополнение. Offline `VERIFY.py` и MANIFEST обеспечивают независимую проверку
переданных файлов; их PASS обозначен NOT_PATH. Секреты/state/raw logs провайдера
в пакет не входят; первичные файлы выгрузки сохранены отдельным allowlist.

Исторический [run96abd1…](path-start-2dc98c6-run.md): LLM/admission PASS, AS saved,
repair не использован, start/presentation NOT_RUN, ответы0, owned cleanup PASS.
PREP-DIAG-01 остаётся UNKNOWN, не объясняется этой доработкой.

Последнее поручение владельца05.11 заменяет промежуточный выбор расширения каталога:
**ограниченный пилот на девяти существующих Cases при неизменном полном M2=61**.
CAT-COVERAGE-01 не исполнялась и теперь SUPERSEDED_NOT_STARTED. Исходный незакоммиченный
diff относительно de3b831 и отдельный draft сохранены в двух resume-*.patch.gz
с проверкой checksum распакованных bytes; текст diff не «исправлялся» ради whitespace.
Они не являются ни прежним, ни новым методологическим допуском маршрута.
Новый PATH-PILOT-01 содержит восемь позиций-кандидатов/39 предлагаемых целей,
матрицу61/55 проектных возможностей, условные ветви и22 отсутствующие цели отдельно, источники,
тайминг PILOT-120 и точный перечень решений P1–P3/M1–M4/T1/R1.
Проект DRAFT_FOR_REVIEW, approvals=PENDING, runtime_authorization=NONE.
READY/admission не ослаблялись. Дальнейший PATH AWAIT_SPECIFIC_PLAN_APPROVAL,
а не blanket-допуск LIMITED. PREP-DIAG-01 по-прежнему отдельно UNKNOWN.

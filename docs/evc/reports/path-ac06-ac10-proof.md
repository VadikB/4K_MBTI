# AC06/AC07/AC09/AC10 — завершение бесплатных доказательств

06.11.2026. Технический результат: четыре AC **PASS** в заданном HTTP/PG scope.
AC18 **NOT_RUN**, подготовлен [конкретный план](../tasks/path-ac18-final-plan.md).
Это не человеческая приёмка всего PATH и не новый real-provider PASS.

## SHA и независимые состояния

- Fresh main/origin-main: `3f42bba992e1a556e1961ca4abdaa0954a367153`,2.0.69,
  tree `23f065e1c8827a141a48c57fb97b6b4251439e6c`.
- Кандидат инструмента, на котором повторены адресные проверки:
  `2a868e5f909b0493e1e3b936e5407b07c73e811a`, `codex/path-ac06-ac10-proof`.
  Финальный handoff commit добавляет только отчёт/evidence/состояние; точный SHA
  и byte hashes находятся в `code-identity.json` переданного пакета.
- Api/web/dist/assessment_definitions/CI/schema/metadata продукта: **без diff** к main.
  Менялись tests/runner identity/profile/инструкции и документация. Bump нет:
  унаследованная2.0.69 в кандидате не обозначается новым выпуском.
- CI кандидата: **NOT_RUN**, push/PR не разрешены. Старый CI2.0.69 не выдан за новый.
- Main и deploy не изменялись. Последний подтверждённый test —3f42bba/2.0.69,
  закрытие [PR174](https://github.com/VadikB/4K_MBTI/pull/174#issuecomment-6681555673).
  В этом задании нового deploy/server readback нет; AUTH/R10 не переоткрыт.
- Отдельный worktree; три прежних untracked документа корня/прочие ветки сохранены.

## Применимость прежних доказательств

Прочитаны пути/версии из [карточки](../tasks/path-ac06-ac10-proof.md), ADR-003,
pilot-plan-start-admission-contract v1; аудит2.0.68 и PATH1.3 не использованы как
доказательство нынешнего дефекта. Закрытые позднее AUTH/R10 учтены.
Ранее questionnaire_sources_db подтверждал stale/foreign SQL, membership_db — lock,
path29_owned — реальный HTTP/SQL. Fake adm27 Assignment Connection/resolver не
зачтены как атомарность. В новых admin checks нет подмены успешного resolver,
readiness, authorization или Connection; настоящие router/cookie sessions/PostgreSQL16.

Change01 И-6 права/повторы → ADR-003/scoped questionnaire+assignment →
`routes._require_superadmin/_require_organization_admin`, questionnaire.confirm,
assessment_programs.resolve, assignment_sources.record_operation/bind → новые
HTTP/PG regressions. M1 v1.4 FROZEN/CURRENT=NO, полный M2 и границы PM не менялись.

## Критерии и первичное evidence

Основной [индекс](../evidence/path-ac06-ac10-proof/evidence-index.json) связывает
адресные HTTP/PG receipts, browser SQL-readback, component-only кадры и cleanup.
Проверяемые исходники входят в пакет; [offline CHECK](../evidence/path-ac06-ac10-proof/CHECK.py)
не обращается к БД/LLM. Все snapshot hashes сравниваются с тем же объектом до/после,
не с хешами разных сущностей.

| AC | Факт | Доказательство / остаток |
| --- | --- | --- |
| AC06 PASS | Ordinary admin PUT program своей/чужой org:403. Foreign PATCH, members POST/DELETE, admins, domains POST/DELETE, questionnaire preview, assignment:403. Ни одна предметная строка не меняется | 10 actual HTTP отказов и SQL hashes/counts до/после. User/cookie/admin scope реальны; не UI-only |
| AC07 PASS | Новая correct revision подтверждена HTTP200 и SQL context/version. Superseded неподтверждённая revision:409 REVISION_CONFLICT; реальная foreign revision через свою org:409 NOT_FOUND; через foreign URL:403. Exact replay не создаёт второй context/access revision | Actual HTTP + SQL, точные revision1/2/3 и context refs в receipt; не реконструкция старой удалённой БД |
| AC09 PASS | Same-key и different-key конкурентные HTTP, lost delivery/retry/new key/readback дают одну assignment/binding,0 Cycle. Реальный UI dblclick:1 POST. route.fetch committed200 → abort ответа → reload/retry: прежние2 assignment/binding,0 Cycle | PostgreSQL unique+locks, реальные sessions, browser events+SQL. Поздний domain409 и PG500 откатывают весь batch/operation; nontransactional sequence доказывает достижение SECOND binding после FIRST. Дополнительно component-only повтор при existing Cycle оставляет1/1/1/1 |
| AC10 PASS | Retired/absent/draft program connect:409 PROGRAM_NOT_AVAILABLE. Assignment retired program, disallowed role, foreign catalog scope, assignment-ref mismatch, missing/incomplete questionnaire, source-selection override: точные409 без частичных предметных строк | 8 source/scope cases +3 connect negatives. Foreign recipient — предусмотренный200 item not_assigned, нет assignment/binding/Cycle для него; технический operation receipt допустим. Правила batch не изменялись |
| AC18 NOT_RUN | План single real-provider PATH, pinned1.2, same AS на4 ширинах,0 answers и cleanup. Нужны отдельные release и paid-run разрешения | Кандидат инструмента локальный; окончательный deployed SHA определяется после разрешённого выпуска |

Основной child suite: **18 PASS**,31 event,25 no-write denial,3 race/repeat modes;
snapshot проверяет20+ domain tables, не только число assignments. PG16.15,
READ COMMITTED. После suite Cycle/AS/prepare jobs/product operations/lab/equivalent
generation rows —0, provider/mail credentials отсутствуют. Писем и LLM нет.

## Дефекты и изменения

Подтверждённых дефектов продукта в четырёх проверенных критериях **не найдено**.
Поэтому Api, транзакции, права, схема и продуктовые источники не менялись.

Новые fixtures/collector доведены с сохранением отрицательных попыток:

| Ожидание → факт | Причина / исправление | Повтор |
| --- | --- | --- |
| foreign member403 →422 | Новый fixture не передал обязательный role_description; добавлено валидное поле, чтобы дойти до guard | 403/no-write PASS |
| Confirm replay context ref →KeyError | API намеренно не отдаёт внутренний context id; проверка перенесена в настоящий SQL readback, не расширен публичный API | HTTP+SQL PASS |
| late domain rejection →fixture NOT NULL error | Неполная synthetic confirmation; создан собственный профиль/контексты second user и полные confirmed inputs | Второй bind409, полный rollback PASS |
| Browser selection/status →strict locator/class mismatch | Новые test selectors: несколько checkbox и data-tone вместо CSS class; исправлены selectors | Actual browser AC09 PASS |
| Superadmin/default screen и shared context →hidden panel | Явная штатная навигация; separate contexts вместо ручной замены cookie в прежнем UI/localStorage | Super/admin contexts PASS |
| Viewport geometry после resize/scroll →отрицательные измерения | Raw DOM scroll заменён actionability API, measurements на активной странице, trial без click; причины конкретных старых IO timing не объявлены продуктовым дефектом. Failure metrics/PNG сохраняются до cleanup | Новый строгий collector и обе browser regression PASS, assertions не удалены |

Найден и закрыт именно **пробел будущего AC18 evidence**, а не отказ admission:
старый runner снимал первую AS только1440. Новый helper собирает5 screen phases ×
4 widths без prepare/start/ответа на каждой ширине. Важные controls, overflow,
длинные данные и screenshot review; original W02 шестиширинный/zoom тест сохранён.
Первый успешный component-run с двумя controls не выдан за полный новый контроль;
окончательный проверяет также home/pause/finish и post-start repeat assignment.

## Команды и результаты

Стерильное окружение, PYTHON_DOTENV_DISABLED=1/PYTHONPATH=., DB_POOL_MIN_SIZE=0,
DB_NAME=unused/DB_PORT=1 для обычных тестов. Реальные integration URL указывали
только новый контейнер `4k-ac0610-pytest-20261106`, localhost59669; never working.env.
Python3.12.13, Node25.5.0, Playwright1.63.0/Chromium1243. Полные commands — профиль,
tests/README и task; стандартные npm backend команды эквивалентны ниже.

| Команда | Факт и применимость |
| --- | --- |
| `python -m pytest -q -s --run-integration tests/integration/test_path_admin_contract_owned_stand.py` | На source SHA2a868e5: outer1 PASS + child18 PASS; отдельная новая owned-БД, первичные receipt до cleanup |
| `python -m pytest -m 'not integration and not e2e and not llm'` | 921 PASS /354 deselected; повтор на source SHA, JUnit backend.xml |
| `python -m pytest -m e2e tests/e2e` | 108 PASS /12 deselected, повтор на source SHA; JUnit http.xml |
| `python -m pytest --run-integration -m 'integration and not llm'` | 240 PASS /1034 deselected,0 skip;996s. Читал ту же окончательную Python/Api ветку; затем source commit без изменения этих bytes. Targeted wrapper повторён на SHA; JavaScript collector не подменяет этот PG набор. JUnit integration.xml |
| `npx playwright test tests/browser/path-admin-contract.spec.mjs tests/browser/path29-participant.spec.mjs --workers=1` | 2 PASS,0 retry/skip/flaky, повтор на source SHA; actual PG browser + отдельно component-only PATH. Новый JSON и PNG, не старые129 PASS |
| `node --test tests/frontend/*.test.mjs` |145 PASS, runtime web bytes не менялись |
| `npm run lint:js`, `npm run build:web`, `git diff --check` | PASS;45 rebuilt assets идентичны main, без web diff. Node syntax checks трёх новых/изменённых browser файлов PASS |

Deprecation warnings httpx/Starlette и psycopg pool open зафиксированы; не suppress,
не продуктовые ошибки задачи. Full CI и платные llm tests NOT_RUN по границе.
Первый staged diff-check отказал из-за trailing whitespace в сырых negative
pytest/Playwright logs. Hook не обходился: исходные bytes упакованы в gzip без
редактирования и доступны для восстановления; затем diff-check повторён.

## Синтетика, cleanup и ограничения

Новый admin suite использует существующий E10.2 seed: **техническое моделирование
исходного QA**, не подтверждение real human review/целевой pilot admission. Его
историческое поле origin=human_review с controlled-test actor не выдаётся за
человеческий review. Опубликованные версии Git/рабочей БД не менялись. Отдельный
бесплатный PATH29 component fixture имеет явную upstream plan подстановку; запрещён
для real/full PATH. В новых AC06/07/09/10 решениях никаких upstream success mocks.

Каждый run сохранил receipt/log/SQL readback перед штатным marker-guarded DROP DATABASE
без FORCE. Контейнер создан только этим заданием; перед его удалением проверены
label/ID,0 owned БД/соединений. Удалены лишь временные synthetic test данные;
восстановление их не требуется, evidence сохранено. Рабочая БД/старые контейнеры
не использовались. Offline CHECK/пакет имеют отдельные checksum manifest.

Денежный/token cap у нынешнего runner не гарантирован; одно разрешение run не
означает бесконечные ручные повторы. Точный provider/stages/transport/repair план
и негативная ветка без AS/start — в AC18 plan. PREP-DIAG-01 исторический UNKNOWN;
его root не объясняется ни новым тестовым coverage, ни исправлениями harness.

## Выпуск, откат, следующий шаг

Push/PR/merge/deploy/version_bump/artifact_publish/paid_llm — false.
Нужен отдельный допуск выпуска **этого harness-кандидата**, не повтор AUTH/R10:
штатный preflight, согласованный PATCH (возможный следующий2.0.70, пока не назначен),
PR/mandatory CI/human review; merge/test отдельно, затем server/readback.
После фиксации окончательного deployed SHA — отдельное разрешение одного AC18 run.
Публикация/активация новой программы не требуется; pinned1.2 уже существует.

Миграций/новых предметных артефактов/API изменений нет. Откат — revert только
локальных task commits; сохранённые данные не затронуты. Конфиг/безопасность:
секреты не экспортированы, permanent DB cleanup guard не изменён. Делегирования нет.

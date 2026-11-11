# F02 — Проверки и границы доказательств

Дата: 11.11.2026. Base/main `748be43e55587aa3b7e3a3945189c5ac737f59eb` / 2.0.97.
Финальный code SHA: `15232259d5915d564c7c9551dd80941862c3cd9a`.
Все финальные проверки ниже запущены после этого коммита; runtime не менялся.
SHA-256 изменённых файлов и исходной карточки: `evidence/code-manifest.json`.
Это отчёт локальной передачи. Новый допуск/кандидат/CI/main/TEST отслеживаются
отдельно в [RELEASE.md](RELEASE.md); история локальных флагов ниже сохраняется.

## Финальные результаты

| Проверка на code SHA | Результат | Evidence |
| --- | --- | --- |
| Backend unit | **1086 PASS**,45.27s | `evidence/backend.log` |
| HTTP contracts | **144 PASS**,10.16s | `evidence/http.log` |
| Frontend | **261 PASS** | `evidence/frontend.log` |
| JS lint/build, byte-identical dist | **PASS** | `evidence/lint.log`, `build.log`, clean runtime diff |
| Actual F02/recovery/layout browsers | **3 PASS**,51.9s | `evidence/browser-summary.json`, `browser.log` |
| Полный integration, empty marker-owned PostgreSQL/UTC | **385 PASS**,2 SKIP,276.03s | `evidence/integration.log`; SKIP только explicit real LLM |
| Независимый code review | **PASS**, новых actionable findings нет | scope UPDATE/INSERT + auth/receipt/trigger review |
| Diff-check, локальные task links, fresh main fetch | **PASS** | source SHA/проверенные пути; main прежний748be43 |

## Данные и независимость проверки

Новый собственный PostgreSQL16.15 (Homebrew), localhost55502, test-role
`p4k_f02_owner`. Каждый browser/HTTP harness создаёт новую БД
`product4k_pytest_<run_id>`, проверяет comment ownership marker до доступа/cleanup
и независимо подтверждает отсутствие БД после DROP без FORCE. Пароли, cookies
и raw tokens остаются в памяти или закрытом временном state, в evidence не входят.
`.env`, рабочая БД, реальные письма и paid LLM не используются.

Основной browser fixture создаёт отдельные ordinary member и admin+member,
действующего org-admin, чужого участника/последнего администратора, own member
с чужой атрибуцией и прежнюю inactive запись. Для двух удаляемых целей сохраняется
синтетический граф profiles → assignment → active Cycle/Session/AS → Dialogue,
C46/calculation/Results/Report и queued preparation. Это fixture удаления, не
пройденная оценка и не методологическая приёмка. SQL readback проверяет заранее
сохранённые точные первичные ключи и ownership columns, не вызывает purge planner.
Контрольные users/organizations сравниваются до/после целиком в выбранных полях.

## Критерии карточки

| ID | Ожидаемый результат / проверка | Фактический результат на финальном code SHA | Evidence |
| --- | --- | --- | --- |
| F02-AC01 | Уполномоченный UI click удаляет обычного и admin+member вместе с обеими функциями и графом, controls сохранены | **PASS**;18 отрицательных table checks, чужие данные сохранены | `evidence/ac01-03-04-05-browser/events.json` |
| F02-AC02 | Старые cookies/invitation/magic/action, late worker и повтор email не восстанавливают аккаунт/историю | **PASS** owned actual HTTP/PG; cookie401, magic/action/register/reset400, invitation404, новый id; worker/FK отказ;4 concurrent auth cases и positive register/reset | `evidence/ac02/checks.json`, `cleanup.json` |
| F02-AC03 | Потерянный ответ после commit/reload и ошибка storage после200 сохраняют ту же операцию/известный результат | **PASS** actual browser+HTTP/PG: storage setItem cleanup failure реально сработал; retained operation после reload; lost-before/lost-after commit; один receipt, новый preview отсутствует | основной browser events; `evidence/recovery-browser/events.json` |
| F02-AC04 | Явные отказы без partial changes: foreign organization/недостаточные права/configured/self/last-admin | **PASS** browser explicit403/409; scope UPDATE/INSERT races воспроизведены/исправлены,50 адресных тестов и полный integration PASS | основной browser events; `test_purge_test_organization_db.py`, `test_account_delete_person.py` |
| F02-AC05 | Нет exclude/restore/transfer UI/API scenario, новая сессия не видит удалённых | **PASS**: API не содержит excluded/detached, legacy DELETE410 без mutation, новая сессия и независимый SQL readback | основной browser events; frontend261; legacy owned HTTP |

## Промежуточные общие проверки

- `npm run test:backend` с `PYTHON_DOTENV_DISABLED=1 DB_POOL_MIN_SIZE=0`:
  1081 PASS, 526 deselected, 38.03s до последней concurrency correction.
- `npm run test:backend:http`: 144 PASS, 12 deselected, 9.91s.
- `node --test tests/frontend/*.test.mjs`: 261 PASS; lint/build PASS.
- Actual recovery browser1 PASS19.2s; основной F02 browser1 PASS20.4s;
  layout12 states1 PASS8.9s, affected auth/layout browser5 PASS.
- Первый полный integration: **FAIL** —357 PASS/6 FAIL/13 ERROR/2 SKIP.
  Ошибка среды: reference предварительно bootstrap вместо требуемой пустой схемы;
  timezone нового local test-role Europe/Moscow вместо UTC. 3 SQL-extraction tests
  дали StopIteration в сочетании полного прогона. После выбора новой marker-owned
  empty reference и UTC все19 затронутых queue/M3/lineage/auth tests PASS6.12s.
  Отдельный устаревший PATH29 tail ожидавший exclude200 обновлён на410/no mutation;
  owned PATH291 PASS4.41s. Код продукта ради этих fixtures не ослаблялся.
- Backend final targeted перед INSERT-closure correction:47 PASS
  (21 PostgreSQL integration +26unit); UPDATE race воспроизведён до исправления,
  после исправления concurrent writers блокируются, stale CTID даёт отказ до intent.

После промежуточной истории код стабилизирован и закоммичен. Финальный полный
набор на `1523225` прошёл целиком:385 PostgreSQL tests PASS, включая прежние
queue/M3/lineage/auth failures и обновлённый PATH29. Сочетание проверено на
неизменном source; временные результаты первого запуска сохранены как история.
Code review отдельно проверил closure при INSERT-before-parent-pin и controls.

Собственные browser/HTTP и reference БД удалены с marker/absence proof.
Независимый readback показал0 оставшихся test databases. Собственный PostgreSQL
остановлен. Evidence — `evidence/*/cleanup.json`, `intermediate-cleanup.json`,
`postgresql-cleanup.json`.

## Раздельные состояния

Код: локальный commit `1523225`, подготовлен [текст одного PR](PR.md).
CI: **NOT_RUN**, PR не опубликован, release flags false.
Main: прежний SHA. TEST: новый выпуск NOT_RUN, состояние сервера не читалось.
Human visual: **PENDING**, визуальная приёмка владельцем не заявляется.
Автоматические screenshots/layout — проверка агентом, не приёмка от имени владельца.
Реальные LLM/письма: NOT_RUN по границам задания. Миграция legacy данных: NOT_RUN,
только [адресный план](LEGACY-TRANSITION.md).

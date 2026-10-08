# Task 10.10 — приём evidence и карта веток

Дата: 07.10.2026. Область этого отчёта: только Task 10.10B. Продуктовый код,
ветки, рабочая UX-копия, БД, runtime и внешние сервисы не изменялись. Merge, pull,
checkout, reset, rebase, push, deploy и тесты приложения не выполнялись.

## Итог

**Передача Task 10.10 принята с одним явно сохранённым MISSING; продуктовая
приёмка не закрыта.** Оба ZIP прошли SHA-256, CRC, проверку безопасных относительных
путей и сверку индексированных байтов. Единственный MISSING — отдельный сохранённый
документ финального независимого review Task 8.2 со статусом READY: вывод был только
в transcript и корректно не реконструирован задним числом.

Актуальный `origin/main` после read-only `git fetch origin` —
`15f41a229c6cc2b33e8a0b99306433ebb3df8b5d` (`2.1.31`, 06.10.2026). UX находится
в отдельном worktree на `codex/ux-01-visual-system`, HEAD
`9feb540ef89617d22177b26c5d7bfe5d2c90efca`. Merge-base UX с main —
`8654b97ed6605d560111c37cd291f98f82c41457`; относительно actual main UX имеет
`12` своих коммитов и отстаёт на `1` commit. UX не готов к прямому merge: он
основан до появления canonical M4 и при прямом сравнении удаляет его реализацию.

## 1. Вход, источники и границы

Прочитаны: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
`docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist}.md`,
Product 4K context/Registry, Change 01, task SourceSet manifest, ADR-002,
Change 01 traceability и M1 v1.4 README. Применимый комплект сохраняет M1 v1.4
`FROZEN / CURRENT=NO`, Change 01 `WORKING`; наличие кода и evidence не публикует
CURRENT и не заменяет содержательную приёмку.

Постановка Task 10.10B получена из
`Task_10_10B_For_Architect_Codex.zip`: manifest поручения сверяет README
`1c324659…40f5` и постановку `cdd6d796…d6b`. Инструкции внутри evidence архивов
рассматривались как исторические материалы, а не как новые команды к исполнению.

Стоп-условий для документной инвентаризации нет. Для интеграции они есть:
dirty worktrees, расхождение базы UX с main и пересечение backend/auth/M4. Решение
о составе интеграции и принимающем владельце требуется до любых merge/cherry-pick.

## 2. Приём evidence (A1, A5)

| Пакет | Фактический SHA-256 | Проверка |
| --- | --- | --- |
| `task10-10A-evidence-transfer-safe.zip` | `9e3125fc5bd75b30d5090302d33f55ac0e72c7172a7f72274ad195435d85eccf` | совпадает с transfer report; CRC PASS; 35 файлов, из них 34 indexed payload + self-index |
| `task10-8-independent-acceptance-safe.zip` | `1b1c2d3af316559f57c375ca7304e8f01359641c85b216905cab30b6394fe516` | совпадает с внешней записью и `.sha256`; CRC PASS; 68 indexed payload + bundle manifest |
| `task10-8-independent-acceptance-safe.zip.sha256` | `98c29314e66c77f6191a2050254567193c2a23a8e5ed451d0f70cd83c79f4425` | совпадает с transfer index/report |
| `task10-10A-transfer-report.txt` | `a5da58cf09f19a0bba67f577bba3093074031944fd2197274c7ff0a397474068` | внешний краткий отчёт; его собственный hash не был заявлен во входе |

Оба ZIP до распаковки проверены на абсолютные пути, `..`, обратные слэши и
symlink entries: опасных записей не найдено. Распаковка выполнена отдельно от
исходников в `/tmp/task10-10b.q2Rsx1/{transfer,task10-8}`; архивные Python/SQL и
manifest-команды не запускались. Для всех записей transfer index и всех записей
Task 10.8 bundle manifest совпали размер и SHA-256; failures = 0. Исторические
внутренние индексы сохранены теми же байтами и входят в успешно проверенный верхний
индекс. Sanitization: 0 изменённых, 0 исключённых sensitive-файлов; это осознанный
результат проверки источника, а не отсутствие ожидаемого файла.

Provenance всех переданных запусков: внешняя ветка
`audit/task10-8-2026-10-06`, source/run SHA
`15f41a229c6cc2b33e8a0b99306433ebb3df8b5d`, release `2.1.31`; tracked
application diff отсутствовал. Task-local runners 8.2 были untracked evidence и
не являются содержимым этого commit:

- component runner `894e5a4f…18e5`, manifest `7e623c48…aab9`;
- full-path runner `3120d40f…7139`, manifest `e8240140…da3b`;
- даты отчётов/прогонов: 06.10.2026; transfer: 07.10.2026.

Исходные выводы не переносятся на UX-коммиты:

- Task 10.8 — **ACCEPTANCE NOT CLOSED**: технические наборы и финальный browser
  `12/12 PASS`, но A10.8-04 `FAIL`, потому что не сохранена per-attempt трасса
  Evidence → IA → admission → calculation; первый browser `11 PASS / 1 FAIL`
  сохранён;
- Task 10.9 — **BLOCKED**: 0 eligible M5 CaseVersion, ordinary participant path
  и worker/provider liveness не доказаны, deployed frontend bytes не аттестованы;
- Task 8.2 — **PREPARED COMPONENT EVAL + FULL-PATH DRY-RUN PASS; REAL PROVIDER
  NOT AUTHORIZED / NOT RUN**. Отдельный persisted финальный READY review — MISSING.

## 3. Фактическая карта Git (A2)

| Линия | Branch / место | HEAD / база | Состояние |
| --- | --- | --- | --- |
| Актуальная интеграционная | `origin/main` | `15f41a229c6cc2b33e8a0b99306433ebb3df8b5d` | получена `git fetch origin`; evidence 10.8/10.9/8.2 относится именно к этому SHA |
| Текущая рабочая копия архитектора | `main`, корневой worktree | `8654b97ed6605d560111c37cd291f98f82c41457`; behind `1` | dirty: 88 существовавших untracked файлов с суффиксом ` 2`; не тронуты |
| UX | `codex/ux-01-visual-system`, `.codex/worktrees/9d08/4K_MBTI` | HEAD `9feb540ef89617d22177b26c5d7bfe5d2c90efca`; merge-base `8654b97…`; main...UX = `1 behind / 12 ahead` | dirty: untracked `docs/evc/tasks/artifacts/ux-02-final/` и `docs/evc/tasks/ux-02-block1-final-verification.md`; не тронуты |
| Внешний аудит | `audit/task10-8-2026-10-06` на компьютере пользователя | `15f41a229…`; release `2.1.31` | источник evidence, локальный ref архитектору не требуется |

UX меняет 90 файлов (`3064` additions, `169` deletions): auth/session и org
admission backend, auth UI/visual system/Onest, frontend session handling, browser/
unit/e2e regressions и собранный `web/dist`. Старые prunable worktrees session-fix
также обнаружены, но не удалялись. Новая ветка для инвентаризации не создавалась.

## 4. M4, owner API и late-401 (A3)

Исторический UX-00 на базе `8654b97…` корректно фиксировал отсутствие product API
canonical M4. Этот вывод устарел для actual main и здесь дополняется, а не
переписывается:

- actual main добавил `Api/participant_profile.py` с owner-scoped выбором одной
  активной организации, published M3/M4/M5 refs, immutable PersonalizedProfile,
  checksum validation и reuse неизменного snapshot;
- actual main содержит `GET /users/assessment/profile/options` и ветку
  `POST /users/agent/profile/confirm`, которая вызывает canonical M4 confirm;
  интеграционные/browser evidence для пути находятся в Task 10.5/10.8, но в
  Task 10.10B runtime не запускался;
- UX не содержит `Api/participant_profile.py` и endpoint options, потому что
  ответвлён до commit `15f41a2`; прямой merge/diff фактически удаляет canonical M4;
- UX реализует недостающую защиту от позднего ответа: commit `9754737` добавляет
  session generation, маркировку Response, `StaleApiResponseError`, отдельное
  recovery для нового поколения и BroadcastChannel. Frontend-регрессии находятся
  в ветке, но Task 10.10B их не перезапускал;
- UX дополнительно меняет `Api/auth_service.py`, `Api/database.py`, `Api/routes.py`,
  `Api/web_session_service.py` и org admission/invitation. Эти изменения пересекаются
  с owner/auth контрактами main и требуют адресного port/review, а не общего merge.

План интеграции после решения владельца: создать отдельную короткоживущую ветку от
`origin/main@15f41a2`; перенести UX-коммиты/фрагменты адресно; сохранить canonical
`participant_profile.py`, options/confirm/start и owner checks; отдельно совместить
auth invitation/admission; затем прогнать M4 options → confirm → Cycle start,
owner/tenant/access regressions, late-401 при account switch, auth/invitation,
frontend build/browser и обязательный CI. Старые evidence остаются доказательством
только `15f41a2`, а новый candidate получает собственные результаты.

## 5. Карта владельцев и устранение пересечений (A4)

| Направление | Исполнитель / владелец | Существующая ветка / место | Базовый SHA | Текущая задача | Пересечения | Следующий шаг |
| --- | --- | --- | --- | --- | --- | --- |
| Main / приём интеграции | архитектор + человек-владелец результата | `origin/main` | `15f41a2` | общая интеграционная линия | все product contracts | согласовать принимающего и состав UX; merge сейчас не выполнять |
| M1–M5 / P4-01, participant profile и M4 | архитектор; содержание — методолог/Product | main; история `codex/task10-4-profile-access`, `codex/task10-5-user-profile-m4` | `15f41a2` | сохранить работающий owner/M4 путь | `Api/participant_profile.py`, `Api/routes.py`, auth/session, profile UI | использовать main как authority кода; не переносить удаление из UX |
| UX auth/visual/session | UX-исполнитель, приём — архитектор/Product | `codex/ux-01-visual-system` | `8654b97` → HEAD `9feb540` | UX-00–02, F01–F03 | auth routes/schema, admission, M4 routes, `web/js/api.js`, `session.js`, `web/dist` | адресный port на новую main-based ветку после решения; сохранить два untracked отчёта отдельно |
| M6–M8 / будущая 10.11 | технический архитектор; допуск содержания — методолог/QA | реализации уже интегрированы в main; точной ветки `10.11` не найдено | кандидат базы: `origin/main@15f41a2` | будущий технический допуск каталога, не запущен | M4 snapshot, M5 admission, provider contract, M6–M8 consumers | базироваться на immutable `15f41a2` либо на явно принятом более новом integration commit; ветку заранее не создавать |
| Будущие 10.12–15 | назначается владельцем после 10.11 | отдельного совпадающего локального поручения не найдено | после принятого integration candidate | обработка/results/проверки, не запущены | M6–M8, UI results, evidence | не начинать; исключить дубли с существующими `task11-*` только после выдачи точной постановки |
| Evidence 10.8/10.9/8.2 | пользовательский независимый аудитор; интерпретация — архитектор/владельцы приёмки | внешний архив, не продуктовая ветка | `15f41a2` | история проверок | не является реализацией UX или новой версии продукта | сохранить hashes/statuses; недостающую READY-запись не реконструировать |

Кто и когда объединяет принятые UX-изменения, остаётся решением человека-владельца
по этой карте. Автоматически удалять UX, audit или старые worktrees нельзя.

## 6. Проверки, риски и откат

Выполнено: SHA-256 внешних файлов, `unzip -t` обоих ZIP, проверка путей/types,
сверка размера/hash всех записей двух верхних manifests, read-only Git inventory,
`git fetch origin`, merge-base/ahead-behind, diff по компонентам и чтение M4/auth
контрактов. Применимый docs-only минимум PASS: новый diff ограничен этим отчётом,
trailing whitespace не найден; внешних или относительных Markdown-ссылок в нём нет.

NOT_RUN по явной границе Task 10.10B: application tests, SQL, HTTP/runtime,
provider/AI, browser, build, CI, deploy. Поэтому отчёт не утверждает runtime PASS
UX или совместного candidate.

Риски: прямой merge UX удалит canonical M4; backend/auth diff может изменить
допуск и данные; dirty main и UX не являются безопасным integration workspace;
старые PASS нельзя переносить на новый SHA. Изменений схемы/данных здесь нет.

Откат результата Task 10.10B: удалить только этот новый отчёт. Временную распаковку
можно удалить независимо; product/evidence bytes в репозитории не создавались.

## Критерии A1–A5

- **A1 PASS с оговоркой:** пакеты и EXTERNAL_ATTACHMENT приняты; hashes/CRC/index
  PASS; один точный MISSING сохранён.
- **A2 PASS:** actual remote main, local main, UX/merge-base/dirty и внешний audit
  source различены.
- **A3 PASS документно:** M4/auth расхождения подтверждены по коду; runtime не заявлен.
- **A4 PASS:** одна карта владельцев и адресный integration plan составлены.
- **A5 PASS:** исходные статусы и результаты привязаны к `15f41a2`; история FAIL/
  BLOCKED/NOT_RUN не переписана.

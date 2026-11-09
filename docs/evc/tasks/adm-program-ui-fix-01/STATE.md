# P4K-ADM-PROGRAM-UI-FIX-01

09.11.2026, локальный Codex/macOS. Прямое поручение пользователя: распаковать
`P4K_ADM_PROGRAM_UI_FIX_01_2026-11-09.zip` и выполнить `START_CODEX.txt`; общий
checkpoint не требуется. Пакет — источник требований; локальная реализация и
передача разрешены прямым поручением. Исторические допуски выпуска не наследуются.

## Основание и границы

- Repository: https://github.com/VadikB/4K_MBTI.
- Свежий fetch main: `46a5532336e41c5cdedf9684ba7bd5a9c5c202d1`, 2.0.87.
- Ветка: `codex/adm-program-ui-fix-01`; отдельная копия
  `/private/tmp/p4k-adm-program-ui-fix-01-20261109`. Исходные checkout сохранены.
- Единственный редактор ветки — root; параллельные агенты только читают код,
  рекомендуют проверки и проводят review (разрешено инструкцией multi-agent).
- Разрешены UI/guard fixes, адресные synthetic checks, локальный build/commit/bundle.
- branch_push/pr/merge/deploy/version_bump/artifact_publish=false.
- LLM=0, реальные письма=0; рабочая БД/.env не используются. EXEC исключён.
- Не возобновлять разработку 1А–1В/3А–3Б или полный PATH. Эта задача заменяет
  предшествующий запрос итоговой QA; live TEST не объявляется проверенным.

## План

1. Разведка источников/renderer/handlers — завершено.
2. Формы и guards, сохранение scoped drafts и stale callback fences — завершено.
3. Локальные checks и visual states — завершены на точном code SHA ниже.
4. Проверенный bundle, CHECKS/evidence/VISUAL/PR_BODY и передача — упаковка локального результата.

## Прочитано / применимость

- Все файлы входного пакета; SHA256SUMS: 6/6 PASS.
- AGENTS.md; EVC agent-workflow, verification-matrix, artifact-recipe,
  task-template/review-checklist, CONTRIBUTING.md; адресные записи decision-register.
- ADR-003: подключение программы, revision анкеты, назначение, подготовка и старт
  различаются; published definitions неизменяемы. SYN-CONTOUR-OWNERSHIP: только
  новая marker-owned test/pytest-БД и проверенный cleanup.
- Product Architecture 1.0 context/registry, Change01 WORKING; существующий UI
  PM-02/PM-03. Методологические нормы не меняются; M1 CURRENT не присваивается.
- ac18-adm-1a/1b: действующие manual/CSV revision, stale/foreign/idempotency guards
  сохраняются. Старые PASS и допуски не используются как результат этой задачи.

## Проверки и ограничения

- Fetch + отдельная ветка PASS; код пока не изменён.
- Минимум: diff check, JS lint/build, затронутые frontend tests; browser реальные
  renderer/handlers и отсутствие запрещённых POST; positive manual/CSV HTTP/owned
  PostgreSQL по существующей fixture, без генерации и внешней почты.
- Все результаты привязываются к точному code/candidate SHA; owner visual
  acceptance, физические телефоны, CI и release — отдельные NOT_RUN/PENDING.
- Открытых предметных решений нет; API/schema/definitions не меняются, все
  стоп-условия workflow для локальной реализации — нет.
- Откат: revert собственных commits без удаления продуктовых данных.

## Исправленный результат и уточнение владельца

- Без подтверждённой программы нет editable ref и предложения исторического ключа.
  Preview/confirm/assignment сверяют точное серверное подключение перед POST.
- Unknown имеет GET-only проверку, не использует прежний currentProgram/ref для
  команды. Запоздалые collection/import/program GET не восстанавливают старый scope.
- Raw drafts/авторы сохранены по scope; native CSV после перерисовки честно просит
  повторный выбор. Failed GET сохраняет последние изменения полей.
- Локальная галерея: `node scripts/adm-program-ui-preview.mjs`, порт18944;
  реальные HTML/dist, synthetic HTTP, без БД/LLM/почты. Она не доказывает путь TEST.
- По прямому дополнению пользователя в этом же чате включена «Готовность назначения»:
  absent — один основной blocker и следующий шаг подключения суперадминистратором;
  unknown — роль/анкета ещё не проверены для программы; нет ложного «Оценка не выбрана».
  Confirmed — отдельные факты role capabilities, чтения и подтверждения exact анкеты.
  Known roles[] отличаются от отсутствующих сведений о роли; независимая карточка
  редактируется при любом состоянии программы.
- Адресные CSS: перенос длинных слов и min-width шапки admin-panel при text200;
  чат/assessment и общие стили не меняются.
- Старые positive browser fixtures теперь задают подтверждённую программу, вместо
  ввода hidden ref. Содержательные assertions, role/identity guards сохранены.
- Предыдущий code SHA `6a899606f1fbf1a787e7e2c66f567ead866733cd`: 70 browser,
  192 frontend, 26 HTTP PASS. Это ещё без последнего уточнения readiness и не
  объявляется результатом нового SHA. Новый полный адресный прогон фиксируется далее.
- Физические iOS/Android, native text zoom, owner visual acceptance, TEST и CI/release
  остаются отдельными NOT_RUN/PENDING. LLM/EXEC/оценочные ответы/отчёты не запускались.

## Финальная проверка

Проверенный code SHA: `f7d6a951c45df39800d6343280197f6822aa17d7`, app release2.0.87.
После него меняется только эта STATE. Точный delivery HEAD и эквивалентность product/
test/script bytes фиксируются в SOURCE_MAPPING.json внешнего handoff, не самоссылкой.

- `node --test tests/frontend/*.test.mjs`: **192/192 PASS**.
- `npm run lint:js`, `npm run build:web`, `git diff --check`: **PASS**.
- Адресный Playwright: **76/76 PASS**, включая 22 guards/readiness, 6 visual cases
  с **108** сочетаниями role/state/view/width/text, 2 actual HTTP/owned PG positive
  manual/CSV, 29 старых admin/confirmation/scope checks и 17 feedback/draft guards.
- Questionnaire/assignment/readiness HTTP regressions: **26/26 PASS**.
- В обеих actual PG проверках: preview201 → confirm200 → HTTP/PG/reload readback
  одной revision, provider_operations0, counts оценочного пути неизменны.
  Evidence сохранено до cleanup; owner_verified/database_absent/state_absent=true,
  force=false. Собственный PG16 cluster55443 остановлен; preview18944 работает без БД.
- Readiness: absent/unknown дают только основной blocker подключения и непроверенные
  зависимые строки. Confirmed роли unknown/none/unavailable/available и exact/cached
  confirmation проверены отдельно; независимая карточка и правильный positive assignment
  сохранены. Назначение без подтверждённой программы блокируется до POST.
- Первичные evidence: внешняя передача `outputs/p4k-adm-program-ui-fix-01-20261109`,
  CHECKS.csv, нормализованные browser receipts, actual PG JSON/PNG и checksums.
  Промежуточные FAIL сохранены как история диагностики, не включены в финальные counts.
- Локальное read-only review выполнено; его замечания по draft/late callbacks закрыты
  адресными регрессиями. Owner visual acceptance не присвоена агентом.

Остаток этой локальной задачи: проверка пакета и передача. Разработка повторно не
требуется. Следующий этап архитектора — импорт точного bundle в свою ветку, review,
согласованная release-подготовка и обязательный CI по отдельным полномочиям.

## Интеграция архитектором в актуальный main

09.11.2026 кандидат импортирован из проверенного `implementation.bundle` и перенесён
на актуальный `origin/main` `60234f2a1d8d8389567fbfb012f4b83eb3b4a21f` / 2.0.88.
Хешированные файлы `web/dist` не переносились со старой базы: они пересобраны из
итоговых исходников на новой базе. Source/test diff применился без конфликтов.

До release-подготовки на интегрированном дереве: `git diff --check`, `npm run lint:js`,
`node --test tests/frontend/*.test.mjs` (200/200) и `npm run build:web` — PASS.
Следующий согласованный PATCH — 2.0.89; точный release SHA и GitHub CI фиксируются
в PR. Откат остаётся совместимым squash-revert без удаления продуктовых данных.

Первый CI head `eab70f74f45ce6212f1b1e0efb705f3a51e2e980`: `frontend`, `pytest`,
`integration` и четыре runtime browser shard — PASS; `browser (fast)` — FAIL на
единственном legacy assertion `PROGRAM01 R10 shows a terminal error when exact readback
is null` (222 остальных теста PASS). Реализация теперь выдаёт более точный fail-closed
текст о неподтверждённой версии, тогда как тест ожидал прежнюю фразу о повторном чтении.
Assertion синхронизирован с новым контрактом; адресная регрессия и полный CI должны
быть повторены на новом head. Merge до зелёного `full-verification` запрещён.

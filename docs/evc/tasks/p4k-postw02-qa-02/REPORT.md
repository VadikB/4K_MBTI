# QA-02 — локальный результат

Реализована матрица приглашений редакции1.1: безопасные причины в POST/GET и списке,
различение подтверждённого отказа и неизвестного исхода, controlled transport,
сохранение identity/частичного batch, свёрнутые сведения участника. Это локальный
кандидат без merge/deploy и нового номера версии; фактическая доставка не проверялась.
Точный SHA зафиксирован в родительском outputs/p4k-postw02-qa-02-20261117/DELIVERY.json.
Base71a9c535cee4aea094d2b49c2b73f39e22f99bbe,2.1.28; финальный fetch подтвердил ту же базу.

## Доказательства и границы

| Проверка | Результат | Область |
| --- | --- | --- |
| lint:js / build:web / diff --check | PASS | production bundle, текущие CSS/entrypoints |
| frontend/*.test.mjs |429PASS | Включая25 новых проверок представления;22 строки текста сверяются с приложенной матрицей как независимым источником |
| test:backend |1247PASS | Controlled I/O; sandbox-запрет ps устранён ограниченным запуском. После финального bounded fingerprint дополнительно адресный набор ниже |
| test:backend:http |216PASS | Обязательный HTTP-набор, включая15 новых QA02 случаев |
| Адресный transport + invitation HTTP |61PASS | Реальные handlers, безопасные provider codes, malformed/timeout/protocol loss, старые guards |
| Полный integration |459PASS,2SKIP,1FAIL | Единственный FAIL — старая fixture без существующей production-колонки created_at; реальные provider tests SKIP по штатному marker |
| После исправления fixture, финальный адресный SQL/HTTP |28PASS | QA02 + R03 + revoke + adm1c; оба разрешённых scope, UTC/Moscow, конкурентность, fingerprint, сохранённые причины |
| Browser |15PASS |5 новых QA02 и10 прежних invitation; production bundle, controlled API,1440/390/320,1worker,0retry |
| REFERENCE_V10 |PASS24хеша | source e44fa78efb1ec8605b28cf9bc2c2272da2b9122a; композиция сохранена |
| GitHub CI / PR / TEST доставка |NOT_RUN | Внешняя публикация и deploy не выполнялись; локальные проверки CI не подменяют |

Полный integration не выдаётся за единый зелёный прогон после исправления:
используются459 неизменённых PASS и28 адресных PASS с исправленной fixture и
финальным invitation-кодом. Повтор всего run не запускался. Исторические ошибки
sandbox/DNS/устаревших текстовых ожиданий отделены от продуктового результата.
Итоговые команды и счётчики: evidence/checks.json. Тестовые окружения изолированы,
реальные mail/LLM0; PostgreSQL остановлен, browser HTTP servers закрыты.

## Приёмка

| AC | Проверка | Результат |
| --- | --- | --- |
| I1 | Production ветви readiness/unsupported/minimum/membership/ACL/config/transport; frontend словарь и22 точных текста из owner spec |PASS |
| I2 | SQL+HTTP для admin/superadmin, оба timezone; controlled sink и один эффект при replay/concurrency |PASS |
| I3 | Сохранённый envelope после GET/replay; pre-INSERT rows0/GET404, без фиктивных записей |PASS |
| I4 | Malformed/empty/non-object/timeout/incomplete-read/5xx unknown; lost client reply→тот жеID/readback; без transport retries |PASS |
| I5 | Mixed accepted/error/unknown, нормализованная сводка, сохранение частичных фактов, запрет изменения batch ID и пересечения unresolved |PASS |
| I6 | Sender/org/assignment/token legacy negative guards, foreign sender404, safe whitelist без raw error; late response не меняет другую карточку/контекст |PASS |
| I7 | PNG1440/390/320: единый общий блок, локальное пояснение, collapsed details, long ID без горизонтального overflow; copy/keyboard |PASS |
| I8 | queued/in-flight/accepted/error/unknown; active/expired/revoked/used link facts и registration отдельно; accepted не delivery |PASS |
| I9 | error без категории сохраняет failed; response loss unknown; неоднозначный provider code не становится конкретной причиной |PASS |
| I10 | Закрытие/открытие во время GET сохраняет последнее действие, новая карточка collapsed; attempt-key смена закрывает details |PASS |

Скриншоты: evidence/common-failure-{1440,390,320}.png,
evidence/details-{1440,390,320}.png, evidence/mixed-recovered-1440.png.
Они синтетические и не показывают конфигурацию TEST.

## Реализация, совместимость и ревью

Контракт — CONTRACT.md. Изменены только invitation routes/projection/schemas,
почтовый адаптер, invitation presentation/details и их wiring/CSS/entrypoint;
тесты, evidence и штатная пересборка dist. Общие report/draft/polling-функции не
перерабатывались. Файлы другой задачи в исходном checkout не изменены.
Архитектурные/методологические нормы, published sources, grants и схема БД сохранены.

Self-review: нет новых приглашательных блокеров, миграций или произвольных причин
по HTTP500; используются существующие проверки. Устаревшее known error не теряет
причину; неизвестный исход не даёт автоматический новый ID. Принятие транспортом,
ссылка, регистрация и назначение различаются. Legacy поля остаются, новые имеют
default. Риск выпуска: потребуются точный head CI, человеческое review и согласованный
номер перед Ready/merge; локальный результат этого не заменяет.

## Внешний остаток и откат

QA05 RESULT.md17.11 — PARTIAL: обе живые invitation причины UNKNOWN, SSH publickey
отказ. QA02 повторную ревизию TEST не выполнял. Нужны доступные оператору прежние
operation_id или организация/время/номер попытки и разрешённый read-only сбор.
Настройки, ключи, environment и данные TEST не изменены. Механизм проверен controlled
transport; доставку в почтовый ящик и устранение живого отказа не утверждаем.

Откат: revert QA02 commit целиком с собранным dist. Новые поля добавлены совместимо;
миграции нет. Старый backend читает TEXT envelope как error, прежний UI скрывает
произвольный error. Переданный старому UI текст может стать общим — это ожидаемая
потеря детализации при откате. Участников, операции и ссылки не удалять/не пересоздавать.
# Дополнение выпуска 17.11.2026

PR246: https://github.com/VadikB/4K_MBTI/pull/246, кандидат2.1.29.
CI head496aa25 подтвердил unit1248, HTTP216 и integration462PASS/2SKIP.
Первый полный CI неуспешен: frontend блокирует unpatched picomatch
(https://github.com/advisories/GHSA-fc5q-39xc-vjpf); browser-fast340PASS/40SKIP/10FAIL,
runtime3 7PASS/1FAIL, runtime1 и4 PASS, runtime2 CANCELLED на checkout.

После диагностики исправлены: принятие неполного batch без обязательного exact
readback (лишний адресат не доказывает новые факты; безопасная часть неполного
ответа сохраняется); повторный Finish в тестовом помощнике после закрытия AS другой
вкладкой. Старые browser-assertions проверяют новый summary и дату в подробностях.
Локальные результаты исправлений: frontend431PASS, lint/build/diffPASS,
program-guards+QA0240PASS, controlled real-backend ADM281PASS, runtime1183 1PASS;
radar1PASS на текущем bundle и1PASS на неизменённом main71a9c53. Renderer не менялся;
причина CI-only radar-font FAIL остаётся UNKNOWN, без снижения порогов проверки.
Диагностика зависимости: latest picomatch4.0.7, patched=None; latest knip6.45.1
сохраняет эту зависимость. Ни audit, ни обязательные CI gates не изменены.

Merge и deploy НЕ выполнены. Исправления сохраняются в диагностическом draft PR;
после устранения tooling-блокера нужен новый полный CI актуального head.
Реальные mail/LLM0, TEST не менялся, owned PG55439 остановлен.
Далее сохранён исходный отчёт локальной реализации до этапа выпуска.

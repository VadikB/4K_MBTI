## Основание изменения

Задача: `docs/evc/tasks/p4k-remain-05/TASK.md`, REMAIN_05 v1.6. Base `a1cdfedfb8b71d150b078eb0380ea013f0b08965` включает REMAIN_01–04 (#215–218). Кандидат PATCH **2.1.5**.

## Результат

После AbortError, deadline или пустого/повреждённого201 клиент терял pending первого старта. Теперь ключ записывается до POST; заголовки/тело ограничены существующим deadline, квитанция проверяется, неопределённый исход восстанавливается через owned runtime того же Cycle. Известные отказы сохраняют причину, включая отказ при readback; unknown не открывает непроверенную AS. Ошибки GET/PUT/POST знакомства имеют понятное объяснение и отдельный код обращения; введённый текст и шаг остаются.

F27 проверен через controlled tester/challenger/queue и настоящую isolated PostgreSQL/HTTP. Admission, prompts, retry policy и frozen snapshots сохранены. Все7 AC PASS TECH в области CHECKS; остановка на первой AS,0оценочных ответов.

## Изменённые файлы

`web/js/product-cycle-start.js`, новый `acquaintance-errors.js`, error presentation `screens/onboarding.js` и собранный dist. Frontend/browser регрессии; optional `first_case_only` в существующем integration harness (default false) и узкий reuse wrapper до первой AS. Штатная синхронизация версии в pyproject/uv.lock/config/index.

## Источники и решения

M1v1.4 FROZEN/CURRENT=NO, M4v1.0, M5v1.1, M7v1.3; Change01 WORKING И-2/3/6, C23/24/34, PM03→PM04. Пути/хеши и rule→data→code→test — TASK/CHECKS. Новых методологических решений нет. Владелец подтвердил работу и продолжение на машине архитектора; публикационный этап PR отделён от merge/deploy.

## Проверки (команда → результат)

- `npm run ready:prepare -- --candidate 2.1.5`, lint/build/release gate/diff — PASS.
- `node --test tests/frontend/*.test.mjs` — **305 PASS** на кандидате2.1.5.
- Адресный Playwright F04/F27 — **8 PASS** на2.1.5; hard180с/no-progress60с, retries0.
- Protocol units — **65 PASS**; actual PostgreSQL/HTTP — **23 PASS**, reused сd1326a3e по byte-identical Api/integration области. Новая БД при bump не нужна.
- Первичные safe gzip logs, исходные harness FAIL и ограничения — `docs/evc/tasks/p4k-remain-05/CHECKS.md`, ресурсы/cleanup — STATE.

## Непроверенное (что и почему)

CI ждёт этого PR; remote full-verification обязателен. Полный локальный backend/integration/browser не повторялись: продуктовый Python/схема не менялись, JS minimum и адресные реальные границы проверены. Browser — synthetic HTTP projections, SQL/HTTP — настоящая owned PostgreSQL; это сочетание границ, не единая полная auth→AS сессия. Human review/TEST acceptance/physical device/real LLM/mail NOT_RUN. Исторические fd…/PREP-DIAG остаются UNKNOWN.

## Риски: конфиг / схема / деплой / безопасность / откат

Конфиг/схема/API/опубликованные определения не меняются. Runtime использует сохранённые snapshots; явный start/admission guards прежние. Секретов/PII нет, .env не читался. Существующее ограничение sessionStorage отмечено в CHECKS. Откат — revert этого PR с dist/версией, без изменений сохранённых Cycle/AS/profiles. Временные БД/servers/process groups остановлены.

## Следующий минимальный шаг

Обязательные frontend/pytest/full-verification точного head/base, затем человеческое review и отдельный допуск merge; штатный deploy-test только после разрешённого merge.

## Открытые вопросы (блокеры)

Предметных блокеров нет. CI и человеческое review обязательны перед принятием.

## Действия выпуска

- [x] branch_push
- [x] pr
- [ ] merge
- [ ] deploy
- [x] version_bump:2.1.5
- [ ] artifact_publish

## Готовность

- [x] Один независимо принимаемый результат, без несвязанного рефакторинга.
- [x] Локальный минимум выполнен; evidence и ограничения сохранены.
- [x] Старые данные/snapshots совместимы; миграция не нужна.
- [x] Регрессии и реальные HTTP/SQL границы проверены.
- [ ] Актуальный CI успешен и человеческое review завершено.
- [x] Baseline не присваивался.


## Сопровождение CI

Первый head5bf7aca5: frontend/pytest и все5 browser lanes PASS, integration1FAIL/410PASS/2SKIP. Причина — прежняя positive fixture EXEC-FIX05 с остатком0.1с после resume. Задержка0.2с воспроизвела тот жеM7_TIME_LIMIT_REACHED; после увеличения только synthetic positive запаса до60.1с и сохранения delay regression18HTTP/SQL+10unit PASS. Product timers/Api и exact negative boundaries не менялись. Before/after и primary CI link — CHECKS/receipts. Новый head проверяется обязательным CI, предыдущий FAIL не скрыт.


## Ожидание фактической доставки ASK в test driver

На d4fbee4b integration прошёл; runtime3/4 выявил прежний race `COMPOSITE_ASK_NOT_DELIVERED` (на первомhead тажеlanePASS). ASK и доставка фиксируются раздельно. Driver теперь boundedожиданием ждёт question_turn_id доотправкиответа; sameCycle/sameAS/id и негатив never-delivered сохраняются. Controlledbefore1FAIL, after6driver+305frontendPASS. Продуктовыйruntime/admission/M6/M8 не менялись. ПредыдущиеCIисходыиprimarylinks вCHECKS; дляновогоhead выполняетсяобязательныйCI.

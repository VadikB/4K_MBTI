# P4K-POSTW02-04 — результат реализации

Повторная доработка представления по review: [актуальный отчёт A–H](REVIEW_FIX_REPORT.md), [снимки](VISUAL_REVIEW_FIX.html), проверенный код `0145485814ab4bd35a7ffa109a9be68977ecb5f1`. Первичная серверная реализация и её доказательства ниже сохранены.

Подготовка оценки, следующей ситуации и отчёта получила одну безопасную проекцию
сохранённой операции: подтверждённый этап, объяснение, начало, последняя смена
этапа, завершение, последнее чтение, актуальность, действия и стабильный код.
Эта проекция показана в готовности, «Моих оценках», прохождении, ожидании отчёта
и назначении администратора. Техническая трасса доступна только серверному CLI.

Base: `99d225119108526912c44a6b8a6e6012cc289b04` / `2.1.16`.
Ветка: `codex/p4k-postw02-04`. Точный переданный head, PR и CI сохраняются вне Git
в `outputs/p4k-postw02-04-20261116/DELIVERY.json` родительского workspace, чтобы
запись результата наблюдения не изменяла проверяемый commit.

## Источники и границы

Поручение пользователя: «выполни задание 4» от 16.11.2026. Приложения
`P4K_POSTW02_04_Preparation_Status.txt` и `REFERENCE_POSTW02_04_05.txt`, rev1.0,
задают требования. Это источник требований, а прямой запрос пользователя —
источник полномочия локального выполнения. Передача подготовлена как один draft PR,
но внешний этап требует отдельного подтверждения: `branch_push/pr=pending_approval`,
`merge/deploy/version_bump/artifact_publish=false`. Автоматическая проверка безопасности
отклонила push в `VadikB/4K_MBTI`: прямой запрос задачи не признан достаточным
разрешением на экспорт исходников, тестов, отчёта и снимков в этот remote. Ветка
не отправлена, PR не создан; владельцу задан конкретный вопрос о push/draft PR.

Прочитаны AGENTS, README, CONTRIBUTING; EVC agent-workflow, verification-matrix,
artifact-recipe, decision-register, review-checklist; architecture context/registry;
Change01 WORKING 01.10.2026 source И-2–6; ADR002/003; первичная карточка ARCH-A05.
M7 v1.3 §§5.3–5.6 и M8 v1.2 §§1/7 прочитаны из выбранного SourceSet; пять
проверенных хешей совпали с manifest. Точные пути/хеши — [sources.json](evidence/sources.json).
Глоссария WORKING 30.09 нет в manifest: найден и прочитан первичный файл
`P4K_EXEC_FIX_03_2026-11-09/resources/…Reconciliation_WORKING_2026-09-30.docx`,
SHA256 `95bdc36d5ccb7d2da93d268ec6cb2012daace2b85878f0ffefc39e9d4c66b95d`.
Прочитаны Dialogue/Turn/Response и W064: LU — Local Unit; Component — компонент
навыка. Исторические REVIEW и CURRENT сохранены. Архитектурная ответственность
ниже не утверждает отдельный сервис или человека-владельца.

Main повторно обновлён перед передачей: 01/02 и REPORT01–03 уже включены.
POSTW02-03 / PR231 остаётся OPEN на `37881fd38d2e855b6c824b19073032584828cc53`;
его исходники не перенесены. REPORT-04 / PR232 OPEN на
`6bf28fe3efe77abd136aa2ef907fe72cd6a5a29e`: пересекаются имена database.py,
routes.py, index.html и generated dist. Исходные изменения находятся в разных
участках (у REPORT04 display snapshot/PDF/представление Report); чужая задача
не объявляется выполненной. Для объединения dist требуется обычная пересборка;
итоговые обязательные checks выполняются после обновления базы.
`git merge-tree --write-tree` на рабочем commit04 проверил оба сочетания без изменения
веток: с03 exit0/конфликтов0; с REPORT04 exit1/24 конфликта, все только в `web/dist`.
Исходники, включая database.py/routes.py/index.html, объединяются автоматически.
Задание05, знакомство, анкеты, профилирование, роли и нормы оценки не изменены.
Legacy Session-ориентированная генерация набора кейсов не превращена в M7 Cycle;
таблица ниже описывает фактические продуктовые Cycle entry points, включая
выпущенную синхронную совместимость. Старые Cycle-операции без стадий получают
общий подтверждённый статус и честное отсутствие деталей.

## Реальные этапы и маршрутизация

| Вход / точка выполнения | Сохранённый этап | Текст | Фактическая LU / функция для разбора |
| --- | --- | --- | --- |
| `ProductCyclePreparationQueue.enqueue` | queued | Запрос принят. Ожидаем начала подготовки | Инфраструктура: `Api/product_cycle_preparation_queue.py:_claim/_lease_heartbeat` |
| `m10_product_flow.prepare` перед реальным `create_plan` | plan | Составляем план оценки | PM04: `Api/m7_cycle_planner.py:create_plan` |
| `_prepare_next`; functional `generate/repair_candidate` | first / next | Готовим первую / следующую ситуацию | PM03: `Api/m10_product_flow.py:_prepare_next`, `Api/m5_functional_generation_service.py:prepare` |
| Functional `test_candidate` / повторная проверка repair | checking | Проверяем материалы ситуации | PM03: `Api/m5_functional_generation_service.py:test_candidate`, attach допуска — `m7_cycle_planner.attach_functional_generated_as` |
| Синхронные `start_or_resume` / `next_situation` | только реально исполняемые plan / first / next | Те же формулировки | `Api/routes.py` → `Api/m10_product_flow.py`; отдельные попытки наблюдения, прежний HTTP-контракт |
| `_set_state(evidence_queued/assessment_queued)` | answers | Обрабатываем сохранённые ответы; при фактической очереди — ожидание начала | PM05: `Api/m10_orchestration.py:_queue_outbox/_queue_assessment`, `Api/m6_worker_v2.py`, `Api/m6_assessment_worker_v2.py`; свежесть по сохранённым lease |
| `_finalize_cycle`, `create_substantive_detached/create_results` | results | Формируем итоговые результаты | PM05/06: `Api/m6_cycle_aggregation_repository.py`, `Api/m8_results.py:create_results` |
| `create_report_detached` после сохранённых Results | report | Собираем отчёт | PM07 / представление: `Api/m8_results.py:create_report_detached`, `Api/m8_descriptive_report.py` |
| Существующий допущенный Report / проверка старта | терминальное состояние исходной операции | Отчёт готов / действующий экран допуска старта | Готовность не вычисляется из часов или одной completed-записи; `assessment_start_readiness` и M8-доступ сохранены |
| Сервисный recovery отчёта | новая попытка той же операции; results либо сразу report | Только фактически выполненный участок | `Api/m10_orchestration.py:_process_recovery`, без повторного расчёта сохранённых допустимых Results |

Если стадии внутри статической подготовки не разделены, показывается одна
подтверждённая подготовка материалов. Пропущенная работа не изображается завершённой.
Стадии логируются отдельным commit технической таблицы, поэтому другой запрос видит
их во время provider. Этот commit не фиксирует предметную транзакцию. Attempt token
и lease проверяются отдельно; поздняя запись не меняет новую попытку. История repair
и предыдущих попыток остаётся в таблице; heartbeat не меняет stage_started_at.
Отметки старой очереди без timezone читаются в timezone БД и не переписываются.
Анализ interim до закрытия сбора не запускает часы подготовки отчёта.

## Контракты, хранение и ожидание

Аддитивная `preparation_observations` содержит только технические идентификаторы,
безопасные стадии, времена, историю, категории и связи с прежней операцией.
Таблица создаётся существующим ensure-schema; сохранённые snapshots, определения
и результаты не переписываются. Публичные операции дополнены `preparation`, runtime —
`report_preparation`, кабинет — `ParticipantAssessmentCard.preparation`, M8 status и
точная административная стадия — `preparation`. Прежние поля/маршруты сохранены.

`PREPARATION_DELAY_NOTICE_SECONDS=300` в `Api/config.py` / `.env.*.example` — новый
UX-параметр, диапазон 1..300; он не меняет worker timeout, методологию или SLA.
Порог вычисляется по сохранённому началу этапа (для legacy — известному началу
операции с неизвестной детализацией). Клиентское объявление планируется точно к
порогу, даже после остановки сетевых опросов. Длительность обновляется минутами,
не является live region; после завершения отсчёт останавливается.

Различены очередь, длительный живой этап, отсутствие свежего heartbeat/lease,
устаревшее чтение, ошибка чтения и confirmed failed. При ошибке чтения остаётся
последний этап с явным предупреждением и временем последнего успешного чтения.
Готовность и failed имеют приоритет над задержкой. `no_result` и готовый отчёт с
ограничениями не превращаются в ошибку подготовки.

Подготовка использует общий прежний budget60s/backoff1.5–5s; budget сохраняется по
операции при reload. Ожидание отчёта ограничено60s/backoff5–15s. Ручная проверка —
один GET, budget не сбрасывает; новый POST допускается только явным серверным retry.
На навигации сетевой poll прекращается; callback повторно проверяет экран/срок до
запроса. Локальные минутные часы не вызывают API и удаляются вместе с DOM.
Счётчик ситуаций и учёт M7-времени не меняются из-за отображения статуса.

## Разбор конкретной задержки

«Сведения о подготовке → Скопировать сведения» копирует человеческий текст:
вид, этап, ожидание, начало, последнюю смену, актуальность и `P4K-…`.
В нём нет SQL, модели, prompt, AS/Session, raw error/JSON, персональных данных и
обещаний отправленной заявки. Код — SHA256(source:operation_id), первые96bit;
идентичен для участника/администратора и всех попыток той же операции отчёта.

Команда для серверного сопровождения с существующим закрытым доступом:

```sh
.venv/bin/python scripts/preparation_diagnostics.py P4K-<24 HEX>
```

CLI использует `SET TRANSACTION READ ONLY`, находит ту же операцию и попытки,
назначение/артефакты, времена, heartbeat/lease, безопасную категорию, историю и
реальный путь кода. Обычный UI такой endpoint не получает. При новом коде очереди
до первой попытки CLI находит исходную queue-запись; legacy не получает вымышленной
истории. Событие `preparation_delay reference=… attempt=… stage=… owner=…` пишет
worker, один раз на операцию/этап/попытку, а не GET/poll.

Пример обращения: «Подготовка первой ситуации, этап “Проверяем материалы ситуации”,
с начала30 минут, без смены27 минут, код P4K-…; есть ли работающая попытка и что
мешает завершению?» По коду SQL-тест read-only находит `operation`, текущий attempt,
`checking` и `Api/m5_functional_generation_service.py:test_candidate`; heartbeat
свежий, время смены прежнее. Это не установление причины пользовательского
исторического30-минутного ожидания: его исходная трасса не исследовалась.

## Проверки и ограничения

| Проверка | Результат | Область |
| --- | --- | --- |
| Backend offline, без integration/e2e/llm | PASS:1142 | Включая16 новых сценариев проекции. Первоначальный sandbox запрещал `ps`; повтор с разрешением выполнил штатные process-tests,19 PASS; полный итоговый набор1142 PASS |
| HTTP/e2e | PASS:178 | Новый owned GET, отсутствие enqueue/утечки и согласованность admin; прежние177 сохранены |
| Frontend Node | PASS:358 | Стадии,30/27мин, точный5-минутный порог, frozen terminal time, safe copy, legacy regressions |
| Изолированный PostgreSQL16 | PASS:8 | Пять новых stage/read-only/fence/real-entry tests; существующие report recovery/concurrency и queue fencing; отдельная регрессия часов до/после закрытия. Контролируемые providers; отдельная `p4k04_utf8_pytest` localhost:18744 |
| Browser actual dist + fake API | PASS:2,1440/390 | Готовность/reload/read error, следующая ситуация/фокус, отчёт/budget/manual GET/ограничения, admin/clipboard; длинный текст без overflow; без registration/full Cycle |
| Lint / build / diff-check / source hashes | PASS | Сборка существующим esbuild, CI не изменён |
| Полный synthetic Cycle, реальный provider/письма, Prod | NOT_RUN | Явно исключены постановкой; содержательное качество LLM этим не доказано |
| GitHub draft PR / быстрый CI | NOT_RUN | Push отклонён auto-review; ожидается явный допуск на конкретный payload/destination |
| Полный integration/browser CI, release/deploy, human acceptance | NOT_RUN | Следующий этап после Ready и нового номера; локальные узкие проверки не заменяют обязательный CI |

Исправлены выявленные во время разработки ошибки: моковые read-only fixtures
расширены под аддитивный read model; browser выявил последний poll за пределами
budget — callback теперь проверяет срок до GET; сохранён DOM следующей ситуации
для удержания фокуса. Финальные результаты относятся к исправленному коду.

Снимки: [готовность1440](evidence/preparation-1440.png), [готовность390](evidence/preparation-390.png),
[ошибка чтения1440](evidence/read-error-1440.png), [ошибка чтения390](evidence/read-error-390.png),
[следующая1440](evidence/next-preparation-1440.png), [следующая390](evidence/next-preparation-390.png),
[отчёт1440](evidence/report-preparation-1440.png), [отчёт390](evidence/report-preparation-390.png),
[администратор1440](evidence/admin-1440.png), [администратор390](evidence/admin-390.png).
Это синтетические API-состояния реального frontend, а не новые опубликованные сцены Site v10.

## Откат и передача

Revert commit04 возвращает прежние backend/UI; пересобрать dist штатной командой.
Аддитивная таблица может остаться неиспользуемой: откат не требует DROP, восстановления
или перезаписи оценок/snapshots. При выпуске сохранить обязательные frontend/pytest/
full-verification для актуального head после объединения открытых03/REPORT04.
Человеческая приёмка, номер кандидата, Ready, merge и deploy — следующий отдельный
этап владельца; этот отчёт не присваивает baseline, CURRENT или успешный Prod.

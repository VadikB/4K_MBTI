# EXEC-FIX-03 — восстановление неизвестной отправки

Поручение владельца 09.11.2026; только EXEC-FIX-03, C1–C9. Исполнитель — мой Codex,
P4K-EXEC-03-USER, chat 01a1c0f0-59de-7372-a176-def2c23bfe2a, единственный писатель
`codex/exec-fix-03-send-recovery`, `/private/tmp/USER_WORKTREES/exec-fix-03`.
Base: `46a5532336e41c5cdedf9684ba7bd5a9c5c202d1` (2.0.87, P3А+P3Б #199).
Предыдущая реализация 3А зачитывается по фактическим blobs/регрессиям; повторная
реализация transport identity не нужна. STATE и доказательства — внешний пакет
`outputs/p4k-exec-fix-03-20261109` в рабочем каталоге пользователя.

## Результат и границы

Уже имеются prepared/unknown/accepted/saved, устойчивые request/Turn ID,
endpoint/ASK/source phase, readback до retry и guards поздних callbacks.
Исправлены перенос draft в другой вопрос той же AS, отсутствие точного readback
старой AS и бессрочная блокировка отсутствующей операции после смены фазы.
Добавлен узкий owner readback исходной операции, доступный после закрытия/возврата,
без новой записи. Существующий delivery механизм сохранён и расширен адресно.

План: (1) адресный source/code/evidence audit; (2) readback одного ответа по
AS/request/Turn/ASK, phase/owner draft и reconciliation; (3) независимые C1–C9
HTTP/PG/Chromium проверки и shared replay с владельцем01; (4) review, exact SHA,
bundle, описание отдельного PR и вопросы архитектору.

EXEC01 единолично меняет общие write admission/replay/time/return handlers;
запрос координации отправлен в его существующий chat по поручению владельца.
EXEC03 меняет новый readback route/helper, delivery/draft и делегированный ниже
ordinary applied replay; общий
loader/presence/Finish/Next, schema, опубликованные snapshots не переписывает.
Новый GET совместим со старыми клиентами; возвращает только один собственный
Turn и его обработку, без hidden cards/history/AI. Отсутствие — наблюдение под
Cycle→AS lock, не обещание, что будущая новая запись невозможна. Старый endpoint
никогда не подменяется текущим. При смене фазы старая отсутствующая операция
выводится из активного slot только после успешного readback и хранится в архивном
session slot; новая фаза требует нового явного ввода.

## Источники и решения

00_START/START_CODEX/03_EXEC_FIX_03, 06_SOURCES_AND_DECISIONS и общие зависимости,
ресурсы/передача/TEST прочитаны. AGENTS, agent-workflow, verification-matrix,
artifact-recipe, README/CONTRIBUTING применены. Адресный маршрут: Product
Architecture1.0/Change01 И-1/2/4/5/6/7; SourceSet2026-10-01; M1v1.4 FROZEN/CURRENT=NO,
M5v1.1/M6v1.8/M7v1.3/M8v1.2; ADR002, M7 clarification/completion contracts;
WORKING glossary30.09 и UX-E01/ADD01/E02. Decision IDs и hashes — SOURCE_READBACK.md
в пакете. LU=Local Unit; Component=компонент навыка. Новых предметных норм нет.

Независимый review источников/кода выполняется read-only агентами по действующей
инструкции среды; только root пишет worktree. Стоп-условия: предметные сущности,
схема/миграция, новый контур, данные, deploy/публикация не меняются. Узкое совместимое
owner-readback прямо предусмотрено карточкой; реализация и локальные проверки
разрешены прямым поручением. PR/push/version_bump/merge/deploy/paid LLM=false.

## Проверки и откат

Node frontend, lint/build/diff; backend/unit+HTTP, integration на marker-owned
локальной PostgreSQL19332; Chromium real HTTP19331, route.fetch commit→abort,
recovery+reload/two tabs/same key/content conflict/new identical answer/M7 ASK,
owner/AS/question/late receipt, закрытие/time совместно с01. Считать сохранённые
Turns/events/effects, не только DOM. Никаких успешных fake POST.
CI/human review и TEST deploy/readback остаются архитектору; physical mobile
keyboard/owner visual acceptance не объявлять PASS по Chromium.
Откат: revert собственных коммитов; старые клиенты продолжают существующие POST,
Turn/историю/snapshots не удалять. Клиентские legacy ordinary drafts сохраняются;
не привязывать их автоматически к ASK или другому owner.

## Локальные проверки и совместная приёмка

Исправлены draft owner/ASK/revision и capture до lazy import, legacy revision
migration; неизвестный исход восстанавливается точным non-cacheable owner GET.
Документированные external delivery/submit/wiring sections7f0a77b совпадают с
base46a5532 побайтно (EXTERNAL_REUSE.json); готовое не реализовано повторно.
Backend1018, HTTP142, integration254 PASS;2 real-provider tests пропущены.
Эти полные наборы выполнены на867dbdd; весь API и pytest source с тех пор
побайтно неизменен. Финальные frontend211, lint/build/diff PASS после
дополнительной processing regression. Exact SHA/команды/exit/evidence и blob
mapping содержатся во внешних CHECKS.csv/BACKEND_TEST_REUSE.json/HANDOFF.
Actual Chromium ordinary loss-before/after commit, reload/two tabs/late response,
keyboard320/account401/403, M7 phase/ASK и C9 проверяются в отдельном compose
checkout01+03. Три полных сценария R1 прошли на2e11dab; финальный SHA и повтор
после processing fix зафиксированы во внешнем HANDOFF, а не подменяются этим SHA.
На base найден duplicate pipeline projection M7 replay, исправленный owner01;
его исходные коммиты не включены в отдельный candidate03.
Полный CI/TEST/human visual acceptance не выполнялись и не заменены local PASS.

### Согласованное владение ordinary replay

CONTRACT_03.md владельца01 (2ffd976,09.11.2026) адресно передал в03
`m5_scenario_runtime.submit_turn_detached` и `routes.submit_owned_m5_turn`.
Добавлен только lookup уже applied receipt до допуска новой записи: owner первым,
исходный scoped request+checksum(turn/content), точный result_json, никакого provider
или effect. Pending/failed/rejected_late не получают write bypass. Новый reader
не берёт operation FOR UPDATE после Cycle/AS; существующий порядок блокировок
write path не расширяется. Actual PG:6 границ + held-provider retry PASS7;
неизменны Turn/events/rule decisions/AI attempts/C54/operations/handoff counts.
До этой квитанции общие symbols не менялись. M7/return/time semantics01 не правились.

### Recovery после границы AS/Cycle

Pending исходной AS восстанавливается также после её закрытия/Next и на входе
экрана обработки. Читаются только существующие pending ключи текущего owner/Cycle;
исходные endpoint/identity не меняются. Ответ старой AS не рендерится в новой,
поздний readback проверяет owner/identityEpoch/Cycle и снимает только свой slot и
свою draft revision. На processing без серверного runtime разрешена только
очистка conclusive accepted applied/answered/rejected_late; absent/pending/failed
сохраняют исходную identity и draft. Сам переход экрана не доказывает смену фазы.
Добавлены6 production-function регрессий, включая этот крайний случай.
`processing.openProcessing` добавляет только вызов восстановления результата
ответа; status/report pipeline и общий runtime loader не менялись.

В отдельном R1 test entrypoint `exec03_preview.py` переиспользуются marker-owned
bootstrap/seed из p3-a-preview и существующий deterministic AI gateway. Scope
assessment, R1 snapshot,7200/259200 остаются реальными; QA usage switch выключен.
Новые прогоны сохраняют server startup fingerprints API/JS/dist/spec и точный SHA.
Clock fixture меняет только наблюдаемый elapsed interval, не бюджет/политику/
snapshot/Turn. Ожидаемые expiry events/final handoff отделяются от новых ответов.

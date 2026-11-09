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
Остатки: старый draft переносится в новый вопрос той же AS; неизвестная отправка
отсутствует, но смена фазы оставляет бессрочную блокировку. Текущий runtime не
показывает старую AS и не публикует request identity. Нужен узкий owner readback
исходной операции, безопасный при закрытии/возврате, без новой записи.

План: (1) адресный source/code/evidence audit; (2) readback одного ответа по
AS/request/Turn/ASK, phase/owner draft и reconciliation; (3) независимые C1–C9
HTTP/PG/Chromium проверки и shared replay с владельцем01; (4) review, exact SHA,
bundle, описание отдельного PR и вопросы архитектору.

EXEC01 единолично меняет общие write admission/replay/time/return handlers;
запрос координации отправлен в его существующий chat по поручению владельца.
EXEC03 меняет только новый readback route/helper и delivery/draft hunks; общий
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

## Локальный результат до совместной приёмки

Исправлены draft owner/ASK/revision и capture до lazy import, legacy revision
migration; неизвестный исход восстанавливается точным non-cacheable owner GET.
Документированные external delivery/submit/wiring sections7f0a77b совпадают с
base46a5532 побайтно (EXTERNAL_REUSE.json); готовое не реализовано повторно.
205 frontend,997 backend,122 HTTP PASS;247 уникальных integration PASS после
исправления STAND_ADMIN_URL;2 real-provider integration NOT_RUN. Narrow readback
unit/HTTP32 и closed-AS PG1 входят в эти наборы. Lint/build/diff PASS.
Actual Chromium ordinary loss-before/after commit, reload/two tabs/late response,
keyboard320/account401/403 и C7 phase/draft/ASK recovery пройдены до shared M7
replay assertion: на base46a5532 identical replay меняет pipeline revision.
Эта красная регрессия передана01, не замаскирована как local PASS. Общий C9
вынесен в отдельный compose checkout01+03; exact SHA/evidence во внешнем HANDOFF.
Полный CI/TEST/human visual acceptance не выполнялись и не заменены local PASS.

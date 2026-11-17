# P4K-POSTW02-03 — публичные команды участника

Прямое поручение владельца 16.11.2026: «запусти 3 задание». Требования —
P4K_POSTW02_03_Participant_Commands.txt rev1.0 и PAUSE_DECISIONS_AUDIT.txt из
предоставленного пакета POST-W02. Вложения описывают результат и ограничения;
источник полномочий — запрос владельца запустить это задание.

База: origin/main `99d2251` (2.1.16), проверена fetch; POSTW02-01/02 уже слиты.
Ветка `codex/p4k-postw02-03`, отдельный worktree `p4k-postw02-03`.
branch_push=true, pr=true (один draft), merge=false, deploy=false,
version_bump=false, artifact_publish=false. Допуск охватывает локальный код,
синтетические проверки и передачу результата; без Prod, реальных LLM/почты,
реальных данных, миграций, новых Docker/БД и полного PATH.

## Результат и границы

Публичные Cycle/control, Cycle/completion и AS/transitions отклоняют новые
ручные pause/interrupt_for_continuation до мутации с HTTP409 и
`M7_PARTICIPANT_MANUAL_CONTROL_NOT_ALLOWED`. reason не определяет полномочия.
Сохранённые команды читаются до запрета с проверкой идентичности запроса.
Resume восстанавливает только подтверждённую старую паузу текущей незакрытой AS
с сохранением лимитов и обязательного return-continue. Pending continuation intent
потребляется существующим путём. Внутренние и admin/QA вызовы сохраняются.

PM-04 / существующий runtime Cycle/Session/AS; схема, предметные definitions,
R1 algorithm/snapshots, W02, профиль и анкета не меняются. LU — Local Unit;
Component — понятие методологии.

## Прочитанные источники и решения

Все repo-источники на base99d2251: AGENTS.md, README.md, CONTRIBUTING.md,
docs/evc/{agent-workflow,verification-matrix,artifact-recipe,review-checklist,
decision-register}.md; docs/architecture/product-4k/{registry.md,1.0/context.md,
1.0/updates/2026-10-01/README.md,1.0/updates/2026-10-01/source.md} (адресные
разделы Change01 о Cycle, времени, повторах и правах); task SourceSet manifest.json;
M7-v1.3.md §§5.3–5.5,6.3 (FROZEN/CURRENT=NO); m7-completion-contract.md и
m7-return-time-integration.md (их исторические draft/QA границы не повышаются).
Глоссарий WORKING30.09 прочитан адресно из предоставленного ранее ресурса
P4K_EXEC_FIX_03_2026-11-09/resources/Product_4K_Common_Glossary_Reconciliation_WORKING_2026-09-30.docx:
AS, Session/Cycle, PM/LU/Component; он не заменяет поздние нормативные источники.
Прочитаны STATE POSTW02-02, Api/m7_completion*, m5_scenario_runtime,
m5_cycle_runtime, m7_return_integration, затронутые routes и существующие тесты.
R1 основан на сохранённом решении18.10 из аудита и published пакете
sales-pilot-return-r1@2.0; это не permission policy. Snapshot Prod не исследован.
Реестр решений не содержит отдельного допуска ручной кнопки; новый запрет на
публичной поверхности задан текущим поручением. M7 по-прежнему допускает паузу
как внутреннее состояние. Конфликтов, блокирующих эту узкую реализацию, нет.

## План и проверки

1. Разведка, база, публичные пути — завершено.
2. Проверки публичного вызова после readback и безопасный resume — активно.
3. Адресные HTTP/unit/state tests; backend минимум; существующие R1 границы.
4. Review, отчёт/STATE, commit/push, один draft PR, checks точного head.

Локально: git diff --check; npm run test:backend; адресные HTTP tests с подменой
HTTP/time/provider. PostgreSQL-инварианты покрываются integration tests; при
отсутствии существующей изолированной TEST_DATABASE_URL — NOT_RUN до обязательного
CI перед Ready/merge. Новую инфраструктуру не разворачивать. Существующие R1 tests
переиспользовать для lease119/120, двух клиентов, повтора Continue и deadline.
Прошедшие наборы не повторять без изменения основания/новой ошибки.

Стоп-условия рабочего цикла: нет новых предметных норм/форматов, миграций,
неразрешённых PM/данных/контуров. Узкое изменение публичного поведения согласовано
заданием; сохранённые результаты/внутренние переходы совместимы.
Откат: revert собственного коммита; история/intent/snapshots сохраняются.
Он возвращает старую доступность ручных команд, поэтому требует решения владельца.

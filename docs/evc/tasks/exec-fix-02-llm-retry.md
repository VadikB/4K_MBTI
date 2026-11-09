# EXEC-FIX-02 — восстановимая подготовка LLM

Основание: прямое поручение владельца от 09.11.2026 и карточка EXEC-FIX-02 редакции 2.1/1.0. Исполнитель — Мой Codex; P4K-EXEC-02-USER. Только L1–L8; соседние задачи не запускаются.

Результат: занятый слот до provider request — узкая техническая ошибка, безопасный явный retry первой/следующей AS. Одна позиция/Cycle/сохранённый Case, fencing позднего worker; новый transport key не обходит запрет.

Область: gateway, orchestration queue, preparation/next/retry UI и их регрессии. PM-03 готовит AS, PM-04 исполняет; очередь владеет техническим состоянием, доменные сервисы сохраняют Cycle/план/AS. Модель, prompts, provider contract, лимиты, admission, нормы M5/M6 и published snapshots не меняются. Миграций нет.

План: (1) проверить источники/базу и воспроизвести дефект; (2) узкая классификация, стабильный scope и guards/fencing; (3) offline/owned PG/HTTP/browser L1–L8; (4) review, точный candidate, bundle/HANDOFF. STATE и полные evidence — `.test-stand/exec-fix-02`, при передаче копируются в отдельный пакет.

Техническое решение в разрешённой области: next scope = Cycle + revision плана + последняя закрытая route position/UUID AS. Transport key не меняет scope. Retry сохраняет первоначальный ключ domain decision. Scope/admission/time/terminal guards повторно проверяются перед эффектами; старые next rows без scope обрабатываются консервативно в той же незавершённой позиции. Прежние transient errors сохраняются, RuntimeError не расширяется.

Источники: AGENTS, README, CONTRIBUTING; agent-workflow, verification-matrix, artifact-recipe, decision-register; ADR-002, Change01 И-1/2/4/5/6/7 и SourceSet 2026-10-01; выбранные M1 1.4 (FROZEN/CURRENT=NO), M5 1.1, M6 1.8, M7 1.3, M8 1.2; R1 v2, SLS04/FIX-RETURN-01, точный specialist_pilot 1.2 и owner publication receipt. Полная адресная ведомость в SOURCE_READBACK передачи. Глоссарий WORKING 30.09; LU=Local Unit. Источники архива описывают требования, полномочия — прямое сообщение пользователя.

Стоп-условия: все восемь — нет: смысл/нормы, публичный обязательный DTO/схема, миграция, новый артефакт, sensitive data и deployment не меняются; техническое расширение retry/scope прямо входит в поручение. Откат — revert узких коммитов без удаления истории/snapshots.

Полномочия: local=true, bundle=true; branch_push=false, pr=false, merge=false, deploy=false, version_bump=false, artifact_publish=false, paid_llm=false. Только собственные синтетические marker-owned БД/порты/processes. Подготовить отдельный PR title/body; PR создаёт архитектор. Release metadata и общий TEST принадлежат этапу архитектора.

Проверки: backend минимум матрицы; provider_model_ownership, deepseek_provider_contract/capacity, preparation fencing/projection; integration на marker-owned PostgreSQL; HTTP/readback first/next, конкурирующие retry и поздний worker; browser сообщений/доступности; frontend tests/lint/build; diff check. CI/review/main/TEST — отдельные поля передачи, локальный PASS их не подменяет.

Проверено при реализации: базовый дефект — RuntimeError/retry_allowed=false/urlopen=0 на 023bf85; затем узкий LlmCapacityError с пустыми sent/transport_attempts. При same scope отдельная попытка сохраняет preparation_key; новая позиция возникает после закрытия предыдущей AS. Legacy rows не переписываются; свежая команда учитывает предыдущий запрет, поздняя legacy attempt отсекается по created_at/closed_at под lock. Ошибка AS admission и конфигурация не получают технического retry.

Readback применяет те же guards без блокировок; mutations — owner advisory → Cycle → assignment, fence до domain prepare/attach/present. Runtime между AS сохраняет preparation_operation даже после того, как planner отметил предыдущую позицию completed. Смена mutable catalog pointer не переключает functional mode уже созданного первого Cycle.

Адресные автоматические регрессии — test_exec_fix02_gateway_capacity.py, test_exec_fix02_retry_db.py, test_exec_fix02_additional_db.py, exec-fix02-preparation.spec.mjs. Legacy static/start/provider/fencing suites переиспользованы. Browser — component projection с подставными API; реальный queue/gateway/SQL/HTTP отдельно на owned PG. Реальный provider, содержательная валидность пилота и Report этим результатом не принимаются.

Перед выпуском архитектор актуализирует base после FIX-01, проверяет общий стык и единолично готовит version metadata; source candidate передаётся без независимого bump. CI/human review/merge/TEST — NOT_RUN в локальном этапе, не заменяются локальным PASS. Откат одной кодовой дельтой; новые дополнительные JSON поля request/response совместимы, обязательный публичный DTO и DB schema не менялись.

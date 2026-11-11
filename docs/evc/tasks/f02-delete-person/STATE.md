# STATE — F02

- Дата: 11.11.2026. Задача: только F02, исходная карточка `P4K-F02_Delete_Person.txt` v1.0.
- Ветка `codex/f02-delete-person`, base/origin/main `748be43e55587aa3b7e3a3945189c5ac737f59eb` / 2.0.97.
- Прочитаны инструкции, применимые архитектура/решения и P4K.DEV.PRINCIPLES; см. TASK.md.
- Решено: существующий purge, прямой вход из списка, отдельное снятие прав,
  серверные scope/protected guards, одна операция при unknown/reload, R01 receipt.
- Реализованы backend/frontend, R01, actor receipt, protected primary/verified aliases,
  auth lifecycle lock/token transaction, frozen multi-column attribution cleanup.
- AC01/03/04/05 actual browser+HTTP+PG PASS на финальном code SHA:
  `evidence/ac01-03-04-05-browser`. Active ordinary + dual account rich graph,
  independent 18-table negative checks, controls unchanged, localStorage cleanup
  failure, lost commit reply/reload/same operation. AC02 owned HTTP/PG PASS,
  `evidence/ac02`, включая 4 concurrency auth cases/late worker/readd.
- Промежуточно backend1081/HTTP144/frontend261 PASS, lint/build PASS; targeted
  scope/alias43 PASS. В первом integration ошибочно использован
  bootstrapped reference вместо пустой БД; failed fixtures затем PASS19 на
  новой marker-owned empty reference `product4k_pytest_cc13a3c974764f5a872c5193d84d5655`.
- Concurrency UPDATE/INSERT scope races закрыты: pin/re-expand до стабильной
  области, CTID consistency, locked ancestors/actor memberships. Backend50 адресных
  PASS, независимое review без новых actionable findings.
- Финальный code SHA: `15232259d5915d564c7c9551dd80941862c3cd9a`.
  На этом SHA backend1086/HTTP144/frontend261 PASS; lint/build и byte-identical
  dist PASS; actual F02/recovery/layout browser3 PASS51.9s. Полный integration
  на пустой owned reference/UTC:385 PASS/2 SKIP276.03s. Runtime после SHA не меняется.
- Final browser и AC02 evidence обновлены на exact SHA; AC01–AC05 PASS в локальном
  synthetic UI/HTTP/PG контуре. CHECKS содержит данные/expected/actual/evidence,
  PR.md — подготовленное описание одного PR, SOURCE.txt — исходная карточка.
- Новый кластер `/tmp/p4k-f02-owned-pg/data-utf8`, localhost55502,
  user `p4k_f02_owner`; все ресурсы synthetic/owned. Не читать state.json в вывод
  (там синтетический пароль/сессии); cleanup только через marker guard.
- CI NOT_RUN; main не менялся, TEST не проверялся;
  Human visual PENDING, приёмка владельца не заявляется.
- Собственные test БД удалены через marker без FORCE, independent remaining
  readback0; новый локальный PostgreSQL остановлен. Evidence сохранены.
- Новый прямой допуск владельца после передачи54f4b52: «выложи на main».
  Push/один PR/необходимый PATCH/mandatory CI/merge/штатный TEST разрешены;
  artifact_publish и pilot deploy false, Human visual PENDING.
- Fresh main748be43/2.0.97, фактический GitHub actor `bvvfructus-jpg`, push=true.
  Активно: canonical PATCH2.0.98 preflight → PR/CI → squash main → TEST/readback.
  Детали этапа в RELEASE.md. Соседние карточки не запускать.
- При восстановлении сессии перечитать этот STATE и исходную карточку F02.

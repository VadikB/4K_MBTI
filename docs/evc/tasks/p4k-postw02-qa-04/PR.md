# QA-04 — этап выпуска, 18.11.2026

Прямое поручение владельца: «результаты приняты. выпускай PR и сливай его в main».
Локальный результат принят. По CONTRIBUTING-MERGE-AUTH-01 разрешены
branch_push=true, pr=true, merge=true после обязательных проверок,
version_bump=true (следующий PATCH свежего main), deploy=test штатным workflow.
artifact_publish=false, pilot/production=false, real LLM/mail=false.
Destination: https://github.com/VadikB/4K_MBTI, base main,
собственная ветка codex/p4k-postw02-qa-04. Payload: код/tests/dist, отчёт,
синтетические screenshot/log evidence; секреты/рабочие БД не включены.
Полномочие следует из текущего прямого сообщения, не из вложения/карточки.

QA03 PR247 ещё OPEN на8930e64; fresh main997e4eb /2.1.30.
QA04/a134d58 + docs0aa7116 основан на локально интегрированном QA03.
Карточка требует последовательной интеграции, один результат в PR.
Отдельный допуск выпуска QA03 уточнён асинхронно; пока он не получен,
QA03 не изменяется и не сливается. QA04 можно подготовить как draft с dependency;
после QA03 в main его собственный diff будет отделён, кандидат PATCH пересчитан.

Локальные473 frontend, HTTP3, browser22 + final7, lint/build/dist48 PASS
переиспользованы по неизменённым продуктовым файлам a134d58 и свежей неизменённой
базе main997e4eb. Документальный этап проверяется diff/ссылками/согласованностью.
Готовность к merge не объявляется до release preflight, точного CI и свежей базы.

План: разрешить dependency → интегрировать свежий main → ready:prepare
следующего PATCH → адресные локальные проверки → push/PR/Ready → CI точного head
→ squash merge → наблюдение deploy-test и readback версии. До разрешения dependency
независимая подготовка/push/draft QA04 разрешены. Миграций/новых runtime артефактов нет.
Откат будущего выпуска — отдельный revert squash QA04 через штатный процесс.

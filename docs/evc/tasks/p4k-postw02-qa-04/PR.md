# QA-04 — выпуск2.1.32 разрешён, 18.11.2026

Владелец принял результат и поручил: «результаты приняты. выпускай PR и сливай
его в main». После точного вопроса о публикации кода, тестов, web/dist, отчёта,
синтетических screenshots/logs в публичном https://github.com/VadikB/4K_MBTI,
ветке codex/p4k-postw02-qa-04, PR/main и merge после CI ответил:
**«Разрешаю этот состав и публичный репозиторий»**.
Дополнительно: «третье задание слито в main. перепроверь и приступи к своей
выгрузке на main». Это новый точный допуск destination/payload после прежнего
automatic review rejection, не повтор отклонённого действия без нового основания.
branch_push/pr/version_bump/Ready/merge=true, deploy=test штатным workflow;
artifact_publish/pilot/production/real LLM/mail=false. Человеческая приёмка QA04
получена; обязательные release/CI gates сохраняются.

Проверено live: QA03 PR247 MERGED18.11.2026 10:25:54 MSK, squash
`e67cf7a859a5a5ebe5e8d63c1c66d0c463adf3fd`, main2.1.31. Зависимость закрыта.
Собственная ветка интегрирует свежий main. Конфликты были в generated dist,
корневом STATE и старых QA03 PR_BODY/STATE: dist пересобран, актуальные QA03 docs
сохранены из main, история STATE сохранена под актуальным этапом. Принятые
interview.js/wiring.js/answer-drafts.js/interview.css при интеграции не изменились.
Следующий PATCH2.1.32 следует из прямого merge-поручения и CONTRIBUTING-MERGE-AUTH-01.

План выпуска: canonical `npm run ready:prepare -- --candidate 2.1.32`;
frontend/HTTP/lint/build/diff и scoped Chromium после интеграции; own branch push,
один PR main, полный CI точного head, fresh-main check, squash merge, штатный
TEST deploy/readback. Проверки и SHA кандидата фиксируются ниже после результата.
Откат — отдельный revert будущего squash QA04 через штатные release/CI gates;
QA03, серверные Turns/интервалы/snapshots не переписываются.

---

## История предыдущего этапа

## Автоматический отказ публикации

Push862c36a в публичный VadikB/4K_MBTI отклонён automatic approval review:
«Push публикует код, тесты, сборку и отчёты в публичный GitHub-репозиторий;
поручение о PR/merge не явно разрешает передачу этого конкретного payload в
публичный destination, а такая чувствительная egress требует точного согласия».
Удалённая ветка/PR не созданы. Обход/повтор не выполнялись. Запрошен точный
допуск пользователя на этот destination и состав. Исходное поручение PR/merge
сохраняется, его техническая реализация ограничена этим отказом.
Независимый вопрос QA03 PR247 также ожидает ответа; его release не выполняется.

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

## Проверки кандидата2.1.32

Canonical ready:prepare PASS; frontend473 + receipt harness66 =539 PASS;
HTTP3 PASS, Chromium22 PASS (30.1s,1worker/0retries/0real LLM/mail), lint PASS.
Audit high gate PASS; предсуществующие moderate замечания не менялись.
Повторная сборка48 файлов побайтово совпала; diff/source review PASS.
Своих открытых fixture ports0, рабочих БД/.env не использовали.
Evidence: `evidence/release2132/`, новые screenshots1440/390/320.
Серверный API/БД и QA03 docs совпадают с main; продуктовый diff только QA04 + release.
Следующее: один PR в main, полный CI точного head; готовность merge определяется CI.

## Исправление CI browser expectations

CI82102ab: frontend/pytest/integration PASS; runtime shards выявили старое
требование скрывать весь #interview-error после успешного ответа. Эта зона
по QA04 теперь содержит нейтральный receipt. Пропущенные assertions исправлены
в runtime.spec и assessment-completion-profile, без изменения product source.
Проверка требует именно neutral receipt с допустимым текстом; failed/read error/
unknown не принимаются как успешная отправка. Проверки server trace, числа POST,
same-ID readback и разрешённых действий сохранены. Stalled-body test читает
unknown/accepted в новом месте статуса над composer. Лимиты/CI gates не ослаблены.

Локально после правки:539 frontend/receipt PASS;4 runtime cases PASS за2min
(positive/clarification/Report/PDF, lost response/idempotency, REV02, G10.7).
Собственный новый PostgreSQL cluster/test DB,1worker,0retries/LLM/mail; все свои
DB/HTTP процессы остановлены, порты закрыты. Секреты/.env/рабочие БД не читались.
Evidence: evidence/release2132/ci-repair-*. Старый CI не объявляется PASS;
новый push обязан пройти все checks точного нового head перед merge.

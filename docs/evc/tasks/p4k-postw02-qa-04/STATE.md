# QA-04 — обновление CI assertions, 18.11.2026

PR248, кандидат2.1.32, base e67cf7a. CI старого head82102ab нашёл устаревшие
assertions скрытия зоны после успешного ответа. Исправлены только test consumers
runtime/completion-profile и адаптер; продуктовый source/release неизменны.
Локально539 frontend/receipt +4 owned DB/runtime browser cases PASS, все свои
DB/HTTP процессы остановлены. Активно: push → полный CI нового head → merge.
Приёмка и точный публичный destination/payload допуск сохраняются; gates не ослаблены.
Подробности: [PR.md](PR.md).

---

# QA-04 — кандидат2.1.32 проверен, публикация разрешена

Свежая база e67cf7a /2.1.31, QA03/#247 MERGED. Интеграция fca17a6;
принятый продуктовый код QA04 не менялся. Canonical preflight2.1.32 PASS.
Локально:473frontend +66receipt=539, HTTP3, Chromium22, lint/audit-high/build48/diff PASS.
Свои fixture servers закрыты; LLM/mail0. Новый точный допуск: «Разрешаю этот состав
и публичный репозиторий» после вопроса о code/tests/web-dist/report/synthetic evidence
в публичном VadikB/4K_MBTI, PR/main и merge после CI. Старый отказ ниже исторический.
branch_push/pr/version_bump/Ready/merge=true, deploy=test штатно;
artifact_publish/pilot/production=false. Активно: PR → полный CI точного head → merge.
Подробности/проверки: [PR.md](PR.md), evidence/release2132/.

---

# QA-04 — выпуск после интеграции QA03, 18.11.2026

Получен точный ответ: «Разрешаю этот состав и публичный репозиторий» на запрос
о QA04 code/tests/web-dist/report/synthetic evidence в публичный VadikB/4K_MBTI,
с PR/main и merge после CI. Прежний отказ снят новым прямым допуском.
QA03 проверен: PR247 MERGED/e67cf7a, main2.1.31; локально интегрирован.
branch_push/pr/version_bump/Ready/merge=true, deploy=test штатным workflow;
artifact_publish/pilot/production/real LLM/mail=false. Следующий PATCH2.1.32.
Активно: canonical preflight → локальный минимум → PR/полный CI → squash merge.
Результат принят владельцем. Подробности/точные основания: [PR.md](PR.md).

---

# QA-04 — публикация остановлена automatic review, 18.11.2026

Готовый payload862c36a; push в публичный VadikB/4K_MBTI отклонён: reviewer
требует точного согласия на destination и код/tests/dist/report/synthetic evidence.
Remote ветки/PR нет, обхода/повтора нет. Запрошен точный допуск публикации;
отдельно ожидается решение QA03 prerequisite. Локальные проверки остаются PASS.
Полное основание: [PR.md](PR.md).

---

> 18.11.2026: результат принят; прямое поручение на PR/merge разрешает этап выпуска. Текущие полномочия и dependency — [PR.md](PR.md). Ниже сохранён локальный этап.

# QA-04 — локальный результат готов

18.11.2026. Ветка `codex/p4k-postw02-qa-04`; main997e4eb /2.1.30,
локально интегрирован QA03 до8930e64, его PR247 на старте открыт.
Код/tests/dist и финальный UI head **a134d583587226bbc624bb45d0e439a5db89a550**.
Собственные коммиты реализации:4fb6856, ebce9a3, a134d58. Версия не менялась.

C1–C8 PASS в controlled локальном контуре: frontend473, HTTP3, browser22;
после малых placeholder/типографика/blocked-label diff — QA04 browser7 PASS, остальная область22 неизменна.
Lint/build/dist48/diff PASS. Исправлены pending scroll, receipt/action label,
достоверность уведомления, placeholder и потеря draft при новом dialogue Turn.
QA01 conflict/CAS, POSTW02-05 lost ACK и QA03 Next/time сохранены регрессиями.
Снимки1440/390/320 и отчёт: [REPORT](REPORT.md), [TASK](TASK.md).

Прямое поручение: «запусти 4 задание». Приложение — источник требований, не
отдельное полномочие. branch_push/pr/merge/deploy/version_bump/artifact_publish=false.
CI/human review/живой TEST/real LLM/mail NOT_RUN. Причина живой задержки не заявлена.
Свои servers закрыты, созданных БД0, .env не читался, чужие ресурсы не затронуты.

Следующий шаг: приёмка владельцем. Перед внешней передачей сверить фактически
интегрированный QA03 и свежий main; публикация/PR/merge требуют своего этапа.
Открытых технических блокеров локальной карточки нет. Откат — revert a134d58, затем ebce9a3 и4fb6856,
без переписывания истории, интервалов, snapshots и QA03.

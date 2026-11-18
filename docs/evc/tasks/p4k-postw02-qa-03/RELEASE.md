# QA-03 — Ready и merge разрешены, 18.11.2026

Прямое поручение владельца: «Переводи PR #247 в Ready for review, запускай
полные проверки и после их успешного завершения сливай в main».
По CONTRIBUTING-MERGE-AUTH-01 разрешены branch_push/pr/version_bump/Ready/merge=true,
deploy=test штатным workflow после merge; artifact_publish/pilot/production=false.
Main997e4eb /2.1.30 актуален; кандидат — непосредственный PATCH2.1.31.
Границы QA-03 сохраняются; реализация interview.js8b3ca49 не меняется.
Активно: canonical ready:prepare → release commit/push → Ready → все обязательные
CI точного head → свежая база → squash merge → наблюдение штатного TEST deploy.
Старые false flags ниже относятся к прежним этапам и заменены этим поручением.

---

Исходный PR head8930e643c7bed6f780b65af92f73e6f15481ac3c;
быстрые CI frontend/pytest PASS. Предыдущие локальные frontend463/HTTP3/browser12
и DB3 применимы к неизменённой реализации; новый выпуск требует release gate
и полного GitHub CI. Реальные LLM/почта не запускаются. Откат выпуска — revert
итогового squash через штатный PR/CI, без изменения операций/интервалов.

Canonical ready:prepare2.1.31 PASS; release frontend463/lint/diff PASS.
Изменились только согласованные metadata версии, dist и документы.
Полный CI запускается переходом Ready для опубликованного release head.

Первый полный CI44255445204 на3e30584: frontend/pytest/integration и четыре
runtime browser shards PASS; fast lane FAIL на трёх тестовых ожиданиях.
1) auth-r03 timer: обновлён короткий текст, unknown/zero assertions сохранены.
2) invitation fixture: дата17.11 зафиксирована управляемыми часами, без зависимости
от фактического дня18.11. 3) restoration: счётчик questionnaire проверяется после
async GET через expect.poll, ожидается по-прежнему ровно1. Product code unchanged.
Адресный browser3 PASS за2.5s, worker1/retries0, реальные LLM/mail0. Logs сохранены.
Новый head пройдёт полный CI; merge до успешного результата не выполняется.

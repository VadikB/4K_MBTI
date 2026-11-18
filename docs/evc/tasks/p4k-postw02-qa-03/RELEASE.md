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

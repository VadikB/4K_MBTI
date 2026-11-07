# Состояние бесплатной диагностики анкеты

- Worktree: `/Users/vadim_bogachev/Developer/4K/worktrees/ac18-questionnaire-it-inputs`.
- Branch: `codex/ac18-questionnaire-it-inputs`; product base/main61f34aa/2.0.71.
- Предыдущий рабочий шаг e9330ed6: подтверждённая синтетическая ИТ-анкета.
- Текущий шаг завершён:4 actual HTTP/PostgreSQL diagnostic scenarios,3 product FAIL
  (потеря ввода),1 положительный контроль; backend/UI/runner не исправлялись.
- Источники во время проверки: e9330ed6 + новые diagnostic files с точными hashes
  в run.json. Доказательства —43 case-files; offline consistency PASS.
- Cases tree SHA256: `f0d742e438b7c642237c25675ec1e523ef3d6c3c2736b7e616fe7da9d480661c`.
- 4 owned-БД/state удалены штатно без FORCE, maintenance count0, task-контейнер
  PostgreSQL16 остановлен и ephemeral слой удалён; raw state/logs не экспортировались.
- CI diagnostic diff NOT_RUN; branch_push/pr/version_bump/merge/deploy/artifact_publish=false.
- Fresh origin/main61f34aa; последняя проверенная test deployment2.0.71 без новых действий.
- AC18 BLOCKED и не повторялся. LLM0, постоянная БД/программа не менялись.
- Q-DRAFT-01 воспроизведён; историческая причинная связь с конкретным AC18 NOT_PROVEN.
- AC18-TIMEOUT-CLEANUP-DIAG-01 и PREP-DIAG-01 отдельно UNKNOWN.
- Следующий зависимый шаг: отдельное разрешение узкой локальной UI-правки сохранения
  scoped draft и регрессий. Платный PATH/выпуск этим разрешением не подразумеваются.
- Полный отчёт: `docs/evc/reports/ac18-questionnaire-draft-diagnosis.md`.

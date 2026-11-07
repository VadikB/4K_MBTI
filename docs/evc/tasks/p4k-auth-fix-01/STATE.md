# P4K_AUTH_FIX_01 — выпуск на test разрешён 07.11.2026

Текущий этап: [карточка выпуска](../p4k-auth-fix-01-release.md).
Прямое последующее разрешение владельца: branch_push/pr/version_bump/merge/deploy-test=true,
merge только после CI и человеческого review; artifact_publish=false.
Prod/pilot/реальная почта/продуктовые LLM/изменения рабочих данных не разрешены.
Кандидат 2.0.76 относительно свежего main65c1f4c (2.0.75); ready:prepare и полный
применимый локальный минимум, затем обязательные CI/review, PR squash и deploy-test.
Точные SHA и результаты: outputs/p4k-auth-fix-01-release-20261107/ исходного workspace.
Снимки ниже исторические: прежние запреты относятся к прежнему этапу.

## Исторический срез локальной передачи 07.11.2026

- Продолжение: `docs/evc/tasks/p4k-auth-fix-01-completion.md`.
- Исходный f78cb4a сохранён в verified bundle;50 evidence-файлов — в постоянной
  папке `outputs/p4k-auth-fix-01-completion-20261107/backup/` исходного workspace.
- Fresh main65c1f4c/2.0.75 включает MERGED PR174 и180. Локальная интеграция
  сохраняет AUTH и новое main поведение; release не повышается.
- B-01: ALREADY_FIXED(PR174); обязательные управляемые S01/02/03 и прежниеguards
  проверяются на итоговом сочетании; дублирующий runtime fix не добавлялся.
- Актуальный exact candidate/tree, результаты финального минимума и INT-01,
  AC/TC/FIN, blocker/next action — новый постоянный `06_RESULT.json` и `STATE.json`
  в `outputs/p4k-auth-fix-01-completion-20261107/`. Они создаются после фиксации SHA.
- Публикация/push/PR/merge в main/deploy/bump/mail/LLM не разрешены. Автономность
  и текущий профиль разрешений не являются gate этого продуктового завершения.

## Исторический срез 05.11.2026 (не переписывать FAIL)

- Ветка: `codex/p4k-auth-fix-01`, worktree `/private/tmp/p4k-auth-fix-01-20261105`.
- Base/audit: `e63eba67d77fb73f7fb9bb219bc3fe5d3807a909`, релиз2.0.66 сохранён.
- AUTH-V01/AUTH-F01 реализованы, bundle пересобран. Входные материалы вне Git.
- Наблюдаемый остаток: исходный browser FAIL missing-browser-session/journey401,
  воспроизведён отдельно на неизменённом main. Новые2F01 дефекта исправлены.
- Exact commit/tree, итоговые результаты всехAC/TC, команды/exit codes и INT-01:
  внешний `outputs/p4k-auth-fix-01/06_RESULT.json`; краткий `REPORT.md` в той же папке
  исходной задачи. Сам commit не содержит свой SHA; он записывается после фиксации.
- Следующий шаг: решение владельца по отдельной прежней гонке recovery; после её
  устранения повтор затронутого набора и INT-01. Пока не заявлять локальную готовность
  к выпуску при обязательном FAIL. Новые права на выпуск не предоставлены.
- CI/push/PR/bump/merge/deploy/publish/реальная почта/LLM не выполняются.
- Откат: только свои коммиты/патч, исходная пользовательская копия не менялась.

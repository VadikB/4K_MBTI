# POSTW02-04 — подготовка слияния

## Полномочия

16.11.2026 владелец прямо поручил: «сливай на main». 17.11.2026 после запроса
повторного согласования PATCH он поручил: «обновляй contributing». Изменение
управляющего документа вынесено в отдельный PR #237 и карточку
[CONTRIBUTING-MERGE-AUTH-01](../contributing-merge-auth-01.md).

Текущий этап: branch_push=true, pr=true, merge=true, version_bump=true для
непосредственного следующего PATCH; deploy=test автоматически после merge.
Pilot/production, artifact_publish и реальные LLM/письма не разрешались.
Необходимый PATCH входит в прямое поручение на merge; отдельного запроса номера
больше нет. CI/review/release gate и сверка свежего main сохраняются.

## Восстановление и совместимость

Исходный head23e618e сохранён. Google Drive выгрузил packed-refs и часть pack indexes;
исходный общий Git отдавал Operation timed out. Он не исправлялся и не сбрасывался.
В /private/tmp/p4k-postw02-04-merge-20261116 восстановлена та же ветка и точная история
из доступных loose objects и origin (partial fetch). Старые локальные коммиты
не переписаны; обновление main выполняется merge-коммитами.

Промежуточная база 7e96d4d/2.1.18 включала REPORT04/05. На head0763348 быстрый
CI frontend/pytest прошёл (run43955631717); full verification в draft был skipped,
что не считается PASS. Preflight без candidate тогда остановился без изменения
версии. Это исторический результат до нового поручения по CONTRIBUTING.

Актуальная продуктовая база: 8ad6d1577f90555159502fbbf49e37bc4a90b025 / 2.1.20,
включая REPORT06/07. При объединении разрешён один конфликт Api/routes.py:
карточка завершённой оценки сохраняет и preparation из POSTW02-04, и название
программы из history нового main. Остальные конфликты generated dist разрешены
общей пересборкой. Подготовка, попытки, диагностика, сохранённые ответы и snapshots
не удалялись. Метки готовности и время берутся из прежних серверных контрактов.

## Проверки после объединения

На интеграционном head5561e6e: frontend364 PASS, lint PASS, build PASS,
browser3 PASS (1440/390/320 CSS px), Python syntax PASS. Все три экрана подготовки
и карточка администратора повторно просмотрены на desktop1440 и mobile390;
автопроверки дополнительно покрывают320. Новые58 PNG с размерами/SHA256 и логами
сохранены в outputs/p4k-postw02-04-20261116/release-20261117 родительского workspace.
Исторические58 PNG evidence/review не перезаписаны; browser runner использует
POSTW02_EVIDENCE для независимых прогонов. Проверенные снимки содержат footer2.1.20;
последующее назначение2.1.21 меняет release/cache references, а не представление.

Локальные Python/HTTP suites на восстановленном checkout не запускались: Google
Drive не отдаёт pyvenv.cfg прежнего venv. Проверка Python syntax не заменяет suites;
их и integration/browser подтверждает обязательный CI точного кандидата.
Исторические1143 unit/178 HTTP для head0763348 не объявляются новым прогоном.

`npm run ready:prepare -- --candidate 2.1.21` — PASS: непосредственный PATCH
от2.1.20, согласованные pyproject.toml/uv.lock/config/index, frontend пересобран,
release gate пройден. После продвижения main сначала обновляется база и повторяется
preflight; если версия базы изменится, пересчитывается следующий PATCH.

PR #235 переводится Ready после push подготовленного кандидата. Слияние допускается
только после frontend/pytest/full-verification на его точном head, без bypass.
Окончательные SHA, обязательный CI, merge и deploy-test фиксируются после действий
в PR и outputs/p4k-postw02-04-20261116/RELEASE_DELIVERY.json родительского workspace.

Откат представления: revert0145485 с пересборкой. Откат всего выпуска — отдельный
revert squash-коммита PR #235 с обычным выпуском и обязательными проверками.

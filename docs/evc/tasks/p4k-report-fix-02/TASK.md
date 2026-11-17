# P4K-REPORT-FIX-02 — сравнение, оболочка и локальный просмотр

17.11.2026. Основание требований: переданные владельцем задание 2 rev1.0 и
reference rev1.0 (v10 e44fa78e). Полномочие: прямой запрос «запусти задание 2».
Вложения задают требования; внешние действия из них не получают отдельного допуска.
База `71a9c53` / 2.1.28, чистая main; ветка `codex/p4k-report-fix-02`.

Результат: сравнение двух сохранённых оценок с двумя сериями, четырьмя исходами,
публичными ограничениями и основаниями каждой стороны; реальный PDF той же пары;
воспроизводимое меню P01–P06 без сервисов/БД/LLM. Оболочка POSTW02 для отчёта,
сравнения и истории; адресная проверка ADMIN. REPORT-11, Scores, admission,
Results/C-67, права, публикация и схема БД вне области.

Прочитано на базе: AGENTS, README, CONTRIBUTING, agent-workflow,
verification-matrix, artifact-recipe, task-template; architecture context/registry,
Change 01 README/source (C-67, LU-06.2/06.4, LU-07.1/07.2), task source manifest,
M8 v1.2 (исходы, §7.3); m8-results-report и partial-result contracts;
decision-register, STATE, FIX-01 TASK/CHECKS и код/тесты REPORT-04/05/06/07/09/10.
Reference: README, LOCAL_PREVIEW_EXPECTATIONS, UI_BASELINE, локальные review.js,
report.mjs/html/css и сцены report-overview/direction/skill/evidence/limited/
unscored/insufficient, comparison/limited/role. M8 FROZEN/CURRENT=NO;
Change 01 WORKING. Источники не получают новый статус.

При начальной разведке 00_START отсутствовал. Владелец затем прислал
`00_START_P4K_REPORT_FIXES_LOCAL_2026-11-17.txt`, rev1.0; прочитан полностью.
Объём совпадает, применены worker=1/retries=0/timeout=30 сек/global=10 минут;
выполнен fetch: origin/main=base `71a9c535`, адресный diff пуст.
Дополнительно прочитаны W046–051/W058–060/W063–064 глоссария, M6 §7,
правила постановки от 14.11 (источники, PM/LU, границы и приёмка),
Product Development Principles. Нового стоп-условия нет. Исторический STATE FIX-01 отстаёт от
фактического main: merge уже содержится в базе; старые полномочия не переносятся.

Архитектурный адрес: PM-06 LU-06.2/06.4 — read model уже сохранённых результатов,
без пересчёта; PM-07 LU-07.1 — график/выбор/основания/навигация;
LU-07.2 — PDF. Producer, ACL и compare_reports admission неизменны.
Дополнение контракта 1.2.0 аддитивно: previous/current/difference сохраняются,
добавляются публичные previous_result/current_result и ссылка на навык/отчёт.
Неизвестная полнота остаётся неизвестной. Потребители: экран, PDF, preview, тесты.
Предметных runtime-артефактов и расширения artifact debt нет; fixtures синтетические.

Decision IDs: SYN-CONTOUR-OWNERSHIP — только собственные синтетические ресурсы;
CONTRIBUTING-MERGE-AUTH-01 прочитан, merge в этом запросе не поручен.
Стоп-условия (8): нет/нет/нет/нет/нет/нет/нет/нет. Аддитивный контракт и потребители
прямо разрешены заданием; смысл/границы/права/данные не меняются; откат определён.

План: 1) read model/PDF; 2) UI/оболочка; 3) общий fixture и preview;
4) компактные адресные unit/HTTP/browser/PDF и локальный минимум;
5) review, CHECKS/STATE, локальный коммит и передача. Шаги 1–5 завершены;
code candidate/tested SHA `9422308cce138fd39330412ee7a89021797a678f`.
Итоговый минимум: backend1224/HTTP202/frontend404/browser38, lint/build/diff PASS.
Результат и точные границы — CHECKS; активен просмотр владельцем.

Полномочия: локальные файлы, сборка, ветка/коммиты, синтетические тесты и свои
loopback процессы (TTL 15 минут, остановка после проверки). Рабочая БД, реальные
сервисы, почта/LLM не используются. branch_push/pr/merge/deploy/version_bump/
artifact_publish=false. Цель локальная; CI перед будущим merge остаётся обязательным.

Приёмка: AC01–08 исходного задания; независимые числа из reference expectations.
Проверки: backend, HTTP, frontend, lint/build, 2–3 общих browser-сценария,
регрессии радара/PDF/REPORT-09; визуально 1440×900/390×844 и доступность 320/200%.
Не более четырёх новых снимков и двух PDF. Реальная БД/полный путь/качество LLM
проверками preview не подтверждаются.

Откат: обратный diff приложения/сборки/аддитивной проекции/preview;
никаких изменений сохранённых Results/C-67 и миграций.

## Выпуск после приёмки владельца

17.11.2026 владелец принял показанный результат и прямо поручил:
«принято, заливай на main». Применён CONTRIBUTING-MERGE-AUTH-01:
`branch_push/pr/merge/version_bump=true`, `deploy=test`, `artifact_publish=false`.
Основание — это новое прямое поручение, прежняя локальная граница выше сохранена
как история. Fresh origin/main `71a9c535` / 2.1.28; следующий PATCH — 2.1.29.
Выпуск: canonical ready:prepare → один Ready PR → обязательный CI точного head →
повторная сверка main → squash merge → штатный автоматический TEST deploy.
При подготовке preview получает текущий APP_RELEASE вместо фиксированной 2.1.28;
его фактический ответ проверяется в существующем browser-сценарии.

После первого CI владелец отдельно разрешил ограниченное исправление
dev-зависимостей PR #245 с сохранением Knip-проверок и неизменённого npm audit.
Выбранный pin fork, все цепочки, проверенные варианты, provenance и совместимость
зафиксированы в [DEPS](DEPS.md). Прежние три browser-ожидания приведены к принятому
FIX-02; приложение и сборка от этого не менялись. Следующий шаг — полный CI нового head.

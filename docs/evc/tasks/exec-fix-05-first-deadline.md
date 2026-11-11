# EXEC-FIX-05: первое достигнутое основание закрытия

Основание: прямое задание владельца от 11.11.2026 и пакет EXEC-FIX-05.
Исполнитель — мой Codex; сессия `P4K-EXEC-05-USER`; единственный писатель в
`codex/exec-fix-05-first-deadline`, worktree
`/private/tmp/USER_WORKTREES/exec-fix-05-first-deadline`.
Свежий remote main/base: `e6b294e43811fb67afb695506f15547e5efc5f9e`, 2.0.94.
Соответствующей начатой ветки локально/удалённо нет; чужие деревья сохранены.

## Результат и границы

Поздняя обработка двух истёкших временных ограничений сохраняет причину и
`m7_transition_events.effective_at` первого достигнутого предела. Точность
FIX04, collecting-only, паузы/ожидания, календарь, R1/Continue, блокировки и replay
сохраняются. При равенстве сохраняется совместимый технический приоритет
`calendar_deadline`. Дата обработки закрытия и `C-46.collection.closed_at`
остаются датой обработки; новых полей API/БД нет. Закрытые Cycle не пересчитываются.

Найденный дефект воспроизведён настоящим `complete()` на новой owned PG:
бюджет закончился за 5 секунд до наблюдения, календарь за 1 секунду; возвращены
и сохранены `calendar_deadline` и timestamp на 4 секунды позже правильного.
Calendar-first/budget-only — положительные контроли. Исходные логи не переписаны.

## Источники и прослеживаемость

Прочитаны START/TASK/COMMON_WORKFLOW, AUDIT/FINDINGS, предыдущий FIX04 и
P4K.DEV.PRINCIPLES 1.0 из архива; README, CONTRIBUTING, AGENTS,
`docs/evc/{agent-workflow,verification-matrix,artifact-recipe,task-template,review-checklist,decision-register}.md`,
применимые STATE/карточка FIX04, архитектура Product 4K 1.0 context/registry,
Change01 WORKING и SourceSet `docs/methodology/source-sets/2026-10-01/manifest.json`;
M7 v1.3 §§5.3–5.6/7, ADR002/003, completion/return контракты,
glossary WORKING 2026-09-30 (Cycle/Session/AS/Dialogue/LU).

M7 §5.3 «Первое наступившее основание … независимо от остатка по другому параметру»
→ PM-04/LU-04.6 → completion/C-46 → `Api/m7_completion._effective_limit`
→ `test_exec_fix05_first_deadline*`. `PILOT-120` и первичная карточка ARCH-A05
подтверждают 7200/259200 в своей области. Опубликованные определения/снимки,
пороговые значения, prompts, providers и схема не меняются; предметный долг не расширен.

M7 original SHA256 `50a0d53a3aaf6258957ecc6d9e89f27d922bfbe4cd55668185d475c87f4e2f10`;
derived `9b65a8eee1520fed57286b209a28ce73e33cd394ba8c9353c240673867483ec8`;
Change01 PDF `dfc868fd8c2b306e2614e0971759850873da22b354dbe94823c8921460a95081`;
glossary `95bdc36d5ccb7d2da93d268ec6cb2012daace2b85878f0ffefc39e9d4c66b95d`.
Исторические glossary REVIEW не отменяют выбранные FROZEN SourceSet.
Устаревшие registry-ссылки на product-4k/m7-* разрешены по фактическим
`docs/architecture/m7-completion-contract.md` и `m7-return-time-integration.md`.
Конфликтов обязательных норм не обнаружено; нового решения владельца не требуется.

Стоп-условия: изменение смысла — нет (исправление по существующей норме);
API/PM/схема — нет; миграция/удаление данных — нет; новый артефакт/публикация — нет;
доступ/секреты — нет; несовместимость/неопределённый откат — нет;
неизвестная обязательная норма — нет; неразрешённые внешние действия — нет.

## План и полномочия

1. Разведка/воспроизведение базы — завершено.
2. Узкий алгоритм: единый DB clock после Cycle lock, точный crossing collecting
   intervals, выбор раннего достигнутого timestamp; календарь выигрывает равенство.
3. Unit, actual PG/HTTP, late worker/replay, FIX04 и адресные M5/M7/R1;
   полный backend + HTTP по матрице; diff/review и проверка финального SHA.
4. Bundle, base/candidate/tested SHA, PR description, команды/результаты,
   checksums, зависимости/вопросы и независимый импорт bundle.

Прямой запрос разрешает реализацию, бесплатные локальные проверки и передачу.
`branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. PR аккаунта пользователя запрещён.
Собственные marker-owned PG/порты/state/evidence изолированы; shared TEST/Prod и
paid LLM исключены. Обязательные CI/human review и назначение версии — выпуск
архитектора. Локальная передача их не заменяет.

Риск: неверное сравнение или округление даст позднюю/раннюю причину. Контроль —
дробные интервалы, один DB timestamp, точный timedelta, независимые PG readbacks.
Frontend не меняется; UI/browser/paid/full product path этой задачей не требуются.
Откат: revert собственного коммита; историю/evidence/сохранённые Cycle не менять.
Следующий выпуск: EXEC-FIX-05 → ACCOUNT-DELETE-FIX-01 → EXEC-CONTOUR-FIX-02.
Итоговые SHA, логи и статус — в отдельном handoff-пакете и соседнем STATE.

# P3-A — чат и мобильная работа

Основание: прямое поручение владельца 09.11.2026 распаковать
`P4K_P3A_My_Codex_2026-11-09.zip` и выполнить START_CODEX. Архив проверен
по всем 14 SHA256SUMS; внешние reference в продуктовый Git не переносятся.

Результат: одна разрешённая AS в чате, различимые авторы, доступный на телефоне
ввод, безопасный черновик/отправка и воспроизводимый синтетический просмотр.
Критерии: P3-AC01/02/03 и вклад 3А в AC10; итоговый AC10 — 3И, визуальная
приёмка — владелец. Этот saved-AS runtime тест не доказывает AC18 полного пути.

## Область и источники

- PM-04, только слой UI и локальные тестовые инструменты. Cycle/AS/Dialogue/Turn
  не смешиваются. API, БД, методология, time/progress/return 3Б, AUTH,
  published policies, CI/gates, версия и выпуск не меняются.
- Base `023bf85ec796d212d29b33218d906a1ed2023941`, source 2.0.86; свежий fetch
  09.11.2026 совпал с MAIN_BASELINE. Существующий dev checkout сохранён.
- Прочитаны START, TASK_3A, COMMON_EXECUTION, CONTRACT_AND_OWNERSHIP,
  RELEASE_AND_PERMISSIONS, HANDOFF_TEMPLATE, SOURCES, VISUAL_ACCEPTANCE;
  UX-E01 rev1.3 и приоритетный ADD01, FIX-RETURN-01, R1 v2 reference.
- Repo: AGENTS, README, CONTRIBUTING, EVC workflow/matrix/artifact recipe,
  decision register и первичные адресные основания; Product 4K context/registry,
  Change01 и M7 v1.3. Подробный readset — во внешнем evidence этой задачи.
- Применимы ARCH-A05/PILOT-120, PATH-PILOT-01/PATH-START-01-SCOPE,
  SYN-CONTOUR-OWNERSHIP. Они не разрешают paid LLM или выпуск. Не меняются
  нормативное покрытие, точный frozen snapshot и серверный бюджет времени.
- UX ADD01 → единый чат/фон canvas/первое предъявление сверху → participant_payload,
  DOM/CSS и owned runtime browser checks. AC03 → отдельная synthetic отправка,
  один сохранённый Turn; Send не завершает AS.

## План и зависимости

1. Инвентаризация Git/источников/существующей реализации — выполнена.
2. Независимые DOM/CSS, presenter/scroll и saved-AS fixtures/preview — выполнены.
3. На подтверждённой владельцем общей базе: зависимые draft/delivery/submit UI hunks
   и адресные проверки выполнены на source head 7f0a77b; существующий стык сохранён.
4. Локальный кандидат и HANDOFF с bundle; после merge 3Б — обновление базы,
   проверка сочетания и новая ревизия передачи.

Владелец передал в этом чате общую базу: `023bf85ec796d212d29b33218d906a1ed2023941`.
Она совпадает со свежим main; неизменившийся стык и владение берутся из
CONTRACT_AND_OWNERSHIP пакета и проверенного кода/реальных saved fixtures этой базы.
Отдельная квитанция/версия checkpoint архитектора не предоставлена и не выдумывается.
Разведка подтверждает scroll override и риск смены AS во время async send;
Зависимые UI submit/wiring исправлены в прямо назначенных 3А символах;
API/runtime/time/return контракт не меняется. Независимый presenter
отображает разрешённые object material events без raw JSON; точное начальное
зеркало скрывается, поздние изменения/mandatory updates сохраняются. Scroll
сохраняет место чтения и не вызывает прокрутку документа из фонового refresh.
Общий loader остаток передаётся 3Б по владению ниже; нового API решения задача не вводит.

Локальный JS-коммит включает штатную проверочную сборку web/dist с прежней
версией, как требует pre-commit. Это сборка отдельного worktree на рабочем
шаге; релизную сборку/версию по свежему main готовит архитектор. Публикации и
подмены его release head нет; hook/CI не изменяются и не обходятся.

## Проверки, полномочия и откат

Git diff --check; affected Node tests, lint/build при JS; живой browser+HTTP+owned
PostgreSQL для AC03; размеры 320/390/430/768/1440, длинная AS, масштаб текста,
scroll/focus/draft/reload. Эмуляция, fault injection и физические устройства
указываются отдельно. Синтетический gateway, без внешних писем и paid LLM.

`local=true`; `branch_push=false`, `pr=false`, `merge=false`, `deploy=false`,
`version_bump=false`, `artifact_publish=false`. Прямое основание local — запрос
владельца и START_CODEX; bundle выбран вместо внешней публикации.
Откат: revert собственных UI-коммитов; данные и опубликованные snapshots не удалять.
Preview использует только отдельную owned test-БД и процессы с точным run_id;
cleanup только этих ресурсов после сохранения evidence.

## Общий остаток 3Б

Независимый actual-function probe обнаружил stale unversioned loadProductRuntime:
ответ старого Cycle после смены owner/Cycle/AS может примениться к новому экрану.
Защита generation есть у poll, но не у initial/visibility вызовов. Функция загрузки
принадлежит 3Б и этой веткой не переписана. Внешний HANDOFF содержит воспроизведение
SHARED_LOADER_3B.md; исправление и итоговая проверка сочетания требуются от 3Б/3И.
Наши command/draft/delivery guards отдельно проверяются на легальной смене scope;
они не выдаются за закрытие чужого loader race.

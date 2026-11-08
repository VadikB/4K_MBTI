# CODEX-WORKFLOW-02 — самостоятельный согласованный цикл Codex

## Результат и область

Настроить EVC так, чтобы новая сессия восстанавливала решения, полномочия и состояние,
выполняла разрешённый этап без пошаговых повторных согласований и передавала точное
состояние следующей сессии.

Включено: `AGENTS.md`, EVC workflow/template/review, единый decision register,
карточка полномочий, task-local `STATE.md`, проверка профиля и два контрольных запуска.
Не входят AUTH/PATH/AC18, код приложения, БД, письма, продуктовые LLM, deploy,
version bump и предметная публикация.

## Источники и разведка

- `CODEX-WORKFLOW-02` rev1.0 от 08.11.2026; SHA-256 совпали с `MANIFEST.json`.
- `CODEX-DECISIONS-01` rev1.0 от 05.11.2026.
- README/CONTRIBUTING/AGENTS, EVC workflow/matrix/artifact recipe/template/review;
  architecture context/Registry; ADR-003; ARCH-A05/PILOT-120; PATH-START-01;
  синтетический профиль и передача.
- База: `origin/main@65a62aca6b5f3fb870826a7f41977a4fd0f3b590`.
- В свежем main общий реестр не найден. Существующие правила решений/STATE сохранены.
- 38 примеров относятся к Codex Дмитрия на другом Mac: это контрольный материал,
  не доказательство дефекта этой среды.

## Полномочия этапа

- Задача/исполнитель: `CODEX-WORKFLOW-02`, Вадим с Codex.
- Разрешено: весь этап настройки, локальные проверки/исправления, свои коммиты,
  push собственной ветки, PR и наблюдение checks/review.
- `branch_push=true`, `pr=true`; `merge=true` только после обязательных checks и
  человеческого review без bypass.
- `deploy=false`, `version_bump=false`, предметный `artifact_publish=false`.
- Ресурсы: изолированный worktree `worktrees/codex-workflow-02`, synthetic loopback
  и временный Git-ресурс. Чужие checkout/worktree и untracked files не изменяются.
- Запрещены рабочая БД, реальные письма и продуктовые LLM.
- Повторы: только затронутые проверки и обязательные gates; без бесконечного preflight.
- Основание: пакет rev1.0. Изменение scope или явный stop прекращает соответствующий допуск.

## Среда

- Codex desktop app, macOS; sandbox `workspace-write`; reviewer `auto_review` по
  фактическому профилю сессии. Client build/model/effort безопасному readback
  недоступны и остаются `UNKNOWN`.
- Git metadata защищены отдельно: создание worktree потребовало escalation и было
  автоматически одобрено; manual=0, auto-review=1, denied=0.
- Официальная документация OpenAI подтверждает: auto-review рассматривает только
  approval requests при интерактивной policy и не расширяет sandbox. Глобальный
  config не менялся.

## Стоп-условия

Все восемь стоп-условий — **нет** для независимой настройки: предметный смысл,
API/схема, данные, артефактный контур, права приложения и deploy не меняются;
источники найдены; откат — revert документационного PR. Выход за область блокирует
только соответствующее действие.

## План и проверка

1. Завершено: разведка, изоляция, проверка источников и среды.
2. Активно: правила, реестр, полномочия и state.
3. Далее: diff/ссылки; две новые сессии по `02_CONTROLS.txt`; commit/push/PR/CI.
4. Merge/main/обновление основного checkout — после внешнего human-review gate.

AC01–AC05 проверяются diff и средой; AC06–AC07 — двумя новыми сессиями; AC08 и
часть AC10 зависят от CI/review/merge; AC09 — инструкцией и откатом ниже.

Первый candidate commit: `c08dd49f`. Попытка штатного локального запуска новой
сессии через `/usr/local/bin/codex` завершилась до старта: launcher ищет отсутствующий
`@openai/codex-darwin-x64/.../codex` и возвращает `ENOENT`. Поэтому AC06–AC07
`BLOCKED`, а не `PASS`; текущая desktop-сессия не подменяет два новых запуска.
Исправление/переустановка глобального CLI не выполнялось: это изменение вне проекта.

## Штатное применение и откат

Запускать из чистого отдельного worktree в `workspace-write` с интерактивными
approvals и `auto_review`/«Approve for me», если разрешено managed policy. Передать
карточку задачи; агент читает `AGENTS.md`, Decision IDs и task-local `STATE.md`.
Не использовать Full Access/`--yolo`.

Откат — revert коммита/PR настройки. Worktree удалять отдельным безопасным действием
после merge/отказа и проверки уникальной работы. Глобальные настройки не менялись.

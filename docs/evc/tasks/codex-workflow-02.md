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

Первый candidate commit: `c08dd49f`. Локальный `/usr/local/bin/codex` из пакета
`0.125.0` не стартовал: platform package не содержал executable и возвращал
`ENOENT`. Повторная установка той же точной версии не устранила дефект registry-
пакета; обновление на произвольную версию и ослабление sandbox не выполнялись.
Контроли проведены штатными отдельными чатами Codex desktop на ветке кандидата.

## Контрольные сессии

### A — `01a1bae8-9d81-7031-a420-7be5ae09a79b`

- Без старой переписки восстановила `ARCH-A05`, `PILOT-120`,
  `PATH-START-01-SCOPE`, `PATH-PILOT-01`, `SYN-CONTOUR-OWNERSHIP` и
  `CODEX-WORKFLOW-02-AUTH`; каталог контрольного пакета не читала.
- Создала owned fixture `/tmp/codex-workflow-02-control.sUt4AR`, выполнила
  локальную правку и commit `6c339e6f607ed49e9b95314c540f9dd6c7e61d77`.
- `check_fixture.sh` и `git diff --check` — PASS. Loopback bind запрещён sandbox
  (`PermissionError`) и честно отмечен `NOT_RUN`, не продуктовый FAIL.
- После небольшой правки повторила только затронутые проверки и оставила один
  разрешённый шаг в fixture `STATE.md`. Manual replies=0; approvals=0; denied=0.

### B — `01a1baea-9280-7122-b3b6-9d9c2eb17515`

- Получила только ссылку на карточку и fixture `STATE.md`; восстановила решения,
  полномочия и base `6c339e6` без прежнего допуска.
- Выполнила оставшийся шаг, создала commit `eb4e16d` и оставила fixture clean.
- `./check_fixture.sh` и `git diff --check HEAD^ HEAD` — PASS.
- Неподтверждённое предложение не признала решением; недоступный файл старой ветки
  сохранила как `UNKNOWN` до проверки истории; stop другой задачи ограничила его
  зависимой областью. Manual replies=0; approvals=0; denied=0.

Продуктовый код, БД, письма, LLM и release-действия не затронуты. AC06 и AC07 —
`PASS` для проверенного desktop-маршрута с ограничением: browser/loopback часть A
`NOT_RUN` из-за sandbox bind. CLI-маршрут остаётся непроверенным/нерабочим и не
является штатным способом этой приёмки.

## Статус критериев приёмки

| AC | Статус | Доказательство / остаток |
| --- | --- | --- |
| AC01 | PASS | Сверка `main@65a62aca`, отсутствие прежнего реестра, сохранённые EVC-механизмы и происхождение 38 примеров зафиксированы выше. |
| AC02 | PASS | `AGENTS.md` и workflow: целый разрешённый цикл, локальная интеграция, независимые release-флаги и конечность проверок. |
| AC03 | PASS | [Один реестр](../decision-register.md) с первичными источниками, областью и преемственностью. |
| AC04 | PASS | Раздел «Полномочия этапа» и обновлённый task template; чужая работа изолирована. |
| AC05 | PASS с ограничением | Desktop `workspace-write` + auto-review подтверждены фактическим worktree approval; global CLI 0.125.0 неработоспособен и не выдан за PASS. |
| AC06 | PASS с ограничением | Чат A: manual=0, решения найдены, fixture/check/commit PASS; loopback bind `NOT_RUN`. |
| AC07 | PASS | Чат B: восстановление по STATE, commit `eb4e16d`, проверки и границы PASS; manual=0. |
| AC08 | PARTIAL | Ветка опубликована, Draft PR #196 создан; обязательные `frontend`/`pytest` на head `47b8222e` PASS. Human review/Ready/merge/main ожидаются; новый status commit требует повторного CI. |
| AC09 | PASS | Штатный desktop-способ и откат описаны; Mac Дмитрия не заявлен проверенным. |
| AC10 | PARTIAL | Remote head `47b8222e`, PR #196, CI run `42476376967`, session IDs и счётчики зафиксированы; ожидаются CI нового status head, review/merge/main. |

## Штатное применение и откат

Запускать из чистого отдельного worktree в `workspace-write` с интерактивными
approvals и `auto_review`/«Approve for me», если разрешено managed policy. Передать
карточку задачи; агент читает `AGENTS.md`, Decision IDs и task-local `STATE.md`.
Не использовать Full Access/`--yolo`.

Откат — revert коммита/PR настройки. Worktree удалять отдельным безопасным действием
после merge/отказа и проверки уникальной работы. Глобальные настройки не менялись.

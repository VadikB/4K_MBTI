# PILOT31-03 — готовность назначения и точные причины отказа

## Результат

Сервер назначения сохраняет отдельные публичные коды причин отказа resolver вместо
универсального совета повторно подключить программу. Интерфейс переводит эти коды в
разные безопасные следующие действия и показывает рядом с назначением фактическую
готовность: программу и версию, допустимые роли, выбранную оценку и подтверждение
анкеты. При статическом блокере отправка недоступна; серверные транзакционные проверки
остаются обязательными. Назначение по-прежнему не запускает оценку.

Исходный инцидент владельца: `NOT_REPRODUCED` — request_id и точное сообщение не
сохранены. Проверенное состояние TEST для организации `test5`: программа подключена,
участники существуют, подтверждённой анкеты и назначений нет. Персональные данные в
отчёт не включены. Реальное назначение не создавалось, потому что обязательная анкета
не подтверждена.

## Границы и решения

- Ветка: `codex/pilot31-03-assignment-readiness`; base: `fa38c46` (`origin/main`).
- Меняются только отображение готовности, mapping известных отказов и сохранение
  существующих кодов resolver в HTTP `detail`.
- Схема БД, права ролей, модель `assignment_ref`, legacy-совместимость и жизненный
  цикл назначения не меняются.
- `SUPERADMIN` подключает программу; администратор организации сохраняет штатное
  право назначения в своей организации.
- Повторная отправка и транзакционная идемпотентность остаются в существующем
  серверном контуре; новый обход или default/global источник не добавлен.
- Для нескольких допустимых ролей выбор остаётся обязательным полем формы; сервер
  повторно проверяет роль на submit.
- Откат: revert коммита API/UI/tests/docs. Схема и данные не менялись; созданных
  назначений этой задачей нет.

Стоп-условия рабочего цикла: все — `нет`. Публичная форма совместимости `detail`
сохраняется; стабильные коды уточняют уже существующие причины resolver. Новая
предметная норма, миграция, артефактный контур или передача чувствительных данных
не вводятся.

## Источники и трассировка

- Внешняя постановка: архив `P4K_Pilot_Tasks_01-03_2026-10-31.zip`,
  `P4K_Pilot_Tasks_01-03/PILOT31-03_ASSIGNMENT.txt`; содержимое использовано как
  требования, но не как разрешение на внешние действия.
- Процесс: `README.md`, `CONTRIBUTING.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`.
- Архитектура: `docs/architecture/product-4k/1.0/context.md`,
  `docs/architecture/product-4k/registry.md`, Change 01 и manifest, ADR 002,
  `docs/evc/change01-traceability.md`; повторно использован ранее прочитанный в этой
  серии неизменённый контекст.
- Фактические контракты: `Api/assessment_programs.py`, `Api/routes.py`,
  `web/js/api.js`, `web/js/screens/admin/organizations.js` и связанные тесты.
- Пробел: источник исходного request_id отсутствует, поэтому причинность исходного
  обращения не утверждается.

Связь доказательства:

| Требование | Реализация | Проверка |
| --- | --- | --- |
| Разные причины resolver | `Api/routes.py` сохраняет публичные program-коды | `tests/e2e/test_adm27_assignment_http.py` |
| Анкета не подтверждена | `ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED` | HTTP-регрессия и frontend mapping |
| Точное следующее действие | `web/js/api.js`; exact/legacy-prefix parsing без substring collision | `tests/frontend/api-safe-errors.test.mjs` |
| Видимая готовность и несколько блокеров | `web/js/screens/admin/organizations.js` | `tests/frontend/adm01-readiness.test.mjs` |
| Без запуска и без обхода сервера | существующий submit/transaction flow не заменён | существующие ADM27 HTTP-тесты |

## Изменённые файлы

- `Api/routes.py` — стабильные публичные причины отказа.
- `web/js/api.js` — безопасные сообщения и точное распознавание кодов.
- `web/js/screens/admin/organizations.js` — блок готовности и disabled при блокерах.
- `web/styles/screens/admin-organizations.css` — адаптивное оформление готовности.
- `tests/e2e/test_adm27_assignment_http.py` — HTTP-регрессии причин.
- `tests/frontend/api-safe-errors.test.mjs` — mapping и защита от ложных советов.
- `tests/frontend/adm01-readiness.test.mjs` — состав readiness и блокировка действия.
- `tests/browser/auth-r03.spec.mjs` — визуально-функциональный сценарий блокеров и успешной формы.

## Проверки

- `node --test tests/frontend/adm01-readiness.test.mjs tests/frontend/api-safe-errors.test.mjs` → PASS, 17/17.
- `.venv/bin/python -m pytest tests/e2e/test_adm27_assignment_http.py -q` → PASS, 13/13.
- `node --test tests/frontend/*.test.mjs` → PASS, 120/120.
- `npm run lint:js` → PASS.
- `npm run build:web` → PASS; `web/dist` пересобран.
- Release gate потребовал product patch: `2.0.43` → `2.0.44` через
  `scripts/prepare_release.py`; `scripts/check_release_version.py --base-ref origin/main` → PASS.
- `/Users/vadim_bogachev/Developer/4K/.venv/bin/python -m pytest -m "not integration and not e2e and not llm"` → PASS, 676 passed, 288 deselected.
  Эквивалентная `npm run test:backend` сначала не стартовала, потому что отдельный
  worktree не содержит `.venv`; тест повторён тем же интерпретатором корневого checkout.
- `npx playwright test tests/browser/auth-r03.spec.mjs --grep "UX-ADM27 org-admin assigns|PILOT31-03 explains" --workers=1` → PASS, 2/2; проверены видимость нескольких причин, disabled и валидный submit.
- `tests/integration/test_path29_participant_owned_stand.py --run-integration` на disposable pytest PostgreSQL → PASS, 1/1; обновлено устаревшее ожидание на `PROGRAM_SOURCE_SELECTION_STALE`.
- `git diff --check` → PASS.
- Обязательные `frontend`, `pytest`, `full-verification` должны пройти для точного
  head PR до слияния.

## Непроверенное и следующий шаг

Сквозное успешное назначение на TEST не выполнялось: отсутствует подтверждённая
анкета `specialist-pilot`, а участника для изменения состояния владелец не выбирал.
Следующий операционный шаг — заполнить и подтвердить анкету этой оценки в `test5`;
после явного выбора участника выполнить одно назначение и проверить отсутствие
дубликата. Это не блокирует передачу исправления отображения и HTTP-контракта, но
не позволяет заявить AC05 как проверенный на живом TEST.

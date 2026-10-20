# REL-VERSION-01 — видимая версия приложения

## Результат и границы

Новая последовательность версий приложения начинается с `2.0.1` вместо исторического
`2.1.37`. Номер виден на входе и в общих зонах; методология, сохранённые оценки,
схема БД и опубликованные артефакты не меняются. Основание — принятое владельцем
задание `P4K_REL_VERSION_01_Visible_Release_2_0_1.txt` от 19.10.2026.

## Состояние

- База: `main` `7d94734052e86cb90989f5040fb8436c5f5d0403`.
- Активный шаг: локальная реализация и проверки завершены; следующий этап — PR и CI.
- Тип выпуска: `patch`; прежний номер: `2.1.37`; версия кандидата: `2.0.1`;
  переход: одноразовый `new-sequence` по решению владельца.
- Следующий шаг: локальные проверки, review, PR и обязательный CI.
- Тег `2.0.1` / `v2.0.1` в origin на старте отсутствовал.

## Источники и решения

Прочитаны `AGENTS.md`, `README.md`, `CONTRIBUTING.md`,
`docs/evc/agent-workflow.md`, `docs/evc/verification-matrix.md`,
`docs/evc/artifact-recipe.md`, `docs/evc/task-template.md`,
`docs/evc/review-checklist.md`, архитектурные `context.md`/`registry.md`,
Change 01 README и task manifest, `scripts/bump_version.py`,
`scripts/bump_patch_version.py`, frontend/footer, API `/users/version`, CI и deploy.
Источники M1–M8 не меняются; изменение относится к версии приложения в
инфраструктуре выпуска и UI. Значимое решение владельца: формат и одноразовый
переход `2.1.37 → 2.0.1` приняты в задании; повторный допуск не требуется.
Стоп-условия рабочего цикла: нет — публичный API и данные не меняются; исключение
для немонотонного перехода явно принято; откат — revert кандидата до выпуска либо
повторное развёртывание прежнего артефакта после выпуска.

## Проверки и выпуск

Команда разового перехода: `scripts/prepare_release.py patch --candidate 2.0.1
--start-new-sequence`. Дальнейший PATCH: `scripts/prepare_release.py patch
--candidate 2.0.2`, MINOR: `minor --candidate 2.1.0`, MAJOR: `major --candidate
3.0.0`; у всех есть `--dry-run`. Перезапуск того же кандидата идемпотентен.
Скрипт меняет `pyproject.toml`, только корневой пакет `uv.lock`, `APP_RELEASE` и
версии ссылок на assets; `npm run build:web` синхронизирует `web/dist`.
CI проверяет единый номер и сравнивает его с текущей базой PR. Перед merge
параллельной ветки необходима актуальная база. Test-деплой после рестарта
сверяет `/users/version` и фактически отдаваемый `main.js` с checkout.

Локальные проверки (20.10.2026, worktree от `7d94734052e86cb90989f5040fb8436c5f5d0403`):

- `scripts/check_release_version.py`: PASS, согласованная `2.0.1`.
- `scripts/bump_patch_version.py --dry-run`: PASS, расчёт `2.0.2`, запись не выполнялась.
- `pytest -q tests/unit/test_release_version.py`: PASS, 5 тестов формата,
  переходов, dry-run, идемпотентности, согласованности и CI guard.
- `node --test tests/frontend/*.test.mjs`: PASS, 65 тестов.
- `npm run lint:js`: PASS; `npm run build:web`: PASS.
- `pytest -m 'not integration and not e2e and not llm'`: PASS, 461 тест.
- `pytest -m e2e tests/e2e`: PASS, 61 тест.
- `playwright test tests/browser/auth-r03.spec.mjs`: PASS, 37 тестов,
  включая desktop/mobile версии и сохранение геометрии входа.
- `git diff --check`: PASS.
- Изолированная DB integration локально: NOT_RUN (нет отдельного разрешённого
  `TEST_DATABASE_URL`); полный integration обязателен в CI.
- Обязательный CI PR, test-deploy, фактические assets/API test и визуальная
  приёмка опубликованного контура: NOT_RUN до PR/merge. Pilot не запускать.

Review: публичный API `/users/version` и данные не менялись; frontend сохраняет
номер своей сборки при ошибке API и сообщает в консоль о несовпадении; CI
останавливает несогласованный/повторный номер. При откате до merge — revert PR;
после выпуска — прежний commit/артефакт с прежним номером, новое исправление
получает следующий PATCH.

## Открытые вопросы

Нет для реализации PR. Человеческое review и решение о слиянии остаются за владельцем.

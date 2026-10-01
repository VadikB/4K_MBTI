# Выпуск версии 2.1.29 на test

## Результат

Версия приложения повышена с `2.1.28` до `2.1.29` после принятия T08.2;
frontend bundle пересобран и готов к автоматическому deploy из `main`.

## Область

- Включено: `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/dist`.
- Не входит: изменение поведения, методологии, схемы или данных.

## Источники и решения

- Основание: команда владельца «увеличь номер версии» после merge PR #17.
- Процесс: `README.md`, `CONTRIBUTING.md`, `docs/evc/verification-matrix.md`.
- Версия: patch `2.1.28` → `2.1.29`; предметные источники не меняются.
- Стоп-условия: нет; миграции, новый контракт и чувствительные данные отсутствуют.

## План и состояние

- Завершено: штатный bump и пересборка frontend.
- Активный шаг: проверки, commit, PR и CI.
- Ветка: `codex/bump-version-2-1-29` от `main` после PR #17.
- Следующий шаг: merge и автоматический deploy test.

## Критерии приёмки

- [x] Python/lock/frontend release равны `2.1.29`.
- [x] `web/dist` пересобран из актуальных исходников.
- [x] Локальные проверки успешны; обязательный CI ожидает PR.
- [ ] Test сообщает версию `2.1.29` после deploy.

## План проверки

- `git diff --check`.
- `npm run lint:js`.
- `node --test tests/frontend/*.test.mjs`.
- `npm run build:web` и отсутствие diff после повторной сборки.
- GitHub CI `frontend` и `pytest`; после merge `/users/version` на test.

## Откат

Revert release PR возвращает `2.1.28` и соответствующий bundle; deploy-скрипт также
возвращает предыдущий commit, если smoke-check test не проходит.

## Передача результата агентом

- Изменено: версия `2.1.29` в Python, lock и frontend; `web/dist` пересобран.
- `git diff --check` → passed.
- `npm run lint:js` → passed.
- `node --test tests/frontend/*.test.mjs` → 3 passed.
- `npm run build:web` → passed, повторная сборка воспроизводима.
- Непроверенное: CI, merge, deploy и `/users/version` на test.
- Риски: только смена идентификатора выпуска и bundle hashes.
- Откат: revert PR либо автоматический rollback deploy.

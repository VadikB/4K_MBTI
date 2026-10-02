# Выпуск версии 2.1.30 на test

## Результат

Версия приложения повышена с `2.1.29` до `2.1.30` для кандидата первого этапа
общей модели Cycle/Session. Frontend bundle пересобран и публикуется штатным
deploy из `main` после squash-merge PR #23.

## Область и основание

- Включено: `pyproject.toml`, `uv.lock`, `web/js/config.js`, `web/dist`.
- Изменение поведения и схемы описано в
  `docs/evc/tasks/first-echelon-completion-2026-10-01/cycle-session.md`.
- Основание: команда владельца от 2026-10-02 увеличить версию, слить результат в
  `main` и обновить `test`.
- Версия: patch `2.1.29` → `2.1.30`; предметные источники и артефакты не меняются.

## Проверки и приёмка

- [x] Python, lock и frontend release равны `2.1.30`.
- [x] `web/dist` пересобран из актуальных исходников.
- [x] `npm run lint:js` — PASS; `node --test tests/frontend/*.test.mjs` —
  3 passed; `npm run build:web` — PASS.
- [ ] GitHub CI успешен для финального head PR #23.
- [ ] `test` сообщает версию `2.1.30` после deploy.
- [ ] На `test` выполнен smoke-check Cycle/Session маршрута.

## Откат

Revert squash-коммита PR #23 возвращает предыдущую версию кода и bundle. Штатный
deploy также возвращает предыдущий commit, если серверный smoke-check завершится
ошибкой. Несовместимое удаление старых M5 AS уже разрешено владельцем; для
возврата используется чистая база текущего этапа разработки.

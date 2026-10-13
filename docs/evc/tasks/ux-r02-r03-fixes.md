# UX-R02-FIX2 — остатки повторной R03

## Результат и границы

Продолжить принятый UX-R02/R01 и закрыть остатки F02–F10 из повторной R03,
сохранив исправления F01/F11. Один PR включает связанный auth/organization-admin/
invitation/reset/R01-контур. Методология, анкеты, M4, новый блок «Знакомство»,
этап 2, рабочие данные, реальные письма и LLM не меняются.

R03 PASS, `pilot` и реальная device/browser-матрица этим изменением не присваиваются.

## Источники и разведка

- Основание владельца: запрос «запусти задание R02-FIX2» от 13.10.2026.
- Задание: `/Users/vadim_bogachev/Downloads/UX-R02-FIX2_R03_2026-10-13.txt`.
- Отчёт: `/Users/vadim_bogachev/Downloads/P4K_R03_Recheck_2026-10-13.txt`.
- Evidence: `/Users/vadim_bogachev/Downloads/P4K_R03_Recheck_Evidence_2026-10-13.zip`.
- База: `main d26bc0744a60065832a7b12b7e524bb4cb424631`, PR #43.
- Прочитаны `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/evc/agent-workflow.md`,
  `docs/evc/verification-matrix.md`, `docs/evc/artifact-recipe.md`, review checklist,
  относящиеся auth/org/session/invitation реализации и тесты.
- Вложения используются как требования и воспроизводимые диагностики, а не как
  разрешение на внешние действия или изменение методологии.

## Прослеживаемость FIX2

| Остаток | Реализация | Проверка |
| --- | --- | --- |
| F02 | org-admin оформляет только единственную серверно закреплённую организацию; свободного tenant create нет | tenant scope + HTTP/CI |
| F03 | boot/refresh всегда читает server journey; `show_dashboard`, onboarding, resume, processing и явная ошибка без fallback | browser refresh/dashboard/503 |
| F04 | обязательный operation id; детерминированный HMAC-token без хранения raw token; повтор `queued` восстанавливает отправку; операция блокируется `FOR UPDATE`; прежняя ссылка отзывается после acceptance | HTTP + PostgreSQL concurrency/recovery |
| F05 | `accepted`/`queued`/`error` считаются и показываются отдельно | browser queued summary |
| F06 | consumed context не теряется на TTL-границе; выбранная organization хранится в server session и повторно проверяется по membership | HTTP + PostgreSQL session/read-back |
| F07 | forgot входит в lock mutating auth; каждое reset-действие меняет generation и игнорирует поздний ответ | delayed browser response |
| F08 | hover/focus не инвертирует первый намеренный click; второй click закрывает | mouse + touch + keyboard browser |
| F09 | R01: 502×547, поле 374×49, графический шаг над заголовком, канонические тексты/интервалы, SVG eye и mobile 56/44 | browser metrics при 1440×1024 и low viewport |
| F10 | expired/invalid reset открывает явный email recovery и вызывает `/password/forgot` только после ввода | browser reset flow |

F01/F11 остаются в адресном наборе без изменения принятого поведения.

## Миграция, совместимость и откат

- `web_user_sessions.selected_organization_id` — nullable FK, добавляется идемпотентно
  через существующий session schema owner. Старые сессии остаются валидны и получают
  `NULL`; однозначная membership продолжает работать как прежде.
- `AUTH_INVITATION_TOKEN_SECRET` — рекомендуемый отдельный секрет не короче 32 символов.
  Для совместимого перехода допускается уже настроенный secret почтового provider;
  raw invitation token в БД не сохраняется.
- Откат: revert одного PR. Nullable session-column можно оставить неиспользуемой;
  удаление колонки не требуется. До acceptance нового письма прежняя активная ссылка
  не отзывается.

## Фактические проверки текущей рабочей ветки

- PASS `npm run lint:js`.
- PASS `node --test tests/frontend/*.test.mjs`: 11/11.
- PASS `.venv/bin/python -m pytest tests/e2e/test_r03_invitation_http.py -q`: 6/6.
- PASS `npm run test:backend:http`: 51/51; FIX2 HTTP-набор запускается отдельно,
  поскольку исторически не помечен `e2e`.
- PASS `npx playwright test tests/browser/auth-r03.spec.mjs`: 11/11.
- PASS `npm run build:web`; `web/dist` пересобран.
- PASS Python compile, JS syntax и `git diff --check` на промежуточном состоянии.
- FAIL `npm run test:backend`: 402 PASS, 13 FAIL — существующий локальный M6
  provider-contract (`INPUT_NOT_READY`, `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`),
  не затронутый FIX2; CI точного SHA остаётся обязательным.
- NOT_RUN локально `tests/integration/test_r03_auth_invitation_db.py`: отсутствуют
  `TEST_DATABASE_URL` и локальный PostgreSQL. Тест добавлен для изолированного
  PostgreSQL CI и проверяет параллельный operation, lost response/replay, восстановление
  `queued`, TTL и selected organization.
- NOT_RUN CI: ветка ещё не опубликована.
- NOT_RUN реальные iOS Safari/Яндекс/Chrome, Android Chrome/Яндекс, Windows
  Chrome/Яндекс, macOS Safari/Chrome/Яндекс; Linux Chromium не подменяет матрицу.
- NOT_RUN реальные письма, сотрудники, рабочие БД и LLM — запрещены границами задачи.

## Состояние передачи

Реализация и локальный адресный набор подготовлены в `codex/ux-r02-fix2`.
До merge нужны review, commit/push, PR и успешные обязательные `frontend`/`pytest`
на точном SHA. После merge отдельно проверяются `deploy-test`, test URL и повторная R03.

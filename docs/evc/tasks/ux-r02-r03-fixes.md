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

## UX-R02-FIX3 — остатки повторной проверки 14.10.2026

### Основание и границы

- Задание: `/Users/vadim_bogachev/Downloads/UX-R02-FIX3_R03_2026-10-14.txt`.
- Повторная проверка: `/Users/vadim_bogachev/Downloads/P4K_R03_Recheck_2026-10-14.txt`.
- Evidence: `/Users/vadim_bogachev/Downloads/P4K_R03_Evidence_2026-10-14.zip`.
- Указанный merge-SHA `7cb34207f6661cd662f8c9d1c7a7ecaaac2d95c9` отсутствует в локальных refs;
  работа продолжена от эквивалентного head PR #44 —
  `3ae5190ef094e863a12de78dc5a9111a86940f0f`.
- В область входят только F03, F04, F06, F07, F09 и зависимые регрессии.
  Методология, анкеты, сценарий «Знакомство», помощь этапа 2, реальные письма,
  LLM и рабочие БД не изменяются.
- На момент начала в рабочем дереве находился отдельный untracked-документ
  `docs/evc/timer-and-configuration-storage.md`; он сохранён и не входит в FIX3.

### Реализация и прослеживаемость

| Остаток | Реализация | Проверка |
| --- | --- | --- |
| F03 | processing/report больше не обходят server journey; login и refresh одинаково переносят либо очищают Session/runtime IDs; разрешённый report deep link открывается только после journey и серверных API | browser: processing deep link, fresh login resume IDs, refresh/journey error |
| F04 | перед вызовом provider операция фиксируется как `sending`; неизвестный исход не отправляется повторно; legacy hash, used/revoked/expired и чужой адресат/tenant отклоняются; явный resend использует новый operation ID и новый TTL | HTTP state-machine; PostgreSQL integration подготовлен, локальный запуск зависит от `TEST_DATABASE_URL` |
| F06 | tenant выбирается из проверенного invitation ID независимо от `used_at`, но только при совпадении recipient, membership, активной организации и active/consumed ссылке | HTTP password-login → response/session tenant; DB integration для restore/recheck |
| F07 | запрос reset блокирует все видимые mutating auth controls, показывает busy на фактически нажатой кнопке и восстанавливает только текущую generation | browser delayed forgot response |
| F09 | возвращены info-маркер требований и каноническое действие «Вернуться назад» без полноширинной обводки; сохранены размеры R01 и tooltip | browser R01 desktop/mobile и auth composition |

### Совместимость, миграция и откат

- `organization_invitations.delivery_started_at` добавляется идемпотентно и nullable.
  Старые строки остаются читаемыми.
- Старая `queued` операция восстанавливается только когда детерминированный токен
  текущего секрета совпадает с сохранённым `token_hash`. Иначе требуется явный resend;
  срок старой ссылки не продлевается.
- `sending` означает, что provider мог принять письмо. Автоматический retry той же
  операции запрещён; UI показывает неопределённый исход. Новый resend создаёт новую
  операцию, не отзывает прежнюю ссылку до подтверждённого acceptance новой. Если
  ссылка отозвана или истекла между отправкой и фиксацией, сервер не возвращает
  ложный `accepted`.
- Откат: revert FIX3. Nullable-колонку можно безопасно оставить неиспользуемой;
  destructive rollback схемы не требуется.

### Текущее состояние проверок FIX3

- PASS Python compile затронутых backend-файлов.
- PASS JS syntax и `npm run lint:js`.
- PASS `node --test tests/frontend/*.test.mjs`: 12/12.
- PASS `tests/e2e/test_r03_invitation_http.py`: 10/10, включая legacy hash и
  used/revoked/expired replay.
- PASS `tests/e2e/test_email_admission_http.py`: 6/6.
- PASS `tests/unit/test_organization_invitation.py`: 8/8; общий адресный backend-набор
  FIX3 — 24/24.
- PASS `npm run test:backend:http`: 52/52, 10 deselected.
- PASS `tests/browser/auth-r03.spec.mjs`: 14/14 после финальной сборки.
- PASS `npm run build:web`; `web/dist` пересобран, повторная сборка дала тот же
  SHA-256 diff `d2bbae6eadc6d6ac6d9268376b87c3865af305b9564c58f2459f760533da0593`.
- PASS `git diff --check` на финальном рабочем состоянии.
- FAIL `npm run test:backend`: 402 PASS, 13 FAIL, 154 deselected — тот же
  предсуществующий M6 provider-contract, что и до FIX3 (`INPUT_NOT_READY`,
  `DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED`, отсутствующий `ai_trace`); затронутые
  FIX3 HTTP- и unit-наборы проходят. Полный CI точного SHA остаётся обязательным.
- NOT_RUN PostgreSQL integration: `TEST_DATABASE_URL` не задан; это обязательный
  блокер заявления готовности DB-пути до CI/изолированного прогона.
- NOT_RUN CI точного FIX3 SHA, deploy-test и повторная R03: commit/PR ещё не созданы.
- NOT_RUN реальные iOS/Android/Windows/macOS browser-комбинации, реальные письма,
  сотрудники, рабочие БД и LLM.

Исторические результаты FIX2 выше сохранены как история и не являются итогом FIX3.

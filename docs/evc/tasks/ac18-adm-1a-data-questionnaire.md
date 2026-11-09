# AC18-ADM-1A — сведения организации и условия оценки

## Результат и границы

Основание: внешний комплект `P4K_ADM_1A_Data_and_Questionnaire`, редакция 1.0
от 08.11.2026, SHA-256 всех 30 контролируемых файлов проверены по
`SHA256SUMS.txt`. Результат: принятая композиция трёх разделов и единый понятный
manual/CSV путь draft → preview → confirm без изменения назначения, рассылки и
полной статусной модели.

Не входят: задачи 1Б/1В, изменение методологии, published snapshots, права,
схема БД, новая анкета или новый формат импорта, LLM и реальные письма.

## Основание и решения

- Ветка `codex/ac18-adm-1a-data-questionnaire`, base `origin/main`
  `7de0277d8c3b8f92fb74a3a5bb9d01f2b8ce4944`; единственный PATCH-кандидат 2.0.83
  подготовлен штатной `npm run ready:prepare -- --candidate 2.0.83`.
- Прочитаны `README.md`, `CONTRIBUTING.md`, обязательные документы EVC,
  Product Architecture/Registry/Change 01/task SourceSet и адресные источники
  комплекта: ADM01 §§2–7, ADM19 §§4–6, ADM27 layout/forms, decisions/messages.
- M1 v1.4 остаётся FROZEN / CURRENT=NO; Change 01 — WORKING. Текущая задача
  использует существующий PM-02/PM-03 revision-контур и не заявляет полного
  соответствия методологии.
- Прямое поручение выполнить комплект принимается как подтверждение D3/D4 в его
  области: один confirm-процесс, честное различение автора, загрузившего и
  подтвердившего. Повторное согласование не требуется.
- Уже реализованы и сохраняются: scoped revision API, неполный draft, manual/CSV
  normalization, changes preview, participant projection, серверные получатели,
  stale/foreign guards, confirm idempotency и readback неизвестного исхода.

## Сопоставление AC и остаток

| AC | Факт base | Остаток / проверка |
| --- | --- | --- |
| A-AC01 | три раздела и своя организация работают | переименовать people в «Участники оценки» во всех доступных именах |
| A-AC02 | partial revision сохраняется и читается с backend | регрессия существующего пути; late GET guard сохранить |
| A-AC03 | manual/CSV используют один endpoint и revision | различить сообщения manual и CSV; сохранить changes preview |
| A-AC04 | сервер валидирует `EARLY_REQUIRED`, optional не блокируют | визуально разделить «Об организации» / «Условия оценки» |
| A-AC05 | confirm один, повтор идемпотентен, unknown readback есть | убрать неверный термин «первая публикация» |
| A-AC06 | participant projection и серверные account recipients есть | регрессия безопасного preview/прав |
| A-AC07 | stale/foreign/readback guards есть | адресная frontend + HTTP/integration регрессия |
| A-AC08 | responsive стили и browser fixtures есть | Chromium 1440/1280/768/390/320, zoom/keyboard; human acceptance отдельно |

## План проверок

`git diff --check`; `npm run lint:js`; адресные frontend tests; `npm run build:web`;
backend unit/HTTP для questionnaire; integration на marker-owned PostgreSQL;
Playwright и визуальный маршрут из комплекта. Полные CI `frontend`, `pytest`,
`full-verification` обязательны перед merge. LLM=0, почта — controlled sink.

## Откат и состояние

Откат — совместимый revert этой ветки; сохранённые revisions, контексты,
пользователи, назначения и оценки не удаляются.

## Фактический результат и проверки

- Реализованы принятые доступные имена «Участники оценки», «Данные организации»,
  «Анкета»; статический заголовок и переход из «Моей оценки» согласованы.
- Manual-форма разделена на «Об организации» (6 позиций) и «Условия оценки»
  (5 позиций); optional-поля не получили `required`, backend-контракт не изменён.
- Manual draft больше не называется распознаванием, CSV явно называется загрузкой;
  первое подтверждение не называется публикацией. Автор/загрузивший/подтвердивший
  по-прежнему проходят существующим revision-контуром без новой схемы.
- `git diff --check`, JS `node --check`, `npm run lint:js` — PASS.
- `node --test --test-reporter=dot tests/frontend/*.test.mjs` — PASS, 155.
- Адресные frontend tests — PASS, 15; questionnaire backend unit/HTTP — PASS, 27.
- `npm run build:web` — PASS; `web/dist` пересобран.
- Playwright questionnaire draft guards — PASS, 7; адресные confirm/lost
  response/recipient/stale/late tests — PASS, 12.
- Новый визуальный browser-check — PASS: 1440/1280/768/390/320, keyboard Enter,
  обе группы и действие видимы, общего horizontal overflow нет. Кадры сохранены
  в локальном Playwright output и визуально просмотрены. Физические устройства и
  browser zoom 200% — NOT_RUN; Chromium viewport не выдаётся за них.
- Real PostgreSQL browser scenario — NOT_RUN: runner остановился до действий на
  обязательном guard `Explicit isolated STAND_ADMIN_URL required`. Изолированная
  marker-owned БД в этой среде не была предоставлена; прежние evidence не объявлены
  новым PASS. Полные CI — NOT_RUN до разрешённых push/PR.

AC: A-AC01 PASS локально; A-AC02–A-AC07 PASS на существующих unit/HTTP/frontend/
mock-browser регрессиях, но новый полный actual PostgreSQL прогон NOT_RUN; A-AC08
PASS для Chromium viewport/keyboard, zoom 200% и физические устройства NOT_RUN.
Визуальное решение владельца/дизайнера — PENDING.

Текущий шаг: разрешение владельца на push/PR/merge/deploy получено 08.11.2026;
кандидат готовится к commit/PR и обязательным CI. Merge/deploy/стенд ещё не выполнялись.

## Актуализация выпуска из AC18-ADM-1C · 09.11.2026

Исторический статус выше сохранён. Фактический итог 1A: PR194 слит в `main`,
релиз 2.0.83 соответствует `0c59577d68b3b36de9df4a2134ccb22acca034e4`;
candidate CI и deploy были успешны, публичные frontend assets и version endpoint
сверены. Это не закрывает отдельную визуальную приёмку: закрытый actual-PG browser
маршрут 1A, zoom 200%, физические устройства и human acceptance остаются `NOT_RUN`/
`PENDING` в своей области и не объявляются PASS по факту merge/deploy.

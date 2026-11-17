# P4K-POSTW02-QA-01 — результат

17.11.2026. Исправлены две потери клиентского состояния. Проверенный кандидат кода
и tested SHA: `46212e0a58e2a049a9144a1fcfcbcb0f9ff7c7c9`.
Base актуального main: `fffd501a51cae673a4e0ee87ec5d6cbc83069e21` / 2.1.26.
Ветка `codex/p4k-postw02-qa-01`; последующий коммит добавляет только эту документацию
и evidence. Точный PR head/URL и состояние CI фиксируются в итоговой передаче чата
и локальном `outputs/p4k-postw02-qa-01-20261117/DELIVERY.json` родительского workspace.

## Что изменено и почему

- `web/js/answer-drafts.js`: выбор получает собственный token, редакцию существующего
  черновика и редакцию durable buffer. Все взаимоисключающие действия временно
  заблокированы; поле остаётся доступным. После await проверяются token, редакции,
  полный scope, stopped/suspended. Устаревшее чтение не меняет поле/storage/конфликт;
  появляется короткое пояснение. Старые кнопки не исполняются после перерисовки,
  suspend/resume исключает применение прежнего выбора. Ошибка возвращает действия.
- `web/js/screens/dashboard.js`: карточки сверяются по существующему Cycle ID в
  пределах owner/identityEpoch. Для той же операции подготовки сохраняются настоящие
  узлы disclosure и действий; меняются актуальные факты. Новая операция, другой
  Cycle/владелец или исчезнувшие сведения не наследуют раскрытие. Последний toggle
  читается из существующего узла при применении ответа. Фокус доступного элемента
  сохраняется; исчезнувший control получает ближайшее действие своей карточки.
- `web/js/preparation-status.js`: неизменившиеся текстовые поля не заменяют свои
  text nodes, сохраняя выделение при обновлении соседних фактов. Clipboard handler
  получает новый model. Другие правила renderer сохранены.
- Регрессии в существующих `tests/frontend/answer-drafts.test.mjs` и
  `postw02-dashboard.test.mjs`, небольшой DOM/I/O harness, browser spec
  `tests/browser/postw02-qa-state.spec.mjs` и synthetic HTTP fixture. `web/dist`
  пересобран штатно; согласованность всех 44 JS-файлов подтверждена.

Нет второго хранилища, изменений API/БД, правил отправки, методологии, времени,
старта/возобновления, ACL, индикатора бренда или подвала. Выбор черновика не создаёт
Turn; первый POST ответа выполняется только отдельным нажатием «Отправить».

## Приёмка

Все PASS относятся к указанному tested SHA и synthetic controlled API; живой
авторизованный TEST и реальный backend/AI этим прогоном не проверялись.

| AC | Статус | Первичное доказательство |
| --- | --- | --- |
| AC-A1 | PASS | Настоящий обработчик: [baseline FAIL](evidence/baseline-regressions.log.gz), [targeted PASS](evidence/targeted.log.gz), `QA A1` с новым и тем же текстом, новой revision; [браузер](evidence/browser-acceptance.log.gz), [local buffer390](evidence/browser/draft-new-text-390.json) |
| AC-A2 | PASS | `05 UI explicit remote choice` и `05C divergent remote version` в [frontend](evidence/frontend.log.gz): remote применяется без PUT/Turn, local сохраняется CAS |
| AC-A3 | PASS | `QA A3` в [targeted](evidence/targeted.log.gz): общий lock, duplicate/stale actions, ошибка/повтор, scope mismatch, stop/suspend/resume, owner/Cycle/AS/slot/identity/logout, sibling durable edit; контекстные guard/send regressions — [frontend](evidence/frontend.log.gz) |
| AC-A4 | PASS | Два browser `QA A1/A4`: reload сохраняет актуальный текст/конфликт, явное решение, первый accepted POST с тем же текстом — [1440](evidence/browser/draft-submit-1440.json), [390](evidence/browser/draft-submit-390.json) |
| AC-B1 | PASS | `QA B1 real refreshDashboard` исполняет реальный refresh→render с HTTP/DOM: [baseline FAIL](evidence/baseline-regressions.log.gz), [targeted PASS](evidence/targeted.log.gz); browser обновляет этап после controlled30s, тот же details node |
| AC-B2 | PASS | Два `QA B2` с управляемым завершением HTTP — [targeted](evidence/targeted.log.gz); browser закрывает/раскрывает во время запроса, ждёт именно применения нового этапа |
| AC-B3 | PASS | `QA B3` — reorder, текущие/история, новая операция, другой Cycle, removal/reappearance, owner/epoch и stale read: [targeted](evidence/targeted.log.gz); browser reorder/new operation/removal — [390](evidence/browser/dashboard-actions-390.json), [1440](evidence/browser/dashboard-actions-1440.json) |
| AC-B4 | PASS | Browser1440/390: Enter/Tab, copy focus и clipboard с актуальным этапом; выделение номера сохраняется при visibility refresh, scrollY/cardTop неизменны; focus fallback при смене/удалении операции. [390](evidence/browser/dashboard-refreshed-390.json), [1440](evidence/browser/dashboard-refreshed-1440.json), [лог](evidence/browser-acceptance.log.gz). Новое внешнее focus во время запроса не перехватывается — `QA B4` в frontend |
| AC-R1 | PASS | [404 frontend](evidence/frontend.log.gz), [6 browser](evidence/browser-acceptance.log.gz); два существующих `04 review real screens` проверяют готовность оценки, следующую ситуацию, отчёт и админку; текущие UI04/05 сохранены, CSS не менялся |

## Команды и фактические результаты

Рабочая папка — корень репозитория, Node v22-совместимый существующий npm-контур.

| Команда | Результат |
| --- | --- |
| `node --test tests/frontend/*.test.mjs` | exit0, **404 PASS**, [tested SHA/exit](evidence/frontend-result.json) |
| `node --test tests/frontend/answer-drafts.test.mjs tests/frontend/postw02-dashboard.test.mjs tests/frontend/preparation-status.test.mjs` | exit0, **53 PASS**, [лог](evidence/targeted.log.gz) |
| `npm run lint:js` | exit0, [лог](evidence/lint.log.gz) |
| `npm run build:web` + `git diff --exit-code -- web/dist` | exit0/0, **44 совпадающих файла**, [хеши](evidence/build-consistency.json) |
| `npx playwright test tests/browser/postw02-qa-state.spec.mjs tests/browser/preparation-status.spec.mjs --grep 'QA \|04 review real screens (1440\|390)' --workers=1 --retries=0 --timeout=20000 --global-timeout=300000` | exit0, **6 PASS /12.4s**, [лог](evidence/browser-acceptance.log.gz); evidence env указывает в эту задачу |
| `git diff --check` | PASS перед code commit; повтор перед передачей evidence |

Тестовый профиль: один worker, retries0, общий предел300s, step/request20s,
управляемые API и часы, реальных LLM/mail0. Существующие обязательные CI применяют
собственный профиль. Browser listener разрешён вне sandbox после локального EPERM.
Первый функциональный browser run:3PASS/1FAIL из-за недостаточного ожидания в новом
тесте (следующий visibility event попадал в pending предыдущего запроса). Причина
устранена ожиданием обновлённого этапа, [диагностика](evidence/browser.log.gz) сохранена.
Последующие затронутый и итоговый прогоны PASS; расширения после PASS нет.

## Визуальная проверка и ресурсы

Просмотрены исходные PNG: [черновик390](evidence/browser/draft-new-text-390.png),
[черновик1440](evidence/browser/draft-new-text-1440.png),
[dashboard390](evidence/browser/dashboard-refreshed-390.png),
[dashboard1440](evidence/browser/dashboard-refreshed-1440.png).
Нет горизонтального переполнения, disclosure/кнопки доступны; оформление04/05
сохранено. Native размеры/хеши — [manifest](evidence/screenshots.json).
Дополнительные снимки неизменённых потребителей лежат в `evidence/consumers/`.

Owned HTTP-серверы завершены: [QA cleanup](evidence/browser/cleanup.json),
[consumers cleanup](evidence/consumers/cleanup.json), [проверка listener](evidence/resources.json).
Временные baseline-копии удалены через TemporaryDirectory. БД/Docker/LLM/почта
не запускались; чужие сервисы не останавливались. Preview не оставлен.

## Источники, границы и передача

Основания/пробелы/полномочия — [STATE](STATE.md). Дополнительно прочитан ADR-002,
контракты идентичности/C-45 и точных Turns. M7v1.3 §§5.3–5.6 → сохранность материала
и прежние временные границы → PM-04/LU-04.3/04.5 → guard черновика → AC-A1–A4.
Существующее клиентское представление LU-04.2 → keyed Cycle/operation → AC-B1–B4.
Методологическая оценка не затронута; новые LU/статусы CURRENT не назначались.

Principles10.10/Task Rules14.11 найдены, но Google Drive возвращает ошибку чтения;
доступного исходного содержимого нет. Это явное ограничение чтения источников,
их соответствие не заявляется. Технический объём и пределы полностью определены
текущей постановкой и EVC. Преемник применимой архитектуры/глоссария не обнаружен.

Исторические144 проверки и полные backend/SQL результаты04/05 не засчитываются
как проверка исправления. Переиспользованы только неизменённые архитектурные
основания и принятые UI; регрессии выполнялись заново. Backend/HTTP/SQL набор здесь
**NOT_RUN**: сервер/схема/контракт не менялись, локальный JS минимум матрицы выполнен.
Physical mobile/полный Cycle/real AI/живые участники — **NOT_RUN**, вне объёма.

Локальная приёмка AC — PASS. PR передаётся в draft: version_bump/Ready/merge/deploy/
artifact_publish=false, отдельного допуска на номер/merge нет. CI/человеческое
review/TEST/Prod фиксируются отдельно; локальный PASS их не заменяет.
Откат — revert code commit с его generated dist; данных/миграции для отката нет.
Управляющие файлы, предметные пакеты и snapshots не менялись.

# P4K-POSTW02-02 — отчёт

Локальная реализация завершена. Основание и границы — [TASK.md](TASK.md).
Base: `a37a4519cc461339a55aaf7343624fce6e91511f` / main2.1.14 / PR228.
Head фиксируется в PR и локальном delivery receipt после commit; identity содержимого —
[evidence/identity.json](evidence/identity.json). Ветка `codex/p4k-postw02-02`.

## Изменения

- Общая `participant_dashboard.cycle_progress` из POSTW02-01 подключена к runtime
  и return-state. Новые совместимые поля `participant_progress` и подтверждённое
  `blocking_system_wait`; второй расчёт плана не вводится. Проверка provenance
  (Cycle/profile/revision/предъявление) остаётся общей с кабинетом.
- Один индикатор N/M; отсутствие completed не скрывает известную позицию. Нет
  completed+1 и декоративной полосы. При неизвестной позиции выводится только
  подтверждённый общий план; между ситуациями — номер завершённой, без следующего старта.
- Ситуация остаётся единственным начальным сообщением из participant_payload;
  данные не превращаются в новые Turns. Одна колонка, компактный ввод/отправка,
  вторичное завершение под диалогом. Убраны прежний AI-подвал и технические строки.
- Ручные pause/interrupt отсутствуют в обычном активном чате. Клиентские обработчики
  позволяют только recovery уже сохранённого paused/interrupted. Удалён клиентский
  вызов interrupt_for_continuation. Серверные запреты API **не реализованы**: POSTW02-03.
- Pending после 45 секунд остаётся нейтральным. Один deadline на сохранённую фазу,
  без продления при retry/reload; по исчерпании автоматические чтения обработки
  прекращаются, остаётся ручная проверка GET. Сбой чтения, WAIT_TECHNICAL и failed
  различаются. Неизвестный исход ответа не объявляется сохранением, черновик остаётся.
- Active допускает scenario_end после сохранённого ответа без преждевременного
  требования finish_availability. Окончательное закрытие после анализа/уточнения
  доступно только по серверному разрешению. R1 Continue сохраняет AS/историю/вопрос.

## Проверки

| Проверка | Итог и доказательство |
|---|---|
| `node --test tests/frontend/*.test.mjs` | PASS351; frontend.log. После последнего небольшого изменения видимости between-header — адресный PASS26, final-scoped.log, затем проверка recovery23 (recovery-final.log) |
| `npm run test:backend` | PASS1121 составно: 1112 в общем прогоне, 9 test_synthetic_limits в повторе `--lf` после sandbox EPERM на ps; backend.log и backend-sandbox-retry.log. Между прогонами backend не менялся |
| `npm run test:backend:http` | PASS177; http.log. Новые2 — реальный owner HTTP с синтетическим SELECT-only хранилищем, общая projection и отсутствие мутаций |
| `npm run lint:js`, `npm run build:web`, `git diff --check` | PASS; lint.log/build.log; frontend/dist fingerprints в identity |
| Browser Chromium1440/390 | PASS:5 в browser.log (новые3 + существующие F18/F19 plan8/3). После финальной компоновки затронутые3 повторены PASS в browser-final.log |
| Exact v10 local reference | PASS получения рендеров5 сцен ×2 ширины, SHA e44fa78. [Галерея](VISUAL_REVIEW.html); не утверждается пиксельная тождественность разных материалов/данных |
| GitHub CI | Состояние точного head будет в PR/delivery receipt. Локальные результаты не подменяют CI |

Первичные неуспехи сохранены: устаревшие expectations двух счётчиков, неполная
HTTP-fixture, sandbox EPERM. Исправленные ожидания не заменяют переходные проверки:
добавлены тесты pending45s/read failure/failed/WAIT_TECHNICAL/server ASK,
неизменного deadline, восстановления consumed continuation intent без повторной Session, GET-only manual checks, late response, unknown draft,
сохранённого recovery и запрета новых клиентских pause/interrupt.

В браузере проверены короткие/длинные условия и ввод, Tab, скролл истории,
отсутствие перекрытия формы/горизонтального переполнения, пять состояний,
сохранение той же AS/вопроса после R1 Continue и прекращение polling при уходе.
Готовый следующий шаг не стартует из GET. Backend guards не выдаются за проверенные.
Собственные HTTP-серверы закрыты: browser/cleanup.json. DB/LLM/mail=0.

NOT_RUN: авторизованный опубликованный Site/Google login; реальные устройства и
экранная клавиатура; Prod, выпуск, ручная приёмка владельцем, платный provider,
полный синтетический PATH. Integration на локальной PostgreSQL не запускался:
изменены только чтение/проекция/UI; HTTP-контракт проверен без пользовательской БД.
Draft PR откладывает release gate/full-verification до Ready и отдельного номера
кандидата; обязательные workflow сохранены. Merge/deploy не выполняются.

## Риски, совместимость и откат

Аддитивные поля read model, прежние snapshots и saved policy сохранены. Старые
клиенты получают прежние route.progress с валидированным знаменателем; отсутствие
достоверного плана теперь честно null. Для ответа без новой projection совместимо
читается уже существующая явная серверная позиция; вычисления из completed нет.
Неизвестный сетевой исход продолжения восстанавливается существующим ключом.
Не меняются схема/права/данные/артефакты/авторские тексты/W02/анкета/профилирование.
Остаток: запрет старых API-мутаций и совместимость сохранённых состояний — задание03.
Откат — revert данного коммита/PR и пересборка dist, без миграции и потери данных.
